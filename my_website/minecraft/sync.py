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

import errno
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


DEFAULT_FILES = [
    "kubejs/exported/players.json",
    "kubejs/exported/boss_kills.json",
    "kubejs/exported/boss_kills.tsv",
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
    cfg.setdefault("files", DEFAULT_FILES)
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

def fetch(sftp, cfg, dest_dir, dry_run=False, log=print):
    """Bring dest_dir up to date.

    Returns (fetched, unchanged, missing, skipped).
    """
    os.makedirs(dest_dir, exist_ok=True)
    root = cfg["remote_root"]
    got = same = missing = skipped = 0

    for rel in cfg["files"]:
        remote = posixpath.join(root, rel)
        local = os.path.join(dest_dir, os.path.basename(rel))

        try:
            attr = sftp.stat(remote)
        except IOError as exc:
            if exc.errno in (errno.ENOENT, None):
                log(f"  missing   {rel}")
                missing += 1
                continue
            raise

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

    STALE = 30 * 60

    def __init__(self, path):
        self.path = path
        self.held = False

    def __enter__(self):
        try:
            if time.time() - os.path.getmtime(self.path) < self.STALE:
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
