"""Read what the live server exports and shape it for the roster.

A season folder can hold two very different records of the same player. The
.dat save is a snapshot of their body: what they were wearing, what was in the
bag, where they stood. The server's own export, which sync_server pulls into
<season>/data, is a record of what they have *done*: hours played, deaths,
damage traded, ground covered, bosses put down. None of that is in a save.

So this is a second source rather than a replacement. Where both exist they are
merged onto one card; where only the export exists, as on a season still being
played, it carries the card on its own.
"""

import json
import os
import time

from . import sync
from datetime import datetime, timezone

DATA_DIR = 'data'
PLAYERS  = 'players.json'
BOSSES   = 'boss_kills.json'

# The bosses we hold a model for, and where the portal serves them from. Only
# these can appear on the board: a boss nobody can draw is not a boss anyone
# can look at. Minibosses are built the same way, into a folder of their own,
# and stand ahead of the bosses on the roster rather than mixed in with them.
_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'static', 'minecraft')
BOSS_DIR   = os.path.join(_STATIC, 'bosses')
BOSS_URL   = '/static/minecraft/bosses'
BOSS_INDEX = os.path.join(BOSS_DIR, 'index.json')

MINIBOSS_DIR   = os.path.join(_STATIC, 'minibosses')
MINIBOSS_URL   = '/static/minecraft/minibosses'
MINIBOSS_INDEX = os.path.join(MINIBOSS_DIR, 'index.json')

# The exporter runs through KubeJS, where every number arrives as a double, so
# counts come back as 3.0 rather than 3 and have to be pushed back into shape.
def _int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return default


def _load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _span(seconds):
    """2322 -> '38m', 46430 -> '12h 53m', 131400 -> '1d 12h'.

    Each step drops the one below it. A season's playtime runs to hundreds of
    hours, and '312h 41m' is a number you have to stop and divide; the minutes
    on it were never the point anyway.
    """
    seconds = max(0, int(seconds))
    days,  rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f'{days}d {hours:02d}h'
    if hours:
        return f'{hours}h {minutes:02d}m'
    if minutes:
        return f'{minutes}m'
    return f'{seconds}s'


def _when(text):
    """'2026-08-22T06:17:50.402Z' -> an aware datetime, or None."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


# The exporter only rewrites a player's row while they are on the server, so a
# row that kept pace with the file's own timestamp belongs to somebody standing
# in the world right now. That is the whole of the presence check.
ONLINE_WINDOW = 180


def _bosses(raw):
    """boss_kills.json is keyed by name, one entry per boss type beaten."""
    out = []
    for entry in (raw.get('bosses') or {}).values():
        out.append({
            'name':     entry.get('name') or 'UNKNOWN',
            'tier':     _int(entry.get('tier')),
            # records written before the boss/miniboss split default to 'boss'
            'category': entry.get('category') or 'boss',
            'kills':    _int(entry.get('kills')),
            # damage stats are kept in tenths of a heart-point, the same way
            # the game's own statistics screen divides before showing them
            'damage':   _float(_int(entry.get('lastDamage')) / 10),
            'last':     (entry.get('last') or '')[:10],
        })
    out.sort(key=lambda b: (-b['tier'], -b['kills'], b['name']))
    return out


def load(season_path):
    """Every player the server has exported, keyed by uuid."""
    data_dir = os.path.join(season_path, DATA_DIR)
    players  = _load(os.path.join(data_dir, PLAYERS))
    kills    = _load(os.path.join(data_dir, BOSSES))
    if not players:
        return {}

    updated = players.get('updated', '')
    stamped = _when(updated)
    out = {}

    for name, raw in (players.get('players') or {}).items():
        uuid = raw.get('uuid') or name
        boss = kills.get(name) or kills.get(uuid) or {}

        ticks   = _int(raw.get('playTimeTicks'))
        seconds = _int(raw.get('playTimeSeconds') or ticks / 20)
        walked  = _float(raw.get('walkBlocks'))
        sprint  = _float(raw.get('sprintBlocks'))
        swum    = _float(raw.get('swimBlocks'))
        deaths  = _int(raw.get('deaths'))
        mobs    = _int(raw.get('mobKills'))

        health   = _float(raw.get('health'))
        recorded = _when(raw.get('recorded'))
        behind   = int((stamped - recorded).total_seconds()) \
                   if stamped and recorded else None

        out[uuid] = {
            'uuid':        uuid,
            'name':        raw.get('name') or name,
            'health':      health,
            # nobody walks around on no hearts: a zero is a player lying on the
            # respawn screen, which is why their time since death is also zero
            'dead':        health <= 0,
            'max_health':  _float(raw.get('maxHealth'), 20.0) or 20.0,
            'food':        _int(raw.get('food')),
            'level':       _int(raw.get('xpLevel')),
            'dimension':   (raw.get('dimension') or '').split(':')[-1]
                           .replace('_', ' ').upper(),
            'playtime':      _span(seconds),
            'playtime_hours': _float(raw.get('playTimeHours') or seconds / 3600),
            'deaths':      deaths,
            'mob_kills':   mobs,
            'player_kills': _int(raw.get('playerKills')),
            # a run without a death has no ratio to speak of, so the kills stand
            'ratio':       round(mobs / deaths, 1) if deaths else None,
            'dealt':       _float(_int(raw.get('damageDealt')) / 10),
            'taken':       _float(_int(raw.get('damageTaken')) / 10),
            'jumps':       _int(raw.get('jumps')),
            'walked':      walked,
            'sprinted':    sprint,
            'swum':        swum,
            'travelled':   _float(walked + sprint + swum),
            'since_death': _span(_int(raw.get('timeSinceDeath')) / 20),
            'online':      behind is not None and behind <= ONLINE_WINDOW,
            'seen':        _span(behind) if behind else 'NOW',
            'behind':      behind,
            'bosses':      _bosses(boss),
            'boss_kills':  _int(boss.get('totalKills')),
            'boss_types':  _int(boss.get('bossesDefeated')),
            'recorded':    (raw.get('recorded') or updated)[:16].replace('T', ' '),
        }

    return out


def _stamp(folder, name):
    try:
        return int(os.path.getmtime(os.path.join(folder, name)))
    except OSError:
        return 0


def _known(index_path):
    try:
        with open(index_path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def bosses(season_path, faces=None):
    """The boss roster: one entry per mob we can draw, felled or not.

    The export records kills the other way round, per player, so this turns it
    inside out. A boss nobody has beaten still gets a place in the line: the
    point of the roster is the gap where a kill has not happened yet.

    Minibosses are read from their own index and drawn from their own folder,
    but otherwise go through the same reckoning as a boss - they just lead the
    roster instead of sitting in it.
    """
    known = ([{**b, 'category': 'miniboss', 'dir': MINIBOSS_DIR, 'url': MINIBOSS_URL}
              for b in _known(MINIBOSS_INDEX)] +
             [{**b, 'category': 'boss', 'dir': BOSS_DIR, 'url': BOSS_URL}
              for b in _known(BOSS_INDEX)])
    if not known:
        return []

    raw = _load(os.path.join(season_path, DATA_DIR, BOSSES))
    scored = {}
    for player, record in raw.items():
        uuid = record.get('uuid') or player
        for boss_id, entry in (record.get('bosses') or {}).items():
            kills = _int(entry.get('kills'))
            if kills <= 0:
                continue
            hit = scored.setdefault(boss_id, {'killers': [], 'kills': 0,
                                              'first': '', 'last': '', 'tier': 0})
            hit['kills'] += kills
            hit['tier'] = max(hit['tier'], _int(entry.get('tier')))
            hit['killers'].append({
                'name':   record.get('name') or player,
                'uuid':   uuid,
                'kills':  kills,
                'damage': _float(_int(entry.get('lastDamage')) / 10),
                'last':   (entry.get('last') or '')[:10],
            })
            for key, when in (('first', entry.get('first')), ('last', entry.get('last'))):
                when = (when or '')[:10]
                if not when:
                    continue
                if not hit[key] or (when < hit[key] if key == 'first' else when > hit[key]):
                    hit[key] = when

    out = []
    for boss in known:
        hit = scored.get(boss['id'])
        killers = sorted(hit['killers'], key=lambda k: -k['kills']) if hit else []
        for killer in killers:
            killer.update((faces or {}).get(killer['uuid'], {}))
        out.append({
            'key':     boss['key'],
            'id':      boss['id'],
            'name':    boss['name'],
            'mod':     boss.get('mod', ''),
            'category': boss['category'],
            # the server's own script grades them; the roster does not presume to
            'tier':    hit['tier'] if hit and hit.get('tier') else None,
            # the file's own mtime rides along so a rebuilt model is never
            # served from a browser cache that still holds the old one
            'model':   f'{boss["url"]}/{boss["model"]}?v={_stamp(boss["dir"], boss["model"])}',
            'felled':  bool(hit),
            'kills':   hit['kills'] if hit else 0,
            'killers': killers,
            'first':   hit['first'] if hit else '',
            'last':    hit['last'] if hit else '',
        })
    # bosses lead the roster, minibosses stand behind them in a section of
    # their own; within each, what has been beaten leads the rest
    out.sort(key=lambda b: (b['category'] == 'miniboss', not b['felled'],
                            b['mod'] != 'minecraft', b['mod'], b['name']))
    return out


def board(season_path):
    """The whole live picture: who is on, what the server has seen, how fresh.

    This is what the portal polls. It is built from the files on disk every
    time rather than cached, because the point of the board is that it is not
    telling you something from five minutes ago.
    """
    players = load(season_path)
    if not players:
        return None

    data_dir = os.path.join(season_path, DATA_DIR)
    raw      = _load(os.path.join(data_dir, PLAYERS))
    stamped  = _when(raw.get('updated'))
    age      = int((datetime.now(timezone.utc) - stamped).total_seconds()) \
               if stamped else None

    # When the server was last asked, which is not the same as when it last had
    # something new to say. A quiet hour still leaves a stamp, so the board can
    # show it is being kept up rather than looking abandoned.
    try:
        checked = int(time.time() - os.path.getmtime(os.path.join(data_dir, sync.STAMP)))
    except OSError:
        checked = None

    # whoever is standing in the world comes first, then the most recently gone
    order = sorted(players.values(),
                   key=lambda p: (not p['online'],
                                  p['behind'] if p['behind'] is not None else 1 << 30,
                                  p['name'].lower()))

    seconds = sum(p['playtime_hours'] * 3600 for p in order)
    line = bosses(season_path)
    return {
        'players': order,
        'bosses':  line,
        'updated': raw.get('updated', ''),
        'read':    (raw.get('updated') or '')[11:16],
        'age':     age,
        'age_txt': _span(age) if age is not None else '',
        'checked':     checked,
        'checked_txt': _span(checked) if checked is not None else '',
        'totals': {
            'online':  sum(1 for p in order if p['online']),
            'tracked': len(order),
            'played':  _span(seconds),
            'hours':   round(seconds / 3600, 1),
            'deaths':  sum(p['deaths'] for p in order),
            'kills':   sum(p['mob_kills'] for p in order),
            'bosses':  sum(1 for b in line if b['felled']),
            'boss_all': len(line),
            'boss_kills': sum(b['kills'] for b in line),
            'blocks':  int(sum(p['travelled'] for p in order)),
        },
    }


def stamp(season_path):
    """When the export last changed, so a cached roster knows to rebuild."""
    data_dir = os.path.join(season_path, DATA_DIR)
    marks = []
    for name in (PLAYERS, BOSSES):
        try:
            marks.append(os.path.getmtime(os.path.join(data_dir, name)))
        except OSError:
            marks.append(0)
    return tuple(marks)
