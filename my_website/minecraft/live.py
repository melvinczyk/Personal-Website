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
FIGHTS   = 'boss_fights.json'
FIELDGUIDE = 'fieldguide_counts.json'

# The four categories worth a card on the roster - "intro" is the guide's own
# welcome entries, the same handful for everyone and no more a discovery than
# the title screen is.
FIELDGUIDE_CATEGORIES = ('monster', 'animal', 'plant', 'boss')

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


def _kill_entries(record):
    """One player's boss_kills.json row, bosses and minibosses together.

    The export keeps them in two separate dicts under the player rather than
    one flat one with a category field the way it used to - which sub-dict an
    id came from is now the only place that category lives.
    """
    return {**(record.get('bosses') or {}), **(record.get('minibosses') or {})}


def _bosses(record, credited=None, catalogue=None):
    """boss_kills.json is keyed by name, one entry per boss type beaten.

    `credited` is the other half of the same record: what boss_fights.json
    says this player struck the last blow on. The two files are written by
    different halves of the server's script and either can miss a fight the
    other caught, so a boss that appears in only one of them still counts.
    Where both hold the same boss the larger count wins - they are counting
    the same kills, and adding them would double every one they both saw.
    """
    mini = set((record.get('minibosses') or {}).keys())
    out = []
    for boss_id, entry in _kill_entries(record).items():
        out.append({
            'id':       boss_id,
            'name':     entry.get('name') or 'UNKNOWN',
            'tier':     _int(entry.get('tier')),
            'category': 'miniboss' if boss_id in mini else 'boss',
            'kills':    _int(entry.get('kills')),
            'last':     (entry.get('last') or '')[:10],
        })
    held = {b['id']: b for b in out}
    for boss_id, tally in (credited or {}).items():
        boss = held.get(boss_id)
        if boss:
            boss['kills'] = max(boss['kills'], tally['kills'])
            boss['last'] = max(boss['last'], tally['last'])
            continue
        # a fight the kill counter never recorded: the log names the boss and
        # the moment but nothing else, so the rest comes from the roster's own
        # index, which is where an unfelled boss's name and grade come from too
        seen = (catalogue or {}).get(boss_id) or {}
        out.append({
            'id':       boss_id,
            'name':     seen.get('name') or 'UNKNOWN',
            'tier':     _int(seen.get('tier')),
            'category': seen.get('category') or 'boss',
            'kills':    tally['kills'],
            'last':     tally['last'],
        })
    out.sort(key=lambda b: (-b['tier'], -b['kills'], b['name']))
    return out


def _fieldguide(raw):
    """One player's fieldguide_counts.json entry, in the units the card wants.

    Categories arrive as doubles the same way every other KubeJS export does,
    and "intro" is dropped: it is the guide's own handful of welcome entries,
    the same for everyone, and not a discovery.
    """
    cats = raw.get('categories') or {}
    return {
        'total': _int(raw.get('total')),
        'categories': {cat: _int(cats.get(cat)) for cat in FIELDGUIDE_CATEGORIES},
    }


def _label(item_id):
    """'simplyswords:diamond_halberd' -> 'Diamond Halberd'.

    An empty main hand is not a missing reading, it is a real one: the game
    calls an empty slot minecraft:air, and a boss finished off by somebody
    holding nothing was finished off by hand. Saying "Air" made that look
    like a broken lookup.
    """
    if not item_id:
        return ''
    if item_id in ('minecraft:air', 'air'):
        return 'Bare Hands'
    name = item_id.split(':')[-1]
    return ' '.join(word.capitalize() for word in name.split('_'))


# A card is a portrait, not a combat log: the ten most recent fights are
# worth reading, and a boss put down two hundred times would otherwise hand
# it two hundred rows.
FIGHT_LIMIT = 10


def _fight_history(entries):
    """One boss's own list in boss_fights.json, newest first.

    Each fight names whoever landed the kill and how the damage split across
    everyone who took part, which boss_kills.json's per-player rows never
    carried even before the schema changed - a kill counts once for whoever
    is credited with it, but the fight itself is the whole party's.
    """
    out = []
    for entry in entries or []:
        max_health = _int(entry.get('maxHealth'))
        participants = sorted(
            ({'name': name, 'damage': _float(p.get('damage')),
              'share': round((p.get('share') or 0) * 100)}
             for name, p in (entry.get('participants') or {}).items()),
            key=lambda p: -p['share'])
        # a share is already a fraction of the boss's own max health, not of
        # what the tracked participants dealt between them, so whatever they
        # do not add up to is damage from something the fight never credited
        # to a player - discardedDamage names that leftover directly instead
        # of leaving it to be inferred, but the same share-of-max-health
        # units mean it slots into the bar the participants' own shares fill
        discarded = _float(entry.get('discardedDamage'))
        out.append({
            'time':       (entry.get('time') or '')[:16].replace('T', ' '),
            'sort':       entry.get('time') or '',
            'max_health': max_health,
            'duration':   _span(_int(entry.get('durationSeconds'))),
            'finisher':   entry.get('finisher') or '',
            'weapon':     _label(entry.get('finisherWeapon')),
            'participants': participants,
            'discarded':  discarded,
            'discarded_share': round(discarded / max_health * 100) if max_health else 0,
        })
    out.sort(key=lambda f: f['sort'], reverse=True)
    for fight in out:
        del fight['sort']
    return out[:FIGHT_LIMIT]


def _fight_credits(fights_raw):
    """What boss_fights.json alone knows about who has put what down.

    A fight is a kill by any reading: it names the boss, the moment, and
    whoever struck last. boss_kills.json is the only place the roster used to
    look, so a fight the kill counter missed left the boss standing on the
    board with its own fight sitting unread in the file next to it. This
    turns the log into the same shape the kill counter is read in, so the two
    can be weighed against each other.

    A kill is credited to the finisher, the same way boss_kills.json credits
    it - the fight itself belongs to everyone in the participants list, and
    that is what the fight history under the card is for.

    Returns boss id -> {kills, killers {name -> {kills, last}}, first, last}.
    """
    # the file is server-fed and read straight off disk, so a run that finds
    # something other than the log where the log should be reports no fights
    # rather than taking the board down with it
    if not isinstance(fights_raw, dict):
        return {}
    out = {}
    for boss_id, entries in fights_raw.items():
        if not isinstance(entries, list):
            continue
        seen = out.setdefault(boss_id, {'kills': 0, 'killers': {},
                                        'first': '', 'last': ''})
        for entry in entries:
            when = (entry.get('time') or '')[:10]
            seen['kills'] += 1
            finisher = entry.get('finisher') or ''
            if finisher:
                who = seen['killers'].setdefault(finisher,
                                                 {'kills': 0, 'last': ''})
                who['kills'] += 1
                who['last'] = max(who['last'], when)
            if when:
                seen['first'] = min(seen['first'] or when, when)
                seen['last'] = max(seen['last'], when)
    return out


def _by_finisher(credits):
    """The same credits the other way up: player name -> boss id -> tally."""
    out = {}
    for boss_id, seen in credits.items():
        for name, tally in seen['killers'].items():
            out.setdefault(name, {})[boss_id] = tally
    return out


def _uuids(players, kills):
    """name -> uuid, for the one export that names a player and nothing else.

    boss_fights.json writes its finisher and participants by display name
    where everything else carries the uuid alongside, and a killer with no
    uuid has no face to put beside their name on a card.
    """
    out = {}
    for name, raw in ((players or {}).get('players') or {}).items():
        uuid = (raw or {}).get('uuid')
        if uuid:
            out[(raw or {}).get('name') or name] = uuid
    for name, record in (kills or {}).items():
        uuid = (record or {}).get('uuid')
        if uuid:
            out.setdefault((record or {}).get('name') or name, uuid)
    return out


def _catalogue():
    """id -> the name, grade and rank the roster holds for that mob.

    What a record carrying only an id needs to be shown as anything but the
    id itself. It is the same index the board's own line is built from.
    """
    out = {}
    for entries, category in ((_known(MINIBOSS_INDEX), 'miniboss'),
                              (_known(BOSS_INDEX), 'boss')):
        for entry in entries:
            out[entry.get('id')] = {
                'name': entry.get('name') or 'UNKNOWN',
                'tier': _int(entry.get('tier')),
                'category': category,
            }
    return out


def load(season_path):
    """Every player the server has exported, keyed by uuid."""
    data_dir = os.path.join(season_path, DATA_DIR)
    players  = _load(os.path.join(data_dir, PLAYERS))
    kills    = _load(os.path.join(data_dir, BOSSES))
    scans    = _load(os.path.join(data_dir, FIELDGUIDE))
    if not players:
        return {}

    # what the fight log credits each player with, for the fights the kill
    # counter did not record - see _fight_credits
    finished  = _by_finisher(_fight_credits(_load(os.path.join(data_dir, FIGHTS))))
    catalogue = _catalogue()

    updated = players.get('updated', '')
    stamped = _when(updated)
    out = {}

    for name, raw in (players.get('players') or {}).items():
        uuid = raw.get('uuid') or name
        boss = kills.get(name) or kills.get(uuid) or {}
        field = scans.get(name) or scans.get(uuid) or {}

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

        beaten = _bosses(boss, finished.get(raw.get('name') or name), catalogue)

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
            'bosses':      beaten,
            # the export's own totals count only what boss_kills.json holds,
            # so a fight it missed would leave the header under the list
            # disagreeing with the list itself
            'boss_kills':  max(_int(boss.get('totalKills')),
                               sum(b['kills'] for b in beaten)),
            'boss_types':  max(_int(boss.get('bossesDefeated')), len(beaten)),
            'fieldguide':  _fieldguide(field),
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
    fights_raw = _load(os.path.join(season_path, DATA_DIR, FIGHTS))
    if not isinstance(fights_raw, dict):
        fights_raw = {}
    scored = {}
    for player, record in raw.items():
        uuid = record.get('uuid') or player
        for boss_id, entry in _kill_entries(record).items():
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
                'last':   (entry.get('last') or '')[:10],
            })
            for key, when in (('first', entry.get('first')), ('last', entry.get('last'))):
                when = (when or '')[:10]
                if not when:
                    continue
                if not hit[key] or (when < hit[key] if key == 'first' else when > hit[key]):
                    hit[key] = when

    # boss_fights.json is the second half of the same record, and either half
    # can miss a fight the other caught: the Nehemoth went down with a fight
    # written for it and no kill counted, which left it on the board as a mob
    # nobody had touched with its own kill sitting in the file beside it. Both
    # are read, and where they hold the same boss the fuller one is believed -
    # they are counting the same fights, so adding them would double each one
    # they both saw.
    who = _uuids(_load(os.path.join(season_path, DATA_DIR, PLAYERS)), raw)
    for boss_id, seen in _fight_credits(fights_raw).items():
        hit = scored.setdefault(boss_id, {'killers': [], 'kills': 0,
                                          'first': '', 'last': '', 'tier': 0})
        hit['kills'] = max(hit['kills'], seen['kills'])
        held = {killer['name']: killer for killer in hit['killers']}
        for name, tally in seen['killers'].items():
            killer = held.get(name)
            if killer:
                killer['kills'] = max(killer['kills'], tally['kills'])
                killer['last'] = max(killer['last'], tally['last'])
                continue
            hit['killers'].append({'name': name,
                                   # a name is all the log carries, and a
                                   # killer with no uuid has no face
                                   'uuid': who.get(name) or name,
                                   'kills': tally['kills'],
                                   'last': tally['last']})
        for key in ('first', 'last'):
            when = seen[key]
            if when and (not hit[key] or
                         (when < hit[key] if key == 'first' else when > hit[key])):
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
            # a real kill's own tier wins once there is one - it is the same
            # number either way, but a felled record needs no help from the
            # index. Before that, tools/bosses.py has already baked the grade
            # boss_rewards.js gives this boss into its own index entry, so
            # the roster can show a card's rank before anyone has felled it,
            # rather than only after.
            'tier':    (hit['tier'] if hit and hit.get('tier') else None) or boss.get('tier'),
            # the file's own mtime rides along so a rebuilt model is never
            # served from a browser cache that still holds the old one
            'model':   f'{boss["url"]}/{boss["model"]}?v={_stamp(boss["dir"], boss["model"])}',
            'felled':  bool(hit),
            'kills':   hit['kills'] if hit else 0,
            'killers': killers,
            'first':   hit['first'] if hit else '',
            'last':    hit['last'] if hit else '',
            # only a felled boss has fights worth reading, but an unfelled
            # one costs nothing to look up and finding none is itself a
            # cheap confirmation that the two files agree
            'fights':  _fight_history(fights_raw.get(boss['id'])),
        })
    # bosses lead the roster, minibosses stand behind them in a section of
    # their own; within each, weakest tier first and strongest last, so the
    # grid itself reads as a ladder. A miniboss has no tier worth ordering by
    # (it is always 0), so it falls through to what's beaten, then name.
    out.sort(key=lambda b: (b['category'] == 'miniboss', b['tier'] or 99,
                            not b['felled'], b['mod'] != 'minecraft',
                            b['mod'], b['name']))
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
    for name in (PLAYERS, BOSSES, FIGHTS, FIELDGUIDE):
        try:
            marks.append(os.path.getmtime(os.path.join(data_dir, name)))
        except OSError:
            marks.append(0)
    return tuple(marks)
