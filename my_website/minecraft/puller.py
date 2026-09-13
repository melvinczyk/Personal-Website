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
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

from django.conf import settings

from . import activity, chat, history, sync
from .live import MAP_STAMP, MAP_TRY_STAMP

DEFAULT_CONFIG = "mc_sync.json"

# The live world map: a BlueMap render the game host serves on a port of its
# own. It lives here rather than in views because it is now two things - the
# frame the page embeds, and the only witness to the server being up that does
# not go through the export. Addressed by number because the
# servermap.minecraft.bz name it used to be reached by no longer resolves.
MAP_URL = 'http://216.219.93.66:8100/'

# How long to wait on the map. It answers in about a tenth of a second when it
# is there at all, so past this it is not a slow map, it is one that is not
# coming - and a board poll must never wait on a network.
MAP_TIMEOUT = 5

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


# ── is the server actually up? ─────────────────────────────────────────────
#
# Ask the game server's own listener, the way the multiplayer menu does: open
# a socket, send a handshake and a status request, read back the JSON it
# answers with. That is the Server List Ping, and it is the only witness that
# means what the badge claims to mean.
#
# This used to ask the map instead - does http://<host>:8100/ answer? - on the
# reasoning that BlueMap runs inside the game server, so the webserver being
# up and the server being up are the same fact. They are not, and the thing
# that separates them is ReadyPlayerFun: it halts the server's tick loop while
# nobody is playing, and BlueMap's webserver sits behind that loop and stops
# answering with it. The server is still running and still joinable the whole
# time. So the map's verdict was really "is somebody playing right now", and
# the badge went dark every time the last player logged off - which is exactly
# what it is not supposed to do.
#
# The status ping does not have that problem, and cannot: a pause-when-empty
# mod has to keep the network listener accepting, because an incoming join is
# the thing that wakes it. If the listener were asleep the server could never
# be woken, so anything that answers a ping is a server that can still be
# joined. That is the definition the badge wants.
#
# The player count rides along for free, which is a second witness to who is
# on that does not go through the export at all.
#
# The map is kept as a fallback rather than deleted: if the ping is ever
# blocked where the site runs - a host that allows outbound HTTP and nothing
# else would do it - an answering map is still proof the server is up. It can
# only ever turn a "no" into a "yes", so the pause it goes quiet for costs
# nothing now that it is no longer the one being asked.
#
# Never raises. A server that cannot be reached is a "no", and the reason is
# kept so that a probe failing on the deployed box can actually be seen - see
# map_state, which the board carries. That was the real cost of the old
# version: every failure mode looked identical from outside, which is how a
# server that had been up for hours could read OFFLINE with nothing to say
# why.

# Where the game actually listens. Not the SFTP host in mc_sync.json (that is
# the panel's file gateway, on a port of its own) and not the map's address
# either - the same box serves several servers, and :25565 on it belongs to
# somebody else's. This is the address the client's own server list holds.
GAME_HOST = 's45.oddblox.us'
GAME_PORT = 29502

# The protocol number the handshake claims to speak. A status ping is answered
# whatever this says - the field only matters once a client tries to join, and
# this never does - so it is pinned rather than kept up with the server.
PROTOCOL = 765

# A status response carries the favicon as base64, so it is tens of kilobytes
# on a server that has one. Past this something is wrong with the framing and
# reading further is not going to fix it.
PING_CAP = 512 * 1024

# what the last probe did, for diagnosis rather than for the verdict
_map_last = {'at': 0.0, 'ok': None, 'why': 'not asked yet', 'ms': None}


def map_state():
    return dict(_map_last)


def _varint(n):
    """A Minecraft varint: seven bits at a time, high bit says 'more coming'."""
    out = b''
    while True:
        part = n & 0x7F
        n >>= 7
        out += bytes([part | (0x80 if n else 0)])
        if not n:
            return out


def _read_varint(sock):
    n = shift = 0
    while True:
        got = sock.recv(1)
        if not got:
            raise EOFError('socket closed mid-varint')
        byte = got[0]
        n |= (byte & 0x7F) << shift
        shift += 7
        if shift > 35:
            raise ValueError('varint too long')
        if not byte & 0x80:
            return n


def _ping_alive(timeout, host=GAME_HOST, port=GAME_PORT):
    """Does the game server answer a status ping? Returns (ok, why).

    Two packets out, one back. The handshake names the protocol, the address
    dialled and the port, and asks for state 1 (status) rather than 2 (login),
    so this never takes a player slot and never shows up as a join attempt.
    """
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout)
        sock.settimeout(timeout)
        addr = host.encode('utf-8')
        shake = (b'\x00' + _varint(PROTOCOL)
                 + _varint(len(addr)) + addr
                 + struct.pack('>H', port) + _varint(1))
        sock.sendall(_varint(len(shake)) + shake)
        sock.sendall(_varint(1) + b'\x00')       # status request, empty body

        _read_varint(sock)                       # packet length, unused
        if _read_varint(sock) != 0:              # packet id: 0 is the response
            return False, 'ping: unexpected packet id'
        size = _read_varint(sock)
        if size <= 0 or size > PING_CAP:
            return False, f'ping: implausible body ({size} bytes)'
        body = b''
        while len(body) < size:
            chunk = sock.recv(min(8192, size - len(body)))
            if not chunk:
                return False, 'ping: truncated response'
            body += chunk

        # The count is the interesting half of the answer, but a server that
        # framed a reply at all has already said the only thing being asked.
        # So a body that will not parse is still a yes, with a note on it.
        try:
            data = json.loads(body.decode('utf-8', 'replace'))
            players = data.get('players') or {}
            version = (data.get('version') or {}).get('name') or '?'
            return True, (f'ping {version}, '
                          f'{players.get("online")}/{players.get("max")} online')
        except (ValueError, AttributeError):
            return True, 'ping: answered, body unreadable'
    except Exception as exc:                     # noqa: BLE001 - see comment
        return False, f'{type(exc).__name__}: {exc}'
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _map_alive(timeout):
    """Does the map's webserver answer? Returns (ok, why).

    The fallback witness, not the verdict - see the note above. It goes quiet
    whenever ReadyPlayerFun pauses the server, so a "no" from here means
    nothing on its own and is never allowed to decide anything.
    """
    try:
        with urllib.request.urlopen(MAP_URL, timeout=timeout) as res:
            code = getattr(res, 'status', None) or res.getcode()
            res.read(1)                          # prove the body is coming too
            return 200 <= code < 400, f'map HTTP {code}'
    except urllib.error.HTTPError as exc:
        # Something is listening and speaking HTTP, which is the whole
        # question - a 404 from BlueMap's own webserver still means the
        # process behind it is alive. A 5xx is a gateway apologising for
        # something that is not, and a 403 or 407 is very often a proxy
        # refusing to carry the request at all, which is not a witness to
        # anything on the far side.
        ok = exc.code < 500 and exc.code not in (403, 407)
        return ok, f'map HTTP {exc.code}'
    except Exception as exc:                     # noqa: BLE001 - see comment
        return False, f'map {type(exc).__name__}: {exc}'


def _server_alive(timeout):
    """The ping decides; the map only ever gets to overturn a 'no'."""
    started = time.time()
    try:
        ok, why = _ping_alive(timeout)
        if ok:
            return True, why
        backup, why2 = _map_alive(timeout)
        if backup:
            return True, f'{why2} (ping failed: {why})'
        return False, f'{why}; {why2}'
    finally:
        _map_last['ms'] = int((time.time() - started) * 1000)


def probe_map(dest_dir, timeout=MAP_TIMEOUT):
    """Ask the map whether the server is there. Stamp the asking either way.

    Two stamps, and the one written on failure matters as much as the one
    written on success: without it, a probe that has never worked here is
    indistinguishable from a probe that has never run, and the board cannot
    tell "the server is down" from "we have no idea". See live.MAP_TRY_STAMP.

    The attempt stamp carries the reason as its contents, so whichever process
    is serving the board can say why the badge reads what it reads - the
    worker does the probing and the web process draws the page, and they share
    nothing but this folder.
    """
    ok, why = _server_alive(timeout)
    _map_last.update({'at': time.time(), 'ok': ok, 'why': why,
                      'url': f'{GAME_HOST}:{GAME_PORT}'})
    try:
        # the folder is normally there because the sync made it; on a checkout
        # that has never synced it is not, and the probe is the one thing that
        # still works there - so it makes its own place to write to
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, MAP_TRY_STAMP), 'w',
                  encoding='utf-8') as fh:
            fh.write(f'{GAME_HOST}:{GAME_PORT} -> {why}')
        if ok:
            open(os.path.join(dest_dir, MAP_STAMP), 'w').close()
    except OSError as exc:
        # A stamp that cannot be written is not a probe that failed, but it is
        # the reason the badge will not move - so it is worth saying, because
        # returning quietly here leaves the board reading OFFLINE with a probe
        # that believes it succeeded.
        _map_last['why'] = f'{why}, but the stamp failed: {exc}'
    return ok


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
        # and the per-player history, which is the same idea one level down:
        # what each of their numbers was, banked so there is a curve behind
        # them later. Nothing the export carries has one - see history.py
        try:
            history.sample(dest_for(season))
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


# How often the map is asked, when nothing else is asking it. The board is
# polled about once a minute by every open tab, so this is the throttle that
# turns "every poll" into "every couple of minutes" - the same cadence the
# file sync probes at, and three of these fit inside MAP_WINDOW.
MAP_INTERVAL = 120

_map_lock = threading.Lock()
_map_busy = False
_map_at   = 0.0


def refresh_map(season):
    """Ask the map whether the server is there, if it is time to ask again.

    Its own job, on its own clock, deliberately.

    It used to be the last line of a successful file pull, and that was fine
    while the badge had two witnesses and only needed one of them. It is not
    fine now that the map is the whole of the verdict, because of when a pull
    stops succeeding: an unconfigured checkout, wrong credentials, an SFTP
    gateway having a bad afternoon - every one of those skipped the probe
    entirely, and the moment you most want to know whether the server is up is
    exactly the moment the file sync has stopped working.

    So the probe no longer rides along with anything. It answers about the
    game server; the sync answers about a file gateway; they fail for
    different reasons and they are asked separately.

    Returns at once, always - the probe runs on its own thread, and the board
    is drawn from whatever is on disk.
    """
    global _map_busy, _map_at
    # Deliberately not gated on web_pull_allowed().
    #
    # That flag turns off *SFTP pulls driven by page views*, because on a box
    # with a scheduled worker the pulls are its job and a web request has no
    # business opening an SFTP session. This is one HTTP GET to a map, it
    # takes about a tenth of a second, and gating it meant that on the one
    # configuration where the flag is actually set - the deployed one - the
    # web process never probed at all and the badge could only ever be as
    # right as the worker's last run. Which, when the worker's probe was
    # failing, was never.
    with _map_lock:
        if _map_busy or time.time() - _map_at < MAP_INTERVAL:
            return
        _map_busy = True
        _map_at = time.time()
    threading.Thread(target=_map_probe, args=(season,), daemon=True).start()


def _map_probe(season):
    global _map_busy
    try:
        probe_map(dest_for(season))
    except Exception:                        # noqa: BLE001 - never fail a poll
        pass                                 # probe_map does not raise anyway
    finally:
        with _map_lock:
            _map_busy = False


def refresh(season, force=False):
    """Ask for a pull. Returns at once, whether or not one was started."""
    global _running
    # The map is asked whatever the sync is doing, and before the sync's own
    # throttle can return early - see refresh_map.
    refresh_map(season)
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
