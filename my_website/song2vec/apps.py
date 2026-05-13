import threading
from django.apps import AppConfig


class Song2VecConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'song2vec'

    def ready(self):
        # Pre-load all data in a background thread so the first request
        # doesn't block. The _load() call is thread-safe (uses a lock).
        from . import data as d
        t = threading.Thread(target=d._load, daemon=True)
        t.start()
