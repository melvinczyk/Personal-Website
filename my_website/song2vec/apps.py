import threading
from django.apps import AppConfig


class Song2VecConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'song2vec'

    def ready(self):
        # Pre-load all data shortly after startup so the first request
        # doesn't block. The heavy import lives inside the thread, and the
        # delay keeps it from racing Django's own startup imports (the
        # numerical libs can deadlock if two threads import them at once).
        # _load() is thread-safe (uses a lock).
        def _preload():
            from . import data as d
            d._load()
        t = threading.Timer(6.0, _preload)
        t.daemon = True
        t.start()
