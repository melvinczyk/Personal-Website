"""Pull the Minecraft server's exported JSON into the site's static folder.

    python manage.py sync_server                    # normal run, for cron
    python manage.py sync_server --dry-run          # say what would be fetched
    python manage.py sync_server --explore          # walk the remote tree
    python manage.py sync_server --config /path/to/config.json

Credentials come from the config file, never from the command line, so they do
not end up in shell history or a process list.
"""

import os
import posixpath
import stat as statmod

from django.core.management.base import BaseCommand, CommandError

from minecraft import puller, sync

DEFAULT_CONFIG = puller.DEFAULT_CONFIG     # relative to BASE_DIR


class Command(BaseCommand):
    help = "Pull the Minecraft server's exported JSON over SFTP."

    def add_arguments(self, parser):
        parser.add_argument("--config", default=None,
                            help=f"config file (default: BASE_DIR/{DEFAULT_CONFIG}, "
                                 f"or $MC_SYNC_CONFIG)")
        parser.add_argument("--season", default=None,
                            help="season folder to fill (default: config's season, "
                                 "else season5)")
        parser.add_argument("--dry-run", action="store_true",
                            help="list what would be fetched, download nothing")
        parser.add_argument("--explore", action="store_true",
                            help="print the remote tree and stop")
        parser.add_argument("--depth", type=int, default=2)

    def handle(self, *args, **opts):
        path = opts["config"] or puller.config_path()

        try:
            cfg = sync.load_config(path)
        except sync.SyncError as exc:
            raise CommandError(str(exc))

        season = opts["season"] or cfg.get("season") or "season5"
        # the same paths the live portal pulls to, so a scheduled run and a
        # page-driven one can never disagree about where the data lives
        dest = puller.dest_for(season)
        lock = sync.Lock(puller.lock_for(season))
        with lock:
            if not lock.held:
                self.stdout.write("another sync is already running; skipping")
                return

            self.stdout.write(f"connecting to {cfg['user']}@{cfg['host']}:{cfg['port']}")
            try:
                client, sftp = sync.connect(cfg)
            except sync.SyncError as exc:
                raise CommandError(str(exc))

            try:
                if opts["explore"]:
                    self._explore(sftp, cfg["remote_root"], opts["depth"])
                    return

                self.stdout.write(f"season {season} -> {dest}")
                got, same, missing, skipped = sync.fetch(
                    sftp, cfg, dest,
                    dry_run=opts["dry_run"],
                    log=self.stdout.write,
                )
            finally:
                sftp.close()
                client.close()

        clean = True
        if not opts["dry_run"]:
            clean = sync.verify(dest, cfg, log=self.stdout.write)

        summary = f"{got} fetched, {same} unchanged, {missing} missing"
        if skipped:
            summary += f", {skipped} skipped"
        if not clean:
            # A file that does not parse is a failure worth a non-zero exit,
            # or a scheduled run reports success while serving garbage.
            raise CommandError(summary + " — a fetched file is not valid JSON")
        if missing or skipped:
            # Missing is not necessarily an error: players.json only appears
            # once the snapshot script has run with somebody online.
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def _explore(self, sftp, root, depth):
        interesting = {"kubejs", "exported", "world", "playerdata", "stats", "logs"}

        def walk(path, level):
            try:
                entries = sorted(sftp.listdir_attr(path), key=lambda e: e.filename)
            except IOError:
                self.stdout.write(f"{'  ' * level}{path}  (unreadable)")
                return
            for e in entries:
                if statmod.S_ISDIR(e.st_mode or 0):
                    self.stdout.write(f"{'  ' * level}{e.filename}/")
                    if level < depth and e.filename in interesting:
                        walk(posixpath.join(path, e.filename), level + 1)
                else:
                    self.stdout.write(f"{'  ' * level}{e.filename}  ({e.st_size} B)")

        self.stdout.write(f"{root}/")
        walk(root, 1)
