import logging
import os
import threading

from django.apps import AppConfig

log = logging.getLogger(__name__)


class Song2VecConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'song2vec'

    def ready(self):
        # Pre-load all data shortly after startup so the first request
        # doesn't block. The heavy import lives inside the thread, and the
        # delay keeps it from racing Django's own startup imports (the
        # numerical libs can deadlock if two threads import them at once).
        # _load() is thread-safe (uses a lock).
        #
        # ready() runs for every process Django starts, management commands
        # included, so this thread was firing inside the sync worker too - a
        # process that will never serve a song2vec request. On a host without
        # the corpus it died there every startup and printed a traceback into
        # the sync log, which is how it was found.
        if not self._corpus_here():
            log.info("song2vec: no corpus at %s, skipping preload",
                     os.environ.get('SONG2VEC_DATA') or 'the default path')
            return

        def _preload():
            # A preload is an optimisation. Nothing it can hit is worth a
            # traceback in the log of whatever process happened to start it,
            # and nothing it can hit should stop that process working: the
            # first request pays the load instead, and reports its own faults.
            try:
                from . import data as d
                d._load()
            except Exception as exc:         # noqa: BLE001 - never a fault here
                log.warning("song2vec preload skipped: %s: %s",
                            type(exc).__name__, exc)

        t = threading.Timer(6.0, _preload)
        t.daemon = True
        t.start()

    @staticmethod
    def _corpus_here():
        """Asked without importing data.py, which drags numpy in behind it."""
        from .paths import available
        return available()
