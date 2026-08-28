"""Pull the Minecraft server's exported data over SFTP.

The server runs vanilla Forge and nothing else: no plugin, no web hook, no way
to push anything out. What it does do is write JSON into its kubejs/exported
folder every minute, so the site reaches in over SFTP and reads it.

Read-only by design. Nothing here writes to the remote host, and every download
lands under a temporary name and is moved into place only once complete, so a
page render that arrives mid-sync sees the previous copy rather than half of the
next one.

Credentials live in a JSON config file outside version control — see
config.example.json. They are never logged or echoed.
"""

import json
import os
import posixpath
import time

import paramiko


class SyncError(RuntimeError):
    """Anything that should stop the sync with a message worth reading."""


class ConfigError(SyncError):
    """The sync is not set up yet, which is not the same as it being broken.

    A checkout with no credentials is the ordinary state of a fresh clone, and
    the board should say so plainly rather than imply the server is down.
    """


# Dropped in the destination folder every time a check completes, whether or
# not it brought anything back. Without it the only record of a check is a file
# whose contents changed, so a board could say it had not been updated in hours
# when in truth it had been asked every hour and told there was nothing new.
STAMP = ".checked"

DEFAULT_FILES = [
    "kubejs/exported/players.json",
    "kubejs/exported/boss_kills.json",
    "kubejs/exported/boss_fights.json",
    "kubejs/exported/fieldguide_counts.json",
    "kubejs/exported/fish_caught.json",
]


# ── configuration ────────────────────────────────────────────────────────────

def load_config(path):
    if not path or not os.path.isfile(path):
        raise ConfigError(
            f"no mc_sync.json at {path}.\n"
            f"  Copy minecraft/config.example.json to that path and fill in "
            f"your user and credential."
        )
    name = os.path.basename(path)
    try:
        with open(path) as fh:
            cfg = json.load(fh)
    except ValueError as exc:
        raise ConfigError(f"{name} is not valid JSON: {exc}")

    if not cfg.get("host"):
        raise ConfigError(f'{name} has no "host"')
    if not cfg.get("user"):
        raise ConfigError(f'{name} has no "user" yet')
    if not cfg.get("password") and not cfg.get("key_path"):
        raise ConfigError(f'{name} needs either "key_path" or "password"')

    cfg.setdefault("port", 22)
    cfg.setdefault("remote_root", ".")
    # DEFAULT_FILES is not a fallback, it is the floor. A config is written
    # once and kept for months while the exporter grows: mc_sync.json listed
    # the three files that existed the day it was written, so boss_fights.json
    # was never fetched after the server started writing it, and the board
    # showed a fight log frozen at whatever happened to be checked in. A file
    # the site reads and the sync never brings down is invisible - no error,
    # no missing file, just numbers that quietly stop moving - so the list a
    # config gives is what to fetch *as well as* these, never instead of them.
    cfg["files"] = list(dict.fromkeys(list(cfg.get("files") or []) + DEFAULT_FILES))
    cfg.setdefault("max_bytes", 8 * 1024 * 1024)
    cfg["_config_dir"] = os.path.dirname(os.path.abspath(path))
    return cfg


# ── connection ───────────────────────────────────────────────────────────────

def connect(cfg):
    """An SFTP session, with the host key checked rather than assumed."""
    client = paramiko.SSHClient()

    known = cfg.get("known_hosts") or "known_hosts"
    if not os.path.isabs(known):
        known = os.path.join(cfg["_config_dir"], known)
    if os.path.isfile(known):
        client.load_host_keys(known)
    # An unknown key is what interception looks like, and this connection
    # carries a credential — refuse rather than trust whatever answers.
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    kwargs = {
        "hostname": cfg["host"],
        "port": int(cfg["port"]),
        "username": cfg["user"],
        "timeout": 20,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if cfg.get("key_path"):
        kwargs["key_filename"] = os.path.expanduser(cfg["key_path"])
        if cfg.get("key_passphrase"):
            kwargs["passphrase"] = cfg["key_passphrase"]
    else:
        kwargs["password"] = cfg["password"]

    try:
        client.connect(**kwargs)
    except paramiko.AuthenticationException:
        raise SyncError("authentication refused — check the user and credential")
    except paramiko.SSHException as exc:
        if "not found in known_hosts" in str(exc):
            raise SyncError(
                f"host key for {cfg['host']} is not pinned in {known}.\n"
                f"  Pin it:  ssh-keyscan -p {cfg['port']} {cfg['host']} >> {known}\n"
                f"  Then check the fingerprint against your host's panel."
            ) from exc
        raise SyncError(f"ssh failed: {exc}") from exc
    except OSError as exc:
        raise SyncError(f"could not reach {cfg['host']}:{cfg['port']}: {exc}") from exc

    return client, client.open_sftp()


# ── fetching ─────────────────────────────────────────────────────────────────

def _listings(sftp, root, files):
    """Size and mtime for every wanted file, in one request per directory.

    The wanted files sit together in one folder, so asking the folder what it
    holds costs a single round trip where asking after each file in turn costs
    one apiece, and a file that is not there costs a failed one. The host is a
    game panel's SFTP gateway rather than a fileserver, and it is the number of
    requests it minds, not their size.
    """
    out = {}
    for folder in {posixpath.dirname(rel) for rel in files}:
        where = posixpath.join(root, folder) if folder else root
        try:
            out[folder] = {a.filename: a for a in sftp.listdir_attr(where)}
        except IOError:
            out[folder] = {}                 # unreadable or absent: all missing
    return out


def fetch(sftp, cfg, dest_dir, dry_run=False, log=print):
    """Bring dest_dir up to date.

    Returns (fetched, unchanged, missing, skipped).
    """
    os.makedirs(dest_dir, exist_ok=True)
    root = cfg["remote_root"]
    got = same = missing = skipped = 0

    listings = _listings(sftp, root, cfg["files"])

    for rel in cfg["files"]:
        remote = posixpath.join(root, rel)
        local = os.path.join(dest_dir, os.path.basename(rel))

        attr = listings.get(posixpath.dirname(rel), {}).get(posixpath.basename(rel))
        if attr is None:
            log(f"  missing   {rel}")
            missing += 1
            continue

        size = attr.st_size or 0
        mtime = int(attr.st_mtime or 0)

        if size > cfg["max_bytes"]:
            log(f"  too big   {rel} ({size} B) - skipped")
            skipped += 1
            continue

        # Skipping an unchanged file is not just about bandwidth: rewriting it
        # would churn its mtime, which is what anything downstream uses to tell
        # whether there is new data at all.
        if os.path.exists(local):
            st = os.stat(local)
            if st.st_size == size and int(st.st_mtime) == mtime:
                log(f"  unchanged {rel}")
                same += 1
                continue

        if dry_run:
            log(f"  would get {rel} ({size} B)")
            got += 1
            continue

        part = local + ".part"
        try:
            sftp.get(remote, part)
            os.utime(part, (mtime, mtime))
            os.replace(part, local)
        except BaseException:
            if os.path.exists(part):
                os.remove(part)
            raise
        log(f"  fetched   {rel} ({size} B)")
        got += 1


    # the run got all the way through, so record that it happened
    if not dry_run:
        try:
            open(os.path.join(dest_dir, STAMP), "w").close()
        except OSError:
            pass                             # a stamp is a nicety, never a fault

    return got, same, missing, skipped


def verify(dest_dir, cfg, log=print):
    """A JSON file that does not parse is worth knowing about immediately."""
    ok = True
    for rel in cfg["files"]:
        if not rel.endswith(".json"):
            continue
        path = os.path.join(dest_dir, os.path.basename(rel))
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as fh:
                json.load(fh)
        except ValueError as exc:
            log(f"  CORRUPT   {os.path.basename(rel)}: {exc}")
            ok = False
    return ok


# ── locking ──────────────────────────────────────────────────────────────────

class Lock:
    """Keep two scheduled runs from overlapping.

    A run that finds a live lock gives up quietly rather than queueing: the next
    tick is only minutes away, and two syncs writing one folder is the single
    thing that could hand a page a torn file.
    """

    # A backstop only. The usual way a lock outlives its run is the process
    # being taken away mid-pull, and that is caught by the pid below long
    # before this expires; this covers the rest, such as a lock left by a
    # process whose number has since been handed to somebody else.
    STALE = 10 * 60

    def __init__(self, path):
        self.path = path
        self.held = False

    def _dead(self):
        """True if the lock names a process that is no longer running.

        Hosts that recycle their web workers kill the pull thread wherever it
        happens to be, and the lock it was holding stays on disk. Waiting out
        the stale window then means every refresh for the next ten minutes is
        told a pull is already running, when nothing is. Asking after the
        process settles it at once.
        """
        try:
            with open(self.path) as fh:
                pid = int(fh.read().strip())
        except (OSError, ValueError):
            return False                     # unreadable: let STALE decide
        if pid == os.getpid():
            return False
        try:
            os.kill(pid, 0)                  # signal 0 only asks, never sends
        except ProcessLookupError:
            return True
        except OSError:
            return False                     # alive, just not ours to signal
        return False

    def __enter__(self):
        try:
            fresh = time.time() - os.path.getmtime(self.path) < self.STALE
            if fresh and not self._dead():
                return self
            os.remove(self.path)              # a previous run died holding it
        except OSError:
            pass
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            return self
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass
        return False
