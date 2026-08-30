"""Pull the server's chat buffer into the season's archive.

    python manage.py sync_chat                  # one look, for cron
    python manage.py sync_chat --loop           # keep looking, for a worker
    python manage.py sync_chat --loop --interval 20

Separate from sync_server on purpose. That one moves five files holding every
number on the page and runs a few times an hour; this one stats a file of a few
hundred bytes and reads it only when it has moved, which is cheap enough to run
every twenty seconds. Chat that is a quarter of an hour old is not chat.

The urgency is not only about feeling live. The server's buffer holds ten
messages and drops the rest, so whatever is not read before the eleventh
message arrives is gone - see chat.py. The interval is a retention policy
wearing a different hat.

--loop is what to run where a host will keep a process alive: PythonAnywhere's
always-on tasks, a systemd unit, a supervisor program. It reconnects on its own
and backs off when the host stops answering, so it is meant to be started once
and left. Where only a scheduler is available, run it without --loop as often
as that scheduler allows and accept that the archive keeps whatever survived
between runs.

Credentials come from the config file, never the command line.
"""

import signal
import time

from django.core.management.base import BaseCommand, CommandError

from minecraft import chat, puller, sync

# What a failing host is asked at instead. Doubling from the poll interval up
# to this, so a server that has gone down for the night is asked twice a minute
# for a moment and twice an hour thereafter.
BACKOFF_CAP = 15 * 60


class Command(BaseCommand):
    help = "Pull the Minecraft server's chat buffer into the local archive."

    def add_arguments(self, parser):
        parser.add_argument("--config", default=None)
        parser.add_argument("--season", default=None)
        parser.add_argument("--loop", action="store_true",
                            help="keep polling until stopped (for an always-on "
                                 "worker rather than a scheduler)")
        parser.add_argument("--interval", type=float, default=puller.CHAT_INTERVAL,
                            help=f"seconds between polls under --loop "
                                 f"(default {puller.CHAT_INTERVAL})")
        parser.add_argument("--quiet", action="store_true",
                            help="say nothing unless something arrived or broke")

    def handle(self, *args, **opts):
        path = opts["config"] or puller.config_path()
        try:
            cfg = sync.load_config(path)
        except sync.SyncError as exc:
            raise CommandError(str(exc))

        season = opts["season"] or cfg.get("season") or "season5"
        dest = puller.dest_for(season)
        self.quiet = opts["quiet"]

        if not opts["loop"]:
            added, changed = self._once(cfg, dest)
            self._say(f"{added} new, {'changed' if changed else 'unchanged'}",
                      loud=bool(added))
            return

        # a worker is stopped by being signalled, and the thing it is most
        # likely to be doing when that happens is sleeping between polls: catch
        # it so the loop ends on the next tick rather than dying inside a read
        # and leaving a half-written archive behind
        self.stopping = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._stop)

        interval = max(5.0, opts["interval"])
        self.stdout.write(f"watching chat for {season} every {interval:g}s")
        fails = 0
        while not self.stopping:
            start = time.monotonic()
            try:
                added, _changed = self._once(cfg, dest)
                if added:
                    self._say(f"{added} new", loud=True)
                fails = 0
            except Exception as exc:         # noqa: BLE001 - a worker never dies
                fails += 1
                self.stderr.write(f"  {type(exc).__name__}: {exc}")
            wait = (min(interval * 2 ** fails, BACKOFF_CAP) if fails
                    else interval - (time.monotonic() - start))
            # sliced so a stop signal is noticed within a second rather than
            # after however long the backoff had grown to
            while wait > 0 and not self.stopping:
                time.sleep(min(1.0, wait))
                wait -= 1.0
        self.stdout.write("stopped")

    def _stop(self, _signum, _frame):
        self.stopping = True

    def _once(self, cfg, dest):
        """Connect, look, disconnect.

        A held-open session would save the handshake, but a game panel's SFTP
        gateway is not a fileserver and an idle session it decides to drop
        fails on the next read rather than on connect, which is the harder
        failure to recover from. The handshake is the price of not having to
        care.
        """
        client, sftp = sync.connect(cfg)
        try:
            return chat.pull(sftp, cfg, dest)
        finally:
            sftp.close()
            client.close()

    def _say(self, line, loud=False):
        if loud or not self.quiet:
            self.stdout.write(f"  {line}")
