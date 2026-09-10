"""Ask the live map whether the server is up, and say exactly what happened.

    python manage.py probe_map
    python manage.py probe_map --timeout 15
    python manage.py probe_map --season season1

The online badge is the map's verdict and nothing else's, so when the badge is
wrong the question is always "what did the probe actually get?" - and until
this existed there was nowhere to ask it. probe_map swallows every exception by
design, the worker logs one word, and the answer lived in a variable in
whichever process happened to do the asking. A server that had been up for
hours read OFFLINE with nothing anywhere to say why.

This runs the same probe the worker runs, against the same URL, and prints the
reason rather than a word. Run it on the box that serves the site - the point
is what *that* machine can reach, which is not necessarily what your laptop
can.
"""

import os
import time

from django.core.management.base import BaseCommand

from minecraft import live, puller


class Command(BaseCommand):
    help = "Probe the live map and report what it said."

    def add_arguments(self, parser):
        parser.add_argument("--season", default=None,
                            help="season folder the stamps live in "
                                 "(default: the config's, else season1)")
        parser.add_argument("--timeout", type=float, default=puller.MAP_TIMEOUT,
                            help=f"seconds to wait (default {puller.MAP_TIMEOUT})")
        parser.add_argument("--no-stamp", action="store_true",
                            help="probe but leave the stamps alone")

    def handle(self, *args, **opts):
        season = opts["season"]
        if not season:
            try:
                cfg = __import__("minecraft.sync", fromlist=["sync"]).load_config(
                    puller.config_path())
                season = cfg.get("season") or "season1"
            except Exception:                    # noqa: BLE001 - a probe needs no config
                season = "season1"
        dest = puller.dest_for(season)

        self.stdout.write(f"url     {puller.MAP_URL}")
        self.stdout.write(f"stamps  {dest}")

        started = time.time()
        if opts["no_stamp"]:
            ok, why = puller._map_alive(opts["timeout"])
        else:
            ok = puller.probe_map(dest, timeout=opts["timeout"])
            why = puller.map_state().get("why", "")
        took = int((time.time() - started) * 1000)

        line = f"result  {'UP' if ok else 'DOWN'} - {why} ({took}ms)"
        self.stdout.write(self.style.SUCCESS(line) if ok
                          else self.style.ERROR(line))

        if not ok:
            self.stdout.write("")
            self.stdout.write("The badge will read OFFLINE while this fails. If the")
            self.stdout.write("map opens fine in a browser but this cannot reach it,")
            self.stdout.write("the host running the site is the thing being blocked -")
            self.stdout.write("outbound HTTP on a non-standard port is the usual one.")

        # what the board will make of it, which is the question behind the
        # question - the stamps are what it actually reads, not this run
        for name, stamp in (("last answer ", live.MAP_STAMP),
                            ("last attempt", live.MAP_TRY_STAMP)):
            path = os.path.join(dest, stamp)
            try:
                ago = int(time.time() - os.path.getmtime(path))
                self.stdout.write(f"{name}  {ago}s ago")
            except OSError:
                self.stdout.write(f"{name}  never")
