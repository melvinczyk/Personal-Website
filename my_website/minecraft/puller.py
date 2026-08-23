"""Keep the live season's data fresh while somebody is looking at it.

The portal polls a board that is only as good as the files under it, and those
files come off the server over SFTP. Rather than lean on a cron job that runs
whether or not anyone is watching, the board's own endpoint asks for a pull.

That request never waits for the network. A pull runs on a background thread
and the caller is told what the state of things is; the next poll, seconds
later, picks up whatever landed. So a slow or unreachable server costs a page
nothing, and the worst case is a board that says how old its numbers are.
"""

import os
import threading
import time

from django.conf import settings

from . import sync

DEFAULT_CONFIG = "mc_sync.json"

# How long a pull's results are treated as current. The server rewrites its
# export once a minute, but the host's SFTP gateway is a panel service that
# does not care to be logged into once a minute for ever, so the board reads
# it a quarter of an hour at a time. The refresh button ignores this.
MIN_INTERVAL = 15 * 60

# A host that has just refused us will not have changed its mind on the next
# tick, and a game panel's SFTP gateway is exactly the kind of thing that
# starts refusing when it is asked too often. Each failure in a row doubles
# the wait, up to an hour; one success clears it.
BACKOFF_CAP = 60 * 60

_lock    = threading.Lock()
_running = False
_fails   = 0
_last    = {'at': 0.0, 'state': 'idle', 'message': '', 'fetched': 0,
            'wait': MIN_INTERVAL}


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
    return _report(_running)
