"""Pull the Minecraft server's exported JSON into the site's static folder.

    python manage.py sync_server                    # one run, for cron
    python manage.py sync_server --loop             # keep running, for a worker
    python manage.py sync_server --dry-run          # say what would be fetched
    python manage.py sync_server --explore          # walk the remote tree
    python manage.py sync_server --config /path/to/config.json

--loop is for a host that will keep one process alive and only one:
PythonAnywhere gives a free account a single always-on task, and this is it.
It runs the two pulls this site needs on their own clocks, in one process:

  * the chat buffer, every twenty-five seconds, because the game host keeps
    only fifteen messages and drops the rest - whatever is not read before the
    sixteenth arrives is gone for good. See chat.py.
  * everything else, every two minutes. It used to be every quarter of an
    hour, which for "who is online" is most of a session out of date.

Raising that rate is close to free, which is the reason it could be raised. A
full pull only ever runs on a tick that has already connected for chat, so it
adds no handshake at all - it costs one directory listing and whichever files
have actually changed, which in practice is world_data.json and nothing else.
The floor is sixty seconds; below that the listing starts to be most of what
the host is being asked for.

Nothing else is shared between the two: a chat pull that fails does not stop
the counters being fetched, or the other way about.

Credentials come from the config file, never from the command line, so they do
not end up in shell history or a process list.
"""

import os
import posixpath
import signal
import stat as statmod
import time

from django.core.management.base import BaseCommand, CommandError

from minecraft import activity, chat, puller, sync

# What a failing host is asked at instead: doubling from whichever interval
# was due, up to this. A server down for the night is asked twice a minute for
# a moment and twice an hour thereafter.
BACKOFF_CAP = 15 * 60

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
        parser.add_argument("--loop", action="store_true",
                            help="keep pulling until stopped: chat on its own "
                                 "short clock, everything else on the long one")
        parser.add_argument("--interval", type=float, default=puller.FULL_INTERVAL,
                            help=f"seconds between full pulls under --loop "
                                 f"(default {puller.FULL_INTERVAL}, floor 60)")
        parser.add_argument("--chat-interval", type=float,
                            default=puller.CHAT_INTERVAL,
                            help=f"seconds between chat pulls under --loop "
                                 f"(default {puller.CHAT_INTERVAL})")
        parser.add_argument("--no-chat", action="store_true",
                            help="leave the chat buffer alone")

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

        if opts["loop"]:
            if opts["explore"] or opts["dry_run"]:
                raise CommandError("--loop is for running, not for looking: "
                                   "drop --explore/--dry-run")
            return self._watch(cfg, season, dest, opts)

        self.stdout.write(f"connecting to {cfg['user']}@{cfg['host']}:{cfg['port']}")
        try:
            client, sftp = sync.connect(cfg)
        except sync.SyncError as exc:
            raise CommandError(str(exc))

        try:
            if opts["explore"]:
                self._explore(sftp, cfg["remote_root"], opts["depth"])
                return

            # Chat first, and outside the lock.
            #
            # Outside because it writes one file nothing else touches, so a
            # run that finds another sync holding the lock can still bring the
            # chat back rather than returning with nothing.
            #
            # At all, because this path did not used to. Chat was only pulled
            # under --loop, and a host that gives you one always-on task and
            # runs this command from a wrapper every few minutes therefore
            # never pulled chat at all - the five data files moved and the
            # archive sat still. Whichever way this command is invoked, it now
            # grabs the buffer.
            if not opts["no_chat"] and not opts["dry_run"]:
                try:
                    added, _changed = chat.pull(sftp, cfg, dest)
                    self.stdout.write(f"  chat      {added} new" if added
                                      else "  chat      nothing new")
                except Exception as exc:     # noqa: BLE001
                    # the counters are the point of this command; a chat
                    # buffer that would not come back is worth a line, not a
                    # failed run
                    self.stdout.write(self.style.WARNING(
                        f"  chat      {type(exc).__name__}: {exc}"))

            lock = sync.Lock(puller.lock_for(season))
            with lock:
                if not lock.held:
                    self.stdout.write("another sync is already running; skipping")
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
            # Ask the live map whether there is a server behind it. It answers
            # for the server itself where the export answers only for the mod
            # writing it, and those two came apart once already - see
            # puller.probe_map and live._server_up.
            self.stdout.write(f"  map       "
                              f"{'answered' if puller.probe_map(dest) else 'no answer'}")
            # what was played since the last sample, banked before anything
            # else can overwrite the counters we measured against
            seen, banked = activity.sample(dest)
            if banked:
                self.stdout.write(
                    f"  activity  {banked / 3600:.1f} player-hours "
                    f"across {seen} players")

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

    # ── the always-on worker ─────────────────────────────────────────────

    def _watch(self, cfg, season, dest, opts):
        """Both pulls, on their own clocks, in one process.

        Written this way because a host may give you exactly one always-on
        task. Two clocks rather than two processes, and two clocks rather than
        one: chat every twenty-five seconds keeps the buffer from rolling over
        unread, while doing the five-file fetch that often would hammer a game
        panel's SFTP gateway for counters nobody reads to the second.
        """
        chat_every = max(5.0, opts["chat_interval"])
        # a floor rather than a clamp both ends: somebody who asks for an
        # hourly full pull has a reason, and somebody who asks for one every
        # ten seconds has made a mistake the game host would pay for
        full_every = max(60.0, opts["interval"])
        with_chat = not opts["no_chat"]

        # a worker is stopped by being signalled, and what it is most likely to
        # be doing at that moment is sleeping between ticks: catch it so the
        # loop ends on the next tick rather than dying inside a read and
        # leaving a half-written file or a held lock behind
        self.stopping = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._stop)

        self._log(f"watching {season}: chat every {chat_every:g}s, "
                  f"everything else every {full_every:g}s"
                  + ("" if with_chat else " (chat off)"))

        # the long clock starts due, so a worker that has just been restarted
        # brings the counters up to date rather than waiting a quarter of an
        # hour to do the thing it was restarted for
        next_full = 0.0
        fails = 0
        # What chat has done since the last time the log said anything about
        # it. Only a new message was ever printed, so a chat pull that ran two
        # hundred times and found nothing looked exactly like one that was
        # never running at all - which is precisely the question somebody
        # reading an always-on task's log is trying to answer.
        chat_new = chat_looks = 0
        while not self.stopping:
            started = time.monotonic()
            due_full = started >= next_full
            try:
                client, sftp = sync.connect(cfg)
                try:
                    if with_chat:
                        added, _changed = chat.pull(sftp, cfg, dest)
                        chat_looks += 1
                        chat_new += added
                        if added:
                            self._log(f"  chat      {added} new")
                    # Only a pull that actually happened moves the long
                    # clock on. The lock can be held by a hand-run sync or by
                    # the page's own puller, and treating that skip as a run
                    # would cost the counters a whole interval for a
                    # collision that is over in seconds.
                    # said on the full pull's clock rather than chat's own:
                    # once every couple of minutes is enough to show the poll
                    # is alive, where a line every twenty-five seconds would
                    # be the only thing in the log
                    if due_full and with_chat and not chat_new:
                        self._log(f"  chat      quiet, {chat_looks} look"
                                  f"{'' if chat_looks == 1 else 's'}")
                    if due_full:
                        chat_new = chat_looks = 0
                    if due_full and self._full(sftp, cfg, season, dest):
                        # measured from the end of the pull rather than the
                        # start, so a slow fetch does not shorten the wait
                        # after it and creep towards running back to back
                        next_full = time.monotonic() + full_every
                finally:
                    sftp.close()
                    client.close()
                fails = 0
            except Exception as exc:         # noqa: BLE001 - a worker never dies
                fails += 1
                self._log(f"  {type(exc).__name__}: {exc}", err=True)

            base = chat_every if with_chat else full_every
            wait = (min(base * 2 ** fails, BACKOFF_CAP) if fails
                    else base - (time.monotonic() - started))
            # sliced, so a stop signal is noticed within the second rather than
            # after however long the backoff had grown to
            while wait > 0 and not self.stopping:
                time.sleep(min(1.0, wait))
                wait -= 1.0
        self._log("stopped")

    def _stop(self, _signum, _frame):
        self.stopping = True

    # A worker's log is the only window onto it, and Python buffers hard when
    # stdout is a file rather than a terminal - which under an always-on task
    # it always is. Left alone, an hour of work can sit in the buffer and the
    # log reads as a process that never started. Every line goes out as it
    # happens instead.
    def _log(self, line, err=False):
        stream = self.stderr if err else self.stdout
        stream.write(line)
        try:
            stream.flush()
        except (AttributeError, ValueError):
            pass                             # a closed or odd stream is not a fault

    def _full(self, sftp, cfg, season, dest):
        """The five-file pull, on a connection somebody else opened.

        Returns whether it ran, so the caller can tell a pull that happened
        from one that stood aside for somebody else's.

        Under the season lock, exactly as the one-shot run is: the lock is
        what stops this and a hand-run `sync_server` writing the same folder
        at once. Chat is deliberately outside it - it writes one file nothing
        else touches, and queueing a twenty-five second poll behind the
        slower fetch would stall the box for no benefit.
        """
        lock = sync.Lock(puller.lock_for(season))
        with lock:
            if not lock.held:
                self._log("  another sync holds the lock; skipping")
                return False
            got, same, missing, skipped = sync.fetch(
                sftp, cfg, dest, log=lambda line: None)

        line = f"  data      {got} fetched, {same} unchanged"
        if missing:
            line += f", {missing} missing"
        if skipped:
            line += f", {skipped} skipped"
        self._log(line)

        # A file that does not parse is worth saying out loud, but never worth
        # taking the worker down for: the next pull replaces it, and the chat
        # poll in between has nothing to do with it.
        if not sync.verify(dest, cfg, log=self.stdout.write):
            self._log("  a fetched file is not valid JSON", err=True)
        seen, banked = activity.sample(dest)
        if banked:
            self._log(f"  activity  {banked / 3600:.1f} player-hours "
                      f"across {seen} players")
        return True

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
