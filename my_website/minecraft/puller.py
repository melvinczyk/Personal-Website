"""Keep the live season's data fresh while somebody is looking at it.

The portal polls a board that is only as good as the files under it, and those
files come off the server over SFTP. Rather than lean on a cron job that runs
whether or not anyone is watching, the board's own endpoint asks for a pull.

That request never waits for the network. A pull runs on a background thread
and the caller is told what the state of things is; the next poll, seconds
later, picks up whatever landed. So a slow or unreachable server costs a page
nothing, and the worst case is a board that says how old its numbers are.
"""

import json
import os
import threading
import time

from django.conf import settings

from . import activity, chat, sync

DEFAULT_CONFIG = "mc_sync.json"

# How long a pull's results are treated as current. The server rewrites its
# export once a minute, but the host's SFTP gateway is a panel service that
# does not care to be logged into once a minute for ever, so the board reads
# it a quarter of an hour at a time. The refresh button ignores this.
MIN_INTERVAL = 15 * 60

# What the always-on worker fetches everything at, which is a different
# question from the one above and gets a different answer.
#
# MIN_INTERVAL governs the page-driven pull, where every web worker that gets a
# poll may open its own connection to the game host - so it is deliberately
# slack. The worker is one process on one clock, and it is already connecting
# every CHAT_INTERVAL seconds for the chat buffer; a full pull only ever runs
# on a tick that has connected anyway, so running it more often costs a
# directory listing and whichever files actually changed, and not one extra
# handshake. In practice that is one listing and one 95KB world_data.json.
#
# Two minutes rather than fifteen because everything on the board except chat
# was quarter-of-an-hour stale, which for "who is online" is most of a session.
FULL_INTERVAL = 120

# A host that has just refused us will not have changed its mind on the next
# tick, and a game panel's SFTP gateway is exactly the kind of thing that
# starts refusing when it is asked too often. Each failure in a row doubles
# the wait, up to an hour; one success clears it.
BACKOFF_CAP = 60 * 60

# The chat buffer is its own pull on its own clock. Everything else the site
# reads is a tally that is no worse for being a quarter of an hour old, but
# chat that is a quarter of an hour old is not chat - and the server's buffer
# only holds ten messages, so a slow poll does not just show the talk late, it
# loses most of it. See chat.py.
#
# It can afford the tempo because it is one stat and, only when that moves, one
# read of a file measured in hundreds of bytes. The quarter-hour pull is five
# files and the whole world's numbers.
CHAT_INTERVAL = 25

_lock    = threading.Lock()
_running = False
_fails   = 0
_last    = {'at': 0.0, 'state': 'idle', 'message': '', 'fetched': 0,
            'wait': MIN_INTERVAL}


# Some hosts put their web workers somewhere the outside world is harder to
# reach from than a console on the same machine is: the socket dies during the
# SSH handshake and paramiko reports "No existing session", while the identical
# config pulls happily from a shell. Recycled workers make it worse, killing a
# pull mid-flight and leaving its lock behind.
#
# Where that is so, stop the page dialling out at all. A scheduled
# `manage.py sync_server` does the fetching, the page reads what it leaves on
# disk, and Refresh re-reads that rather than opening a connection nobody is
# going to answer. MC_SYNC_WEB_PULL=0 turns the page's own pulling off.
def web_pull_allowed():
    return os.environ.get("MC_SYNC_WEB_PULL", "1").strip().lower() not in (
        "0", "false", "no", "off")


SCHEDULED = {'at': 0.0, 'state': 'scheduled', 'fetched': 0, 'wait': 0,
             'message': 'the server is read on a schedule',
             'running': False, 'ago': None}


_chat_lock = threading.Lock()
_chat_busy = False
_chat_at   = 0.0
_chat_fails = 0
_chat_last = {'at': 0.0, 'state': 'idle', 'message': '', 'added': 0}


def _chat_pull(season):
    """One look at the chat buffer. Runs on its own thread."""
    global _chat_busy
    try:
        cfg = sync.load_config(config_path())
        client, sftp = sync.connect(cfg)
        try:
            added, changed = chat.pull(sftp, cfg, dest_for(season))
        finally:
            sftp.close()
            client.close()
        _chat_mark('ok', f'{added} new' if added else 'nothing new', added)
    except sync.ConfigError as exc:
        _chat_mark('unconfigured', str(exc).splitlines()[0])
    except Exception as exc:                 # noqa: BLE001 - never 500 a poll
        _chat_mark('error', f'{type(exc).__name__}: {exc}')
    finally:
        with _chat_lock:
            _chat_busy = False


def _chat_mark(state, message, added=0):
    global _chat_fails
    _chat_fails = _chat_fails + 1 if state == 'error' else 0
    _chat_last.update({'at': time.time(), 'state': state,
                       'message': message, 'added': added})


def refresh_chat(season):
    """Ask for a chat pull if one is due. Returns at once, always.

    Deliberately not sharing the season lock with the main sync. That lock
    exists to stop two runs writing the same five files at once; chat writes
    one file nothing else touches, and making a twenty-five second poll queue
    behind a five-file pull would give the box a stall every quarter hour for
    no benefit at all.
    """
    global _chat_busy, _chat_at
    if not web_pull_allowed():
        return {'state': 'scheduled', 'at': _chat_last['at']}
    # a failing pull backs off the same way the main one does, so a host that
    # has stopped answering is not asked every twenty-five seconds for ever
    wait = min(CHAT_INTERVAL * 2 ** _chat_fails, BACKOFF_CAP)
    with _chat_lock:
        if _chat_busy or time.time() - _chat_at < wait:
            return dict(_chat_last)
        _chat_busy = True
        _chat_at = time.time()
    threading.Thread(target=_chat_pull, args=(season,), daemon=True).start()
    return dict(_chat_last)


def config_path():
    return (os.environ.get("MC_SYNC_CONFIG")
            or os.path.join(str(settings.BASE_DIR), DEFAULT_CONFIG))


def static_root():
    return os.path.join(str(settings.BASE_DIR), str(settings.STATICFILES_DIRS[0]))


def dest_for(season):
    return os.path.join(static_root(), "minecraft", season, "data")


def lock_for(season):
    return os.path.join(str(settings.BASE_DIR), f".{season}.sync.lock")


def _pull(season):
    """One pull, start to finish. Runs on its own thread."""
    global _running
    try:
        cfg = sync.load_config(config_path())
        with sync.Lock(lock_for(season)) as guard:
            if not guard.held:
                _mark('busy', 'another pull is already running')
                return
            client, sftp = sync.connect(cfg)
            try:
                got, same, missing, skipped = sync.fetch(
                    sftp, cfg, dest_for(season), log=lambda _line: None)
            finally:
                sftp.close()
                client.close()
        # the counters only mean anything as a difference, so a sample is
        # taken every time we have a fresh export in hand - see activity.py
        try:
            activity.sample(dest_for(season))
        except Exception:                    # noqa: BLE001 - never fail a pull
            pass
        _mark('ok', f'{got} fetched, {same} unchanged', fetched=got)
    except sync.ConfigError as exc:
        # An unconfigured checkout is the ordinary case, not a fault: say so
        # plainly so the board can tell a config still to be filled in from a
        # server that cannot be reached.
        _mark('unconfigured', str(exc).splitlines()[0])
    except sync.SyncError as exc:
        _mark('error', str(exc).splitlines()[0])
    except Exception as exc:                     # noqa: BLE001 - never 500 a poll
        _mark('error', f'{type(exc).__name__}: {exc}')
    finally:
        with _lock:
            _running = False


def _mark(state, message, fetched=0):
    global _fails
    _fails = _fails + 1 if state == 'error' else 0
    _last.update({'at': time.time(), 'state': state,
                  'message': message, 'fetched': fetched,
                  'wait': _wait()})


def _wait():
    return min(MIN_INTERVAL * 2 ** _fails, BACKOFF_CAP) if _fails else MIN_INTERVAL


def _report(running):
    """What to tell a page: the last pull, and how long ago it was.

    The age is worked out here rather than from the timestamp, because a
    browser's clock is its own and the two need not agree.
    """
    return dict(_last, running=running,
                ago=(time.time() - _last['at']) if _last['at'] else None)


def refresh(season, force=False):
    """Ask for a pull. Returns at once, whether or not one was started."""
    global _running
    if not web_pull_allowed():
        return dict(SCHEDULED)
    with _lock:
        if _running:
            return _report(True)
        due = force or (time.time() - _last['at']) >= _wait()
        if not due:
            return _report(False)
        # a config that is not there will not appear in the next sixty seconds
        if _last['state'] == 'unconfigured' and not force:
            if not os.path.isfile(config_path()):
                return _report(False)

        _running = True

    threading.Thread(target=_pull, args=(season,), daemon=True).start()
    return _report(True)


def state():
    if not web_pull_allowed():
        return dict(SCHEDULED)
    return _report(_running)
