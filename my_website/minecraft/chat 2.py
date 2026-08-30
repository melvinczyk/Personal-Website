"""The server's chat, kept because the server does not keep it.

kubejs/exported/chat_log.json is a rolling buffer, and a small one: the export
carries a `capacity` and it has been ten and is now fifteen. Whatever the
last slot pushes off the end is gone from the server's side for good, so
reading that file is only ever a look at the last few minutes of talk. Nothing
here reads `capacity` - it is the poll interval that decides how much survives,
and a bigger buffer only buys more slack.

That is the whole reason this module exists. Every read merges what the buffer
holds into an archive on disk, keyed so that seeing the same message five polls
running adds it once. The buffer is the window; the archive is the record, and
the page reads the archive.

Two consequences worth stating plainly:

  * How often this runs decides how much is kept, and *whether it runs at all*
    decides the rest. Fifteen messages is a busy minute on a full server, so a
    poll every twenty-five seconds keeps everything and a poll every ten
    minutes keeps a fraction of it. Nothing here can recover what rolled off
    between two reads - it was never sent to us - and nothing here pretends
    otherwise: a gap is simply absent, not marked.
  * Worth saying twice: puller.refresh_chat only pulls while somebody has the
    page open, so an evening with no tab open keeps nothing at all. Where the
    archive is meant to be a record rather than a window, `sync_chat --loop`
    has to be running as a task of its own - see that command.
  * The archive only grows forwards. It starts the day this first runs, and no
    amount of polling will recover what the server said before that.

Read-only, like the rest of the sync. There is no path back to the game.
"""

import json
import os
import posixpath
import time
from datetime import datetime, timezone

from . import censor, sync

# Where the buffer lives on the game host, under the same remote root the rest
# of the sync is relative to.
REMOTE = "kubejs/exported/chat_log.json"

# What lands in the season's data folder. Deliberately not the remote file's
# own name: that one is the ten-message window and this one is the record, and
# a folder holding both under names a letter apart would be a trap.
ARCHIVE = "chat_history.json"

# What the last look at the buffer looked like, so an unchanged file can be
# left alone rather than downloaded again. Size and mtime only; it is beside
# the archive rather than in it because it is bookkeeping, not chat.
CURSOR = ".chat.seen"

# How much talk the archive keeps. A season is months long and a chatty
# evening is a few hundred lines, so this is a bound on the file rather than a
# retention policy anyone will notice: the box shows a window of it.
ARCHIVE_MAX = 2000

# Refuse anything absurd rather than pulling it into memory. The buffer holds
# ten messages; a megabyte of it means something is wrong at the other end.
MAX_BYTES = 512 * 1024


class ChatError(sync.SyncError):
    """A chat pull that failed in a way worth reporting on the board."""


def archive_path(data_dir):
    return os.path.join(data_dir, ARCHIVE)


def _cursor_path(data_dir):
    return os.path.join(data_dir, CURSOR)


# ── the archive on disk ──────────────────────────────────────────────────────

def _blank():
    return {'seq': 0, 'updated': '', 'messages': []}


def load(data_dir):
    """The archive, or an empty one. Never raises on a bad file.

    A chat box is the least important thing on the page and the easiest thing
    to have half-written when a process is taken away mid-poll. Losing the
    archive costs the record of a conversation; taking the portal down with it
    would cost the rest of the page, so a file that will not parse is treated
    as no file at all and the next merge writes a fresh one.
    """
    try:
        with open(archive_path(data_dir)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict) or not isinstance(data.get('messages'), list):
        return _blank()
    data.setdefault('seq', 0)
    data.setdefault('updated', '')
    return data


def _key(message):
    """What makes two readings of the buffer the same message.

    The timestamp is to the millisecond and carries the player with it, so two
    people saying "gg" in the same second stay apart and one person saying it
    twice in the same millisecond - which is not a thing a keyboard does -
    would not. That is the right way round for a dedupe key.
    """
    return (message.get('at') or '', message.get('uuid') or '',
            message.get('name') or '', message.get('text') or '')


def _clean(raw):
    """One message from the export, reduced to what the page needs.

    Masked here, on the way in, rather than where it is drawn: the archive is
    a file on disk that gets deployed with the site, so filtering on the way
    out would leave the unmasked words sitting in it anyway. There is no copy
    of the original - see censor.py.

    Markup, by contrast, is left exactly as it arrived. It is escaped where it
    is drawn: a line holding a < is a line about arrows, and mangling it here
    would make it impossible to draw correctly later.
    """
    if not isinstance(raw, dict):
        return None
    text = raw.get('text')
    name = raw.get('name')
    if not isinstance(text, str) or not isinstance(name, str) or not text:
        return None
    return {
        'at':   str(raw.get('at') or ''),
        'name': name,
        'uuid': str(raw.get('uuid') or ''),
        # a single line's worth. The game caps chat well below this; the cap is
        # here so a mod that logs a wall of text cannot push the archive over
        # its own size bound in one message. Trimmed before masking, so a word
        # can never be half-cut into something the filter does not recognise.
        'text': censor.clean(text[:512]),
    }


def merge(data_dir, payload):
    """Fold one reading of the buffer into the archive.

    Returns how many messages were new. Ordering is the buffer's own: the
    export writes oldest first and that is the order they are appended in, so
    `seq` climbs with time without this having to trust or parse a timestamp.
    """
    if not isinstance(payload, dict):
        raise ChatError('chat_log.json is not an object')
    incoming = payload.get('messages')
    if not isinstance(incoming, list):
        raise ChatError('chat_log.json has no messages list')

    archive = load(data_dir)
    # only the tail can overlap with a buffer this small, and comparing against
    # the whole archive would mean rebuilding a two-thousand entry set on every
    # poll to catch at most ten
    window = max(len(incoming) * 4, 64)
    seen = {_key(m) for m in archive['messages'][-window:]}

    added = 0
    for raw in incoming:
        message = _clean(raw)
        if message is None or _key(message) in seen:
            continue
        seen.add(_key(message))
        archive['seq'] += 1
        message['seq'] = archive['seq']
        archive['messages'].append(message)
        added += 1

    if added:
        archive['messages'] = archive['messages'][-ARCHIVE_MAX:]
    archive['updated'] = str(payload.get('updated') or '')
    archive['checked'] = time.time()
    _write(data_dir, archive)
    return added


def touch(data_dir):
    """Record that we looked, when there was nothing new to bring back.

    The stamp is meant to move whether or not anything was said, so the box can
    tell "nobody is talking" from "we have not looked in an hour". It did not:
    the only thing writing it was merge(), and pull() returns before merge()
    whenever the remote file has not moved - which on a quiet server is every
    single poll. The archive sat there claiming it had last been checked
    thirteen minutes ago while the pull was in fact running every twenty-five
    seconds and finding nothing, which is the opposite of what the stamp is for.
    """
    archive = load(data_dir)
    archive['checked'] = time.time()
    _write(data_dir, archive)


def _write(data_dir, archive):
    """Atomically, so a page reading mid-write sees the old file, not half."""
    path = archive_path(data_dir)
    part = path + '.part'
    os.makedirs(data_dir, exist_ok=True)
    with open(part, 'w') as fh:
        json.dump(archive, fh)
    os.replace(part, path)


# ── the pull ─────────────────────────────────────────────────────────────────

def _seen(data_dir):
    try:
        with open(_cursor_path(data_dir)) as fh:
            size, mtime = fh.read().split()
            return int(size), int(mtime)
    except (OSError, ValueError):
        return None


def _remember(data_dir, size, mtime):
    try:
        with open(_cursor_path(data_dir), 'w') as fh:
            fh.write(f'{size} {mtime}')
    except OSError:
        pass                                 # bookkeeping, never a fault


def pull(sftp, cfg, data_dir):
    """One look at the buffer. Returns (added, changed).

    Two requests when there is something new and one when there is not: the
    file is stat'ed first and only read if its size or mtime has moved. That
    matters more than the bytes do - the host is a game panel's SFTP gateway
    and it is the number of requests it minds - and this is the one pull that
    runs on the order of once a minute rather than once a quarter of an hour.
    """
    remote = posixpath.join(cfg['remote_root'], REMOTE)
    try:
        attr = sftp.stat(remote)
    except IOError:
        touch(data_dir)                      # we looked; there was no file
        return 0, False                      # not exported yet: not an error

    size = attr.st_size or 0
    mtime = int(attr.st_mtime or 0)
    if size > MAX_BYTES:
        raise ChatError(f'chat_log.json is {size} B, which is too big to be chat')
    if _seen(data_dir) == (size, mtime):
        touch(data_dir)                      # looked, and it had not moved
        return 0, False

    with sftp.open(remote) as fh:
        # one read rather than paramiko's default dribble of small ones
        fh.prefetch(size)
        body = fh.read().decode('utf-8', 'replace')
    try:
        payload = json.loads(body)
    except ValueError as exc:
        # the exporter rewrites this file in place every few seconds, so
        # catching it mid-write is expected rather than alarming: say nothing,
        # leave the cursor alone, and the next poll gets the finished file
        raise ChatError(f'chat_log.json did not parse: {exc}')

    added = merge(data_dir, payload)
    _remember(data_dir, size, mtime)
    return added, True


# ── what the page reads ──────────────────────────────────────────────────────

# What a box in the corner of a screen can show without becoming the screen.
WINDOW = 60

# How old the newest message may be before the box is emptied.
#
# The archive is a record and keeps everything; this is about what a box in the
# corner of a live page should be showing. A conversation from this morning
# sitting under a heading that says SERVER CHAT reads as the chat, and somebody
# glancing at it takes it for what is being said now. An empty box says the
# true thing, which is that nobody is talking.
#
# Nothing is deleted. The moment anybody speaks again the box fills from that
# message on, and the archive behind it still holds every word.
STALE = 60 * 60


def _when(text):
    """'2026-08-22T06:17:50.402Z' -> an aware datetime, or None."""
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    # a stamp with no zone is read as the server's own clock, which is UTC:
    # comparing a naive datetime against an aware one raises, and a chat box
    # is not worth a 500
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _cold(messages):
    """True if the last thing said is older than STALE.

    Unknown counts as warm. A message whose stamp will not parse is a message
    we cannot date, and emptying the box on the strength of a reading we could
    not take would hide a live conversation.
    """
    for message in reversed(messages):
        when = _when(message.get('at'))
        if when is None:
            continue
        return (datetime.now(timezone.utc) - when).total_seconds() > STALE
    return False


def board(data_dir, since=None, limit=WINDOW):
    """The chat as the page wants it: everything after `since`, and a cursor.

    A first load gets the last `limit` messages and the sequence number they
    end at; every poll after that asks for what came next, which on a quiet
    server is nothing at all and costs a few dozen bytes to say so.
    """
    archive = load(data_dir)
    messages = archive['messages']
    cold = _cold(messages)
    if cold:
        fresh = []
    elif since is None:
        fresh = messages
    else:
        fresh = [m for m in messages if m.get('seq', 0) > since]
    # the newest of them when there are more than fit, not the oldest. A box
    # that has been left open through a busy evening wants the end of the
    # conversation on its next poll, and taking from the front would have it
    # crawl through the backlog a window at a time, always behind.
    shown = fresh[-limit:]
    return {
        'messages': shown,
        # the box empties itself on this rather than on a clock of its own, so
        # a tab open for hours and a tab opened just now agree about what the
        # server has been saying
        'stale': cold,
        # how much was passed over to get to those, so the box can say the
        # feed jumped rather than silently splicing two ends of an evening
        'skipped': len(fresh) - len(shown),
        'seq': archive['seq'],
        'updated': archive.get('updated') or '',
        'checked': archive.get('checked'),
        'total': len(messages),
    }
