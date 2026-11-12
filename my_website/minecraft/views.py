import json
from functools import lru_cache
import os
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import redirect, render

from . import activity as activity_data
from . import history as history_data
from . import chat as chat_data
from . import live as live_data
from . import puller
from .roster import faces, season_roster

# STATICFILES_DIRS holds a relative path, which resolves against whatever the
# process happens to be started in. That is the project root under manage.py
# and something else entirely under a service manager, so the puller writes to
# one folder while a page reads another. Anchor both to BASE_DIR.
MINECRAFT_ROOT = os.path.join(puller.static_root(), 'minecraft')

# The season currently being played. It is not a disc: a disc is something you
# put back on the shelf, and this one is still being written. It gets the top
# of the screen and a feed that keeps itself up to date instead. Set this to
# None the day the season ends and it drops into the rail with the others.
LIVE_SEASON = 5

# The live world map: a BlueMap render the game host serves on a port of its
# own. It only ever draws the world being played, which is why it belongs in
# the live stage rather than on a disc: the finished seasons are gone off the
# server and there is nothing left of them to render. The fragment is a camera
# position, so the embed opens over the base instead of the middle of an ocean.
# The address itself lives in puller, which now asks the same map whether the
# server is up.
LIVE_MAP      = puller.MAP_URL
LIVE_MAP_VIEW = '#server_v3:189:0:87:1500:0:0:0:0:perspective'

# Edit season descriptions here
SEASON_DESCRIPTIONS = {
    1: "Groid Pack season 1 - The First Modpack",
    2: "Groid Pack season 2 - Spells and Dragons",
    3: "Groid Pack season 3 PART 1 - Guns and Factories",
    4: "Groid Pack Seven Seas - Pirates PvP",
    5: "Groid Pack OG Remastered - The first pack, rebuilt",
}

# Screenshot used as the backdrop behind each disc on the portal screen.
# Picked for legibility; falls back to a mid-list screenshot if missing.
SEASON_HEROES = {
    1: "2023-09-06_23.01.52.png",
    2: "2024-09-03_22.17.13.png",
    3: "2025-03-29_00.52.26.png",
    4: "2026-01-29_23.46.27.png",
}

SEASON_NAMES = {
    2: "SEASON 2 - Spells and Dragons",
    3: "SEASON 3 (PART 1)",
    4: "SEVEN SEAS",
    5: "OG REMASTERED",
}

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.webm', '.mov'}


def _stems(folder, exts):
    """{stem: filename} for every file in a folder with one of these extensions."""
    try:
        names = os.listdir(folder)
    except OSError:
        return {}
    return {os.path.splitext(n)[0]: n for n in names
            if os.path.splitext(n)[1].lower() in exts}


def _shot_date(stem):
    try:
        return datetime.strptime(stem, "%Y-%m-%d_%H.%M.%S")
    except ValueError:
        return datetime.min


@lru_cache(maxsize=None)
def _season_media(season_path, url_prefix, _stamp):
    """A season's logo, screenshots and clips, read off disk once per change.

    The gallery is built from the web-sized copies under _web/, not from the
    original screenshots: the originals are gitignored (1.3 GB of them), so a
    deployed checkout has none, and listing them is how every gallery came up
    empty. An original is only used where no web copy of it exists. sizes.json
    gives each tile its height before the lazy-loaded image lands.
    """
    web = os.path.join(season_path, '_web')
    try:
        with open(os.path.join(web, 'sizes.json')) as fh:
            sizes = json.load(fh)
    except (OSError, ValueError):
        sizes = {}

    files = _stems(season_path, IMAGE_EXTS | VIDEO_EXTS)
    # WebP first: season 4's logo is 39 frames and the GIF of it is two megabytes
    logo = next((f for f in ('logo.webp', 'logo.png', 'logo.jpg', 'logo.gif')
                 if os.path.isfile(os.path.join(season_path, f))), None)
    files.pop('logo', None)
    originals = {k: v for k, v in files.items()
                 if os.path.splitext(v)[1].lower() in IMAGE_EXTS}
    thumbs = _stems(os.path.join(web, 'thumb'), {'.webp'})
    views  = _stems(os.path.join(web, 'view'), {'.webp'})

    screenshots = []
    for stem in sorted(set(originals) | set(thumbs) | set(views),
                       key=lambda k: (_shot_date(k), k)):
        thumb = f'{url_prefix}/_web/thumb/{thumbs[stem]}' if stem in thumbs else None
        view  = f'{url_prefix}/_web/view/{views[stem]}' if stem in views else None
        url   = f'{url_prefix}/{originals[stem]}' if stem in originals else None
        w, h  = (list(sizes.get(stem) or ()) + [0, 0])[:2]
        screenshots.append({
            'stem':  stem,
            'url':   url or view or thumb,
            'thumb': thumb or view or url,
            'view':  view or url or thumb,
            'w': w, 'h': h,
            'label': stem,
        })
    videos = [{'url': f'{url_prefix}/{name}', 'label': name}
              for name in sorted(files.values())
              if os.path.splitext(name)[1].lower() in VIDEO_EXTS]
    return logo, screenshots, videos


def _season_dirs():
    """(number, folder) for every seasonN directory, in season order."""
    try:
        names = os.listdir(MINECRAFT_ROOT)
    except OSError:
        return []
    return sorted(
        (int(d[6:]), d) for d in names
        if d.startswith('season') and d[6:].isdigit()
        and os.path.isdir(os.path.join(MINECRAFT_ROOT, d)))


def _media(season_dir):
    season_path = os.path.join(MINECRAFT_ROOT, season_dir)
    # the folders' mtimes change when a file is added or removed, which is
    # exactly when the cached listing goes stale
    stamp = tuple(_mtime(os.path.join(season_path, *sub))
                  for sub in ((), ('_web', 'thumb'), ('_web', 'view'), ('_web', 'sizes.json')))
    return _season_media(season_path, f'/static/minecraft/{season_dir}', stamp)


def _hero(season_num, screenshots, kind='view'):
    """The screenshot that stands for a season: the picked one, else a mid-list one."""
    stem = os.path.splitext(SEASON_HEROES.get(season_num, ''))[0]
    shot = next((x for x in screenshots if x['stem'] == stem), None)
    if shot is None and screenshots:
        shot = screenshots[len(screenshots) // 2]
    return shot[kind] if shot else None


def summary():
    """The portal in four numbers and a few thumbnails, for the codec's panel.

    Counted off disk so the home page cannot drift from the gallery it links to.
    """
    seasons = _season_dirs()
    shots = clips = 0
    thumbs, years = [], []
    for num, folder in seasons:
        _, screenshots, videos = _media(folder)
        shots += len(screenshots)
        clips += len(videos)
        years += [d.year for d in (_shot_date(x['stem']) for x in screenshots) if d.year > 1]
        if screenshots:
            thumbs.append({'s': num, 'url': _hero(num, screenshots, 'thumb')})
    span = f'{min(years)}-{max(years) % 100:02d}' if years else ''
    return {'seasons': len(seasons), 'shots': shots, 'clips': clips, 'span': span,
            'thumbs': thumbs, 'map': LIVE_MAP + LIVE_MAP_VIEW if LIVE_MAP else ''}


def portal(request):
    seasons = []
    live = None

    for season_num, season_dir in _season_dirs():
        logo_file, screenshots, videos = _media(season_dir)
        roster = season_roster(os.path.join(MINECRAFT_ROOT, season_dir))
        # a background image the size of the header, never the original
        hero = _hero(season_num, screenshots)

        entry = {
            'number':           season_num,
            'name':             SEASON_NAMES.get(season_num, f'SEASON {season_num}'),
            'description':      SEASON_DESCRIPTIONS.get(season_num, f'Season {season_num}.'),
            'has_logo':         logo_file is not None,
            'logo_file':        logo_file,
            'screenshots':      screenshots,
            'videos':           videos,
            'hero':             hero,
            'roster':           roster,
            'roster_json':      json.dumps(roster),
        }

        if season_num == LIVE_SEASON:
            live = entry
        else:
            seasons.append(entry)

    # the first paint carries a board of its own, so the stage is never an
    # empty box waiting on a fetch to say anything
    board = _board(f'season{LIVE_SEASON}') if live else None
    if board:
        board.update({'live': True, 'season': LIVE_SEASON,
                      'source': puller.state()})

    return render(request, 'minecraft.html', {
        'seasons': seasons,
        'live': live,
        'live_json': json.dumps(board) if board else 'null',
        'map_url':  LIVE_MAP + LIVE_MAP_VIEW if live and LIVE_MAP else None,
        'map_home': LIVE_MAP,
        'forge_stamp': _stamp_for('data.json'),
        'ench_stamp': _stamp_for('enchanting.json'),
    })


def _stamp_for(filename):
    """The mtime of one of the apotheosis data files, as a cache buster.

    These are fetched by script rather than named in the markup, so they never
    pick up the stamp every other asset on the page carries. They are static
    files that want caching hard, and a re-extract served out of a browser
    cache holding the old one is how a changed reforging cost silently does
    not change - so each goes out stamped with its own mtime, which caches
    until the extractor next runs and no longer.
    """
    return _mtime(os.path.join(MINECRAFT_ROOT, 'apotheosis', filename))


def _mtime(path):
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0


def _live_data(feed):
    """A view over the live season's data folder, or a 404 with no season."""
    def view(request):
        if not LIVE_SEASON:
            return JsonResponse({'live': False}, status=404)
        return JsonResponse(feed(
            os.path.join(MINECRAFT_ROOT, f'season{LIVE_SEASON}', 'data')))
    return view


def _board(key):
    """The live board with a face on every row, or None if nothing is synced."""
    path  = os.path.join(MINECRAFT_ROOT, key)
    board = live_data.board(path)
    if board is None:
        return None
    known = faces()
    for player in board['players']:
        player.update(known.get(player['uuid'], {'skin': None, 'slim': False}))
    # a boss's killers are drawn with their own faces too, and so is whoever
    # was in on a kill without leading it - a helper is a player like any
    # other and was showing up as an empty square for being left out here
    for boss in board.get('bosses', []):
        for who in boss['killers'] + boss.get('helpers', []):
            who.update(known.get(who['uuid'], {'skin': None, 'tone': None}))
    # and so is whoever landed each legendary fish
    for catch in board.get('fish', []):
        for angler in catch['anglers']:
            angler.update(known.get(angler['uuid'], {'skin': None}))
    return board


def live_board(request):
    """The live season's numbers, as fresh as the server will give them.

    Asking for the board asks for a pull, which happens on a background thread
    and is throttled: the response is always whatever is on disk right now, so
    the page never waits on the network to draw itself.
    """
    if not LIVE_SEASON:
        return JsonResponse({'live': False}, status=404)

    key   = f'season{LIVE_SEASON}'
    # the PULL NOW button skips the throttle; the polling loop does not
    pull  = puller.refresh(key, force=request.GET.get('force') == '1')
    board = _board(key)

    if board is None:
        return JsonResponse({'live': True, 'players': [], 'source': pull,
                             'map_probe': puller.map_state()})

    board['live']   = True
    board['season'] = LIVE_SEASON
    board['source'] = pull
    # What the last look at the live map actually did, carried so a probe that
    # is failing on the deployed box can be seen rather than guessed at. The
    # badge is the map's verdict now, so "why is it OFFLINE" and "what did the
    # probe say" have to be the same question - they were not, and a server
    # that had been up for hours read OFFLINE with nothing anywhere to say why.
    board['map_probe'] = puller.map_state()
    return JsonResponse(board)


def chat_feed(request):
    """The server's chat, from the archive rather than from the server.

    The buffer on the game host holds ten messages and this endpoint is polled
    by every open tab, so the two are deliberately not connected: a poll reads
    a local file, and a separate clock decides when that file is refilled. A
    hundred tabs and one tab cost the game host exactly the same.

    `since` is the sequence number the caller last saw. Without it the box gets
    a window of backlog to open with; with it, only what has been said since,
    which on a quiet server is an empty list.
    """
    if not LIVE_SEASON:
        return JsonResponse({'live': False}, status=404)

    key = f'season{LIVE_SEASON}'
    # asks for a pull, never waits for one - same bargain as the board
    source = puller.refresh_chat(key)

    try:
        since = int(request.GET['since'])
    except (KeyError, ValueError):
        since = None

    feed = chat_data.board(os.path.join(MINECRAFT_ROOT, key, 'data'), since)
    feed['source'] = source
    return JsonResponse(feed)


# When the server gets played, hour by hour. Its own endpoint rather than part
# of the board: the board is polled every minute and this changes on the sync's
# clock, not the page's, so it is fetched once when the section is opened. The
# hour buckets go out in UTC - rolling them into a day-of-week grid means
# picking a timezone, and the only one worth picking belongs to the reader.
activity_feed = _live_data(activity_data.board)

# What each player's own numbers have been doing, day by day. Its own endpoint
# for the same reason, and because it is bigger: a row per player per day plus
# an hourly gauge series is not something to put on a one-minute poll.
history_feed = _live_data(history_data.board)


def skill_tree(request):
    """The tree itself, redirected to a URL that carries its own mtime.

    It is a static file and a big one, so it wants caching hard - but a
    re-extracted tree served from a browser cache holding the old one is how
    a new field silently does not exist. The same stamp trick every model and
    icon on this page already uses, applied to the one file that is fetched
    by script rather than named in the markup.
    """
    stamp = _mtime(os.path.join(MINECRAFT_ROOT, 'skilltree', 'tree.json'))
    return redirect(f'/static/minecraft/skilltree/tree.json?v={stamp}')


def guide(request):
    """The modpack's own mechanics, for whoever just joined the live season.

    A static page rather than anything read off the server: what a mod's
    config says a system does does not change between restarts the way a
    player's own numbers do, so there is nothing here worth polling for.
    """
    return render(request, 'minecraft_guide.html', {'season': LIVE_SEASON})
