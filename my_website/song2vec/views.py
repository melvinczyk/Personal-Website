import io
import base64
from functools import lru_cache
from itertools import islice

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .paths import available

# The corpus lives outside the repo. A checkout without it answers plainly
# instead of raising FileNotFoundError out of every keystroke in the search box.
NO_DATA = {'error': 'The Song2Vec dataset is not installed on this server.', 'results': []}


def index(request):
    return render(request, 'song2vec.html')


@require_GET
def search(request):
    """
    GET /song2vec/search/?q=bohemian
    Returns up to 10 matching songs from the dataset.
    """
    from . import data as d  # lazy: keeps heavy numerical imports off the boot path

    q = request.GET.get('q', '').strip().lower()
    if len(q) < 2:
        return JsonResponse({'results': []})
    if not available():
        return JsonResponse(NO_DATA, status=503)

    d._load()

    hits = islice((sid for name, artist, sid in d.SONG_INDEX if q in name or q in artist), 10)
    return JsonResponse({'results': [
        {'id': sid, 'name': d.SONGS[sid]['name'], 'artist': d.SONGS[sid]['artist']} for sid in hits]})


@lru_cache(maxsize=256)
def _blob_png(sid):
    """A song's blob as base64 PNG. Drawing one is the slow part of a render and
    the same song always draws the same blob, so the popular ones are kept."""
    from . import data as d
    song = d.SONGS[sid]
    buf = io.BytesIO()
    d.render_blob(sorted(song['genres']), song['tags'], size=400).save(buf, format='PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode('ascii')


@require_GET
def render_song(request):
    """
    GET /song2vec/render/?id=<spotify_id>
    Returns JSON with genres, tags, and a base64-encoded PNG blob image.
    """
    from . import data as d  # lazy: keeps heavy numerical imports off the boot path

    sid = request.GET.get('id', '').strip()
    if not available():
        return JsonResponse(NO_DATA, status=503)
    d._load()
    if not sid or sid not in d.SONGS:
        return JsonResponse({'error': 'Song not found'}, status=404)
    song = d.SONGS[sid]

    return JsonResponse({
        'name':   song['name'],
        'artist': song['artist'],
        'genres': sorted(song['genres']),
        'tags':   [t for t, _ in song['tags']],   # (tag, popularity) pairs
        'image':  _blob_png(sid),
    })
