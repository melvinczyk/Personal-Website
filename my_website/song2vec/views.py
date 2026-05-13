import io
import base64

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import data as d


def index(request):
    return render(request, 'song2vec.html')


@require_GET
def search(request):
    """
    GET /song2vec/search/?q=bohemian
    Returns up to 10 matching songs from the dataset.
    """
    q = request.GET.get('q', '').strip().lower()
    if len(q) < 2:
        return JsonResponse({'results': []})

    d._load()

    results = []
    for name_lower, artist_lower, sid in d.SONG_INDEX:
        if q in name_lower or q in artist_lower:
            s = d.SONGS[sid]
            results.append({
                'id':     sid,
                'name':   s['name'],
                'artist': s['artist'],
            })
            if len(results) == 10:
                break

    return JsonResponse({'results': results})


@require_GET
def render_song(request):
    """
    GET /song2vec/render/?id=<spotify_id>
    Returns JSON with genres, tags, and a base64-encoded PNG blob image.
    """
    sid = request.GET.get('id', '').strip()
    if not sid or sid not in d.SONGS:
        return JsonResponse({'error': 'Song not found'}, status=404)

    d._load()
    song = d.SONGS[sid]

    genres = sorted(song['genres'])
    tags   = song['tags']   # list of (tag, popularity)

    img = d.render_blob(genres, tags, size=400)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('ascii')

    return JsonResponse({
        'name':   song['name'],
        'artist': song['artist'],
        'genres': genres,
        'tags':   [t for t, _ in tags],
        'image':  img_b64,
    })
