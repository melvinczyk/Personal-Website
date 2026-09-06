import json
from functools import lru_cache
import os
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.conf import settings

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


def _derivative(season_path, url_prefix, kind, stem):
    """The URL of a web-sized copy, if tools/web_images.py has built one."""
    name = f'{stem}.webp'
    if os.path.isfile(os.path.join(season_path, '_web', kind, name)):
        return f'{url_prefix}/_web/{kind}/{name}'
    return None


@lru_cache(maxsize=None)
def _thumb_sizes(season_path):
    """Every thumbnail's width and height, from the table beside them.

    The gallery has to know these before the images arrive. Its tiles are
    lazy-loaded into a column layout, and an image with no declared size
    gives its tile no height - so the column collapses, nothing is ever near
    enough to the viewport to trigger a load, and the gallery stays empty for
    good. Read once per season rather than stat-ing six hundred files.
    """
    try:
        with open(os.path.join(season_path, '_web', 'sizes.json')) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def parse_screenshot_date(filename):
    name = os.path.splitext(filename)[0]
    try:
        return datetime.strptime(name, "%Y-%m-%d_%H.%M.%S")
    except ValueError:
        return datetime.min


def portal(request):
    minecraft_root = MINECRAFT_ROOT

    seasons = []

    if not os.path.isdir(minecraft_root):
        return render(request, 'minecraft.html', {'seasons': seasons})

    season_dirs = sorted(
        [d for d in os.listdir(minecraft_root)
         if d.startswith('season') and os.path.isdir(os.path.join(minecraft_root, d))],
        key=lambda d: int(''.join(filter(str.isdigit, d)) or '0')
    )

    live = None

    for season_dir in season_dirs:
        digits = ''.join(filter(str.isdigit, season_dir))
        if not digits:
            continue
        season_num  = int(digits)
        season_path = os.path.join(minecraft_root, season_dir)
        url_prefix  = f'/static/minecraft/{season_dir}'

        logo_file = next(
            # WebP first: season 4's logo is 39 frames of animation and the
            # GIF of it is two megabytes, against six hundred kilobytes for
            # the same thing at the size it is actually drawn
            (f for f in ('logo.webp', 'logo.png', 'logo.jpg', 'logo.gif')
             if os.path.isfile(os.path.join(season_path, f))),
            None
        )
        has_logo  = logo_file is not None
        screenshots = []
        videos      = []

        for filename in os.listdir(season_path):
            if filename in ('logo.png',):
                continue
            ext = os.path.splitext(filename)[1].lower()
            url = f'{url_prefix}/{filename}'

            if ext in IMAGE_EXTS:
                # A web-sized copy where tools/web_images.py has made one, and
                # the original where it has not. The originals are Minecraft
                # screenshots straight off disk - some are thirteen megabytes -
                # and putting one of those behind the header was most of what
                # the page weighed.
                stem = os.path.splitext(filename)[0]
                small = _derivative(season_path, url_prefix, 'thumb', stem)
                big = _derivative(season_path, url_prefix, 'view', stem)
                w, h = (_thumb_sizes(season_path).get(stem) or (0, 0))[:2] or (0, 0)
                screenshots.append({
                    'filename': filename,
                    'url':      url,
                    'thumb':    small or big or url,
                    'view':     big or url,
                    # so a tile has a height before its image lands
                    'w':        w,
                    'h':        h,
                    'label':    filename,
                    'date':     parse_screenshot_date(filename),
                })
            elif ext in VIDEO_EXTS:
                videos.append({
                    'filename': filename,
                    'url':      url,
                    'label':    filename,
                })

        screenshots.sort(key=lambda x: x['date'])

        roster = season_roster(season_path)

        hero_name = SEASON_HEROES.get(season_num)
        # the hero is a background image the size of the header, never the
        # full-resolution original
        hero = next((x['view'] for x in screenshots if x['filename'] == hero_name), None)
        if hero is None and screenshots:
            hero = screenshots[len(screenshots) // 2]['view']

        entry = {
            'number':           season_num,
            'name':             SEASON_NAMES.get(season_num, f'SEASON {season_num}'),
            'description':      SEASON_DESCRIPTIONS.get(season_num, f'Season {season_num}.'),
            'has_logo':         has_logo,
            'logo_file':        logo_file,
            'screenshots':      screenshots,
            'videos':           videos,
            'hero':             hero,
            'screenshot_count': len(screenshots),
            'video_count':      len(videos),
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
    })


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
        return JsonResponse({'live': True, 'players': [], 'source': pull})

    board['live']   = True
    board['season'] = LIVE_SEASON
    board['source'] = pull
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


def activity_feed(request):
    """When the server gets played, hour by hour.

    Its own endpoint rather than part of the board: the board is polled every
    minute and this changes on the sync's clock, not the page's. It is fetched
    once when the section is opened and left alone after that.

    The hour buckets go out in UTC. Rolling them into a day-of-week grid means
    picking a timezone, and the only one worth picking belongs to whoever is
    reading, so the page does it.
    """
    if not LIVE_SEASON:
        return JsonResponse({'live': False}, status=404)

    key = f'season{LIVE_SEASON}'
    return JsonResponse(
        activity_data.board(os.path.join(MINECRAFT_ROOT, key, 'data')))


def skill_tree(request):
    """The tree itself, redirected to a URL that carries its own mtime.

    It is a static file and a big one, so it wants caching hard - but a
    re-extracted tree served from a browser cache holding the old one is how
    a new field silently does not exist. The same stamp trick every model and
    icon on this page already uses, applied to the one file that is fetched
    by script rather than named in the markup.
    """
    path = os.path.join(MINECRAFT_ROOT, 'skilltree', 'tree.json')
    try:
        stamp = int(os.path.getmtime(path))
    except OSError:
        stamp = 0
    return redirect(f'/static/minecraft/skilltree/tree.json?v={stamp}')


def history_feed(request):
    """What each player's own numbers have been doing, day by day.

    Its own endpoint for activity_feed's reason: it changes on the sync's
    clock rather than the page's, so it is fetched when the section is opened
    rather than ridden along on the board's poll. Bigger than the activity
    feed too - a row per player per day plus an hourly gauge series - which is
    a second reason not to put it on something polled every minute.
    """
    if not LIVE_SEASON:
        return JsonResponse({'live': False}, status=404)

    key = f'season{LIVE_SEASON}'
    return JsonResponse(
        history_data.board(os.path.join(MINECRAFT_ROOT, key, 'data')))


def guide(request):
    """The modpack's own mechanics, for whoever just joined the live season.

    A static page rather than anything read off the server: what a mod's
    config says a system does does not change between restarts the way a
    player's own numbers do, so there is nothing here worth polling for.
    """
    return render(request, 'minecraft_guide.html', {'season': LIVE_SEASON})
