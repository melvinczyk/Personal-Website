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
from functools import lru_cache
from zoneinfo import ZoneInfo

from django.conf import settings
from datetime import datetime, timezone

DATA_DIR = 'data'
PLAYERS  = 'players.json'
BOSSES   = 'boss_kills.json'
FIGHTS   = 'boss_fights.json'
FIELDGUIDE = 'fieldguide_counts.json'
FISH       = 'fish_caught.json'

# The four categories worth a card on the roster - "intro" is the guide's own
# welcome entries, the same handful for everyone and no more a discovery than
# the title screen is.
FIELDGUIDE_CATEGORIES = ('monster', 'animal', 'plant', 'boss')

# Starcatcher's own ladder, in its own order, with the colour the mod gives
# each rung. A datapack fish with no registry entry is exported as UNKNOWN
# rather than dropped, so it needs a rung of its own at the bottom.
FISH_RARITIES = ('UNKNOWN', 'NONE', 'TRASH', 'COMMON', 'UNCOMMON',
                 'RARE', 'EPIC', 'LEGENDARY', 'GOLDEN')

# A panel is a portrait, not a ledger. Somebody who has landed all four
# hundred and fifty-six species would otherwise be handed four hundred and
# fifty-six rows; the best dozen is what anybody reads.
FISH_LIMIT = 12

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

# Starcatcher's legendary fish, and the icons tools/fish.py lifted out of the
# mod for them. The board is the same idea as the boss roster: every one of
# them has a place from the start, and an empty slot is the point of the line.
FISH_DIR   = os.path.join(_STATIC, 'fish')
FISH_URL   = '/static/minecraft/fish'
FISH_INDEX = os.path.join(FISH_DIR, 'index.json')

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


def _date(when):
    """'2026-08-25T17:09:20.220Z' -> 'Aug 25, 2026'.

    Every date the portal shows reads the one way: the month by name, then
    the day, then the year. The exports carry ISO, which sorts and compares
    correctly by being a string in the right order and reads like a serial
    number, so it is kept in that shape for the reckoning and turned into
    this only on the way out.

    Built by hand rather than with %-d, which is not a format Windows knows.
    """
    stamp = _local(_when(when) if isinstance(when, str) else when)
    return f'{stamp:%b} {stamp.day}, {stamp.year}' if stamp else ''


@lru_cache(maxsize=1)
def _here():
    """The clock the people reading this are on."""
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except Exception:                        # a bad or missing zone name
        return timezone.utc


def _local(stamp):
    """A reading moved off UTC and onto that clock.

    The exporter writes real UTC and says so: a file stamped 03:01Z was three
    minutes old at 22:04 Central. The game server's console log is on a third
    clock again, an hour ahead of Central, but nothing here reads the log.

    The conversion has to happen before the date is taken as well as the time.
    03:01 UTC is the previous evening in Chicago, so a date left in UTC would
    put an evening's play under tomorrow's heading.
    """
    return stamp.astimezone(_here()) if stamp else stamp


def _clock(stamp):
    """17:09 -> '5:09pm'. Nobody reads a scoreboard in twenty-four hour time.

    Built by hand for the same reason _date is: %-I is not a format Windows
    knows, and %I pads the hour to two digits, which reads as a stopwatch.
    """
    return f'{stamp.hour % 12 or 12}:{stamp.minute:02d}{"am" if stamp.hour < 12 else "pm"}'


def _moment(when):
    """The instant itself, in UTC, for the page to render.

    Which clock a reading should be shown on is not something this end can
    answer: the answer is wherever the person looking happens to be. So the
    server settles the one thing it does know, the instant, and hands it over
    in a form with no ambiguity in it. minecraft.js turns it into words.

    _clock and _local stay for anything rendered server-side, and for the
    fallback the page uses when a browser cannot parse the stamp.
    """
    stamp = _when(when) if isinstance(when, str) else when
    return stamp.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if stamp else ''


# The exporter only rewrites a player's row while they are on the server, so a
# row that kept pace with the file's own timestamp belongs to somebody standing
# in the world right now. That is the whole of the presence check.
ONLINE_WINDOW = 180

# Whether the game server itself is up. The export is rewritten while it runs,
# so the question is not how old the file is now but how old it was the last
# time we went and looked: measured against now, a healthy server would read
# offline for the whole hour between one scheduled pull and the next. A file
# that was current when we checked means the server was writing when we
# checked, which is as fresh an answer as anything here can give.
SERVER_WINDOW = 300


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
            'assists':  0,
            'last':     (entry.get('last') or '')[:10],
        })
    held = {b['id']: b for b in out}
    for boss_id, tally in (credited or {}).items():
        boss = held.get(boss_id)
        if boss:
            # NOT max. The counter gives a player a kill for every fight they
            # were in, helping included, so its number is the one that needs
            # correcting: where the log knows this player and this boss, what
            # the log says they led is what they led.
            boss['kills'] = tally['kills']
            boss['assists'] = tally['assists']
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
            'assists':  tally['assists'],
            'last':     tally['last'],
        })
    # the merge above leans on ISO comparing correctly, so the reading is only
    # made readable once there is nothing left to compare
    for boss in out:
        boss['last'] = _date(boss['last'])
    # what they led leads, and what they only lent a hand to follows
    out.sort(key=lambda b: (not b['kills'], -b['tier'], -b['kills'], b['name']))
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


def _weight(grams):
    """4180 -> '4.18 kg', 640 -> '640 g'.

    A fish is weighed in grams because the small ones want them, and the big
    ones then read as five figures on a panel three columns wide.
    """
    grams = _int(grams)
    if grams >= 1000:
        return f'{round(grams / 1000, 2):g} kg'
    return f'{grams} g'


def _caught_on(seconds):
    """A unix timestamp in seconds -> '2026-08-28', or '' if it is not one."""
    try:
        return _local(datetime.fromtimestamp(int(seconds), timezone.utc)).strftime('%Y-%m-%d')
    except (TypeError, ValueError, OSError, OverflowError):
        return ''


def _fish(raw, covers):
    """One player's fish_caught.json row, in the units the panel wants.

    The export keeps three counts that are easy to confuse, so they are named
    apart here: `total` is every individual fish landed, `species` the number
    of distinct ones, and `legendary` how many of those species are legendary.

    `fish` holds only the rarities the tracker is set to export - LEGENDARY
    alone at the moment - which is why the row count and `species` need not
    agree, and why `covers` rides along: a panel showing four rows out of a
    hundred and twenty caught should say which four it is showing.

    Starcatcher's percentile runs the way a placing does rather than the way a
    score does: CaughtFishInfo.getScale() interpolates from the largest fish
    at 0 to the smallest at 100, so 3.1 is a top-3% specimen, not a poor one.
    """
    rows = []
    for fish_id, entry in (raw.get('fish') or {}).items():
        if not isinstance(entry, dict):
            continue
        rarity = str(entry.get('rarity') or 'UNKNOWN').upper()
        rows.append({
            'id':      fish_id,
            'name':    _label(fish_id),
            'mod':     fish_id.split(':')[0].replace('_', ' ') if ':' in fish_id else '',
            'rarity':  rarity,
            'rank':    FISH_RARITIES.index(rarity) if rarity in FISH_RARITIES else 0,
            'count':   _int(entry.get('count')),
            'size':    _int(entry.get('bestSizeCm')),
            'weight':  _weight(entry.get('bestWeightG')),
            # the mod records this to a tenth and a tenth is what it is worth
            'top':     _float(entry.get('bestPercentile')),
            'golden':  bool(entry.get('golden')),
            'perfect': bool(entry.get('perfect')),
            'first':   _date(_caught_on(entry.get('firstCatch'))),
        })
    # rarest first, then whoever has landed the most of it: the point of the
    # list is the trophy at the top of it, not the tally at the bottom
    rows.sort(key=lambda f: (-f['rank'], -f['count'], f['name']))
    return {
        'total':     _int(raw.get('totalCaught')),
        'species':   _int(raw.get('caught')),
        'legendary': _int(raw.get('legendaryCaught')),
        'covers':    covers,
        'fish':      rows[:FISH_LIMIT],
        # what the cap left out, so a long list can say so rather than just
        # stopping
        'more':      max(0, len(rows) - FISH_LIMIT),
    }


def _covers(fish_raw):
    """Which rarities the tracker is exporting, as something readable.

    It writes the list it was configured with, or the string "all" when it is
    set to export everything.
    """
    rarities = (fish_raw or {}).get('rarities')
    if isinstance(rarities, list):
        return ', '.join(str(r).upper() for r in rarities if r)
    return str(rarities).upper() if rarities else ''


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
    # a few mods hang a model variant off the id with a slash -
    # simplybows:echo_bow/echo_bow - and only the last segment is the item,
    # so keeping the whole path spelled it "Echo Bow/echo Bow"
    name = item_id.split(':')[-1].rstrip('/').split('/')[-1]
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
        # sorted by what each took off the boss, so the first of them is the
        # one the kill belongs to - see _fight_credits for why that is the
        # biggest share rather than the last blow
        participants = sorted(
            ({'name': name, 'damage': _float(p.get('damage')),
              'share': round((p.get('share') or 0) * 100)}
             for name, p in (entry.get('participants') or {}).items()),
            key=lambda p: (-p['share'], -p['damage'], p['name']))
        for place, player in enumerate(participants):
            player['lead'] = place == 0
        # A share is a fraction of the boss's own max health, not of what the
        # tracked players dealt between them, so whatever the participants do
        # not add up to is health the fight took off the boss and credited to
        # nobody: lava, a fall, a wandering mob, or damage discarded when a
        # long-abandoned engagement was reset. discardedDamage names only that
        # last kind, and only sometimes - the Absorber went down with a
        # finisher on 76% and a null there, the missing 24% being the world
        # rather than a stale ledger. Taking the remainder instead names every
        # kind of it at once and, being in the same units, always fills the
        # bar the participants' own shares are drawn on.
        untracked = max(0, 100 - sum(p['share'] for p in participants))
        out.append({
            'time':       _moment(entry.get('time')),
            'sort':       entry.get('time') or '',
            'max_health': max_health,
            'duration':   _span(_int(entry.get('durationSeconds'))),
            'finisher':   entry.get('finisher') or '',
            'weapon':     _label(entry.get('finisherWeapon')),
            # whose kill this is, which the finisher only sometimes also is
            'lead':       participants[0]['name'] if participants else
                          (entry.get('finisher') or ''),
            'participants': participants,
            'untracked_share': untracked,
        })
    out.sort(key=lambda f: f['sort'], reverse=True)
    for fight in out:
        del fight['sort']
    return out[:FIGHT_LIMIT]


def _fight_credits(fights_raw):
    """Who the fight log says led each kill, and who was there helping.

    A boss goes down once, and the kill counter records that against every
    player who was in on it - so a party of two reads as two kills of the
    same mob. The Ancient Guardian went down once and the board said twice.
    The log counts fights rather than players: one entry, one kill.

    It also holds the thing the counter never did, which is how the damage
    split. The kill goes to whoever took the most off the boss, not to
    whoever landed the last blow - often the same player and sometimes not.
    That same Ancient Guardian was finished off with a loaf of bread by the
    one who had dealt the smaller half of its health. Everybody else in the
    fight is recorded as having helped: a real thing to have done and worth
    saying, but not a kill of their own.

    Returns boss id -> {kills, leads {name -> {kills, last}},
                        helped {name -> {fights, last}}, first, last}.
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
        seen = out.setdefault(boss_id, {'kills': 0, 'leads': {}, 'helped': {},
                                        'first': '', 'last': ''})
        for entry in entries:
            when = (entry.get('time') or '')[:10]
            seen['kills'] += 1
            # damage and then name after the share itself, so two players who
            # round to the same percent still land in a settled order rather
            # than whichever way the file happened to be written
            ranked = sorted(
                ((name, _float((p or {}).get('share')),
                  _float((p or {}).get('damage')))
                 for name, p in (entry.get('participants') or {}).items()),
                key=lambda row: (-row[1], -row[2], row[0]))
            # a fight with nobody named in it still had somebody swing last
            if not ranked and entry.get('finisher'):
                ranked = [(entry['finisher'], 0.0, 0.0)]
            for place, (name, _share, _dealt) in enumerate(ranked):
                bucket, field = (('leads', 'kills') if place == 0
                                 else ('helped', 'fights'))
                tally = seen[bucket].setdefault(name, {field: 0, 'last': ''})
                tally[field] += 1
                tally['last'] = max(tally['last'], when)
            if when:
                seen['first'] = min(seen['first'] or when, when)
                seen['last'] = max(seen['last'], when)
    return out


def _by_player(credits):
    """The same credits the other way up: name -> boss id -> what they did.

    Both halves of it, kept apart: the fights a player led, which are their
    kills, and the ones they only helped with, which are not. A record that
    counted the second as the first is what had a player who never led an
    Ancient Guardian fight showing one on their own card - see
    _fight_credits.
    """
    out = {}
    for boss_id, seen in credits.items():
        for name, tally in seen['leads'].items():
            out.setdefault(name, {})[boss_id] = {
                'kills': tally['kills'], 'assists': 0, 'last': tally['last']}
        for name, tally in seen['helped'].items():
            row = out.setdefault(name, {}).setdefault(
                boss_id, {'kills': 0, 'assists': 0, 'last': ''})
            row['assists'] = tally['fights']
            row['last'] = max(row['last'], tally['last'])
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
    # fish_caught.json nests its rows under "players" and carries a header of
    # its own, where every other export is a bare map keyed by player name
    hooked   = _load(os.path.join(data_dir, FISH))
    reeled   = hooked.get('players') if isinstance(hooked, dict) else {}
    covers   = _covers(hooked)
    if not players:
        return {}

    # what the fight log credits each player with, for the fights the kill
    # counter did not record - see _fight_credits
    finished  = _by_player(_fight_credits(_load(os.path.join(data_dir, FIGHTS))))
    catalogue = _catalogue()

    updated = players.get('updated', '')
    stamped = _when(updated)
    out = {}

    for name, raw in (players.get('players') or {}).items():
        uuid = raw.get('uuid') or name
        boss = kills.get(name) or kills.get(uuid) or {}
        field = scans.get(name) or scans.get(uuid) or {}
        rod = (reeled or {}).get(name) or (reeled or {}).get(uuid) or {}

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
            # The export's own totals have the same fault its rows do - a
            # player is credited for every fight they were in, helping
            # included - so the corrected rows are added up instead, and the
            # export is only a floor for a record with no rows at all to sum.
            # Otherwise the header over the list disagrees with the list.
            'boss_kills':  sum(b['kills'] for b in beaten) if beaten
                           else _int(boss.get('totalKills')),
            'boss_types':  sum(1 for b in beaten if b['kills']) if beaten
                           else _int(boss.get('bossesDefeated')),
            'fieldguide':  _fieldguide(field),
            'fishing':     _fish(rod, covers),
            'recorded':    _moment(raw.get('recorded') or updated),
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
            hit = scored.setdefault(boss_id, {'killers': [], 'helpers': [],
                                              'kills': 0, 'first': '',
                                              'last': '', 'tier': 0})
            # NOT a sum. The counter records one kill against every player who
            # was in on a fight, so adding them up turns a party of two into
            # two kills of the same mob. Whoever was there for the most of
            # them is how many times it has actually gone down.
            hit['kills'] = max(hit['kills'], kills)
            hit['tier'] = max(hit['tier'], _int(entry.get('tier')))
            hit['killers'].append({
                'name':   record.get('name') or player,
                'uuid':   uuid,
                'kills':  kills,
                # kept ISO here: the fight log's own tallies are merged onto
                # these below by comparing them, and made readable after
                'last':   (entry.get('last') or '')[:10],
            })
            for key, when in (('first', entry.get('first')), ('last', entry.get('last'))):
                when = (when or '')[:10]
                if not when:
                    continue
                if not hit[key] or (when < hit[key] if key == 'first' else when > hit[key]):
                    hit[key] = when

    # boss_fights.json is the other half of the record, and the only half
    # that can tell a kill from a hand in somebody else's. Where it covers a
    # boss it decides who led: a player the log knows only as a helper is
    # moved out of the killers, and one it does not know at all keeps
    # whatever the counter gave them, so a log that only started recording
    # halfway through a season does not erase what came before it.
    who = _uuids(_load(os.path.join(season_path, DATA_DIR, PLAYERS)), raw)
    for boss_id, seen in _fight_credits(fights_raw).items():
        hit = scored.setdefault(boss_id, {'killers': [], 'helpers': [],
                                          'kills': 0, 'first': '',
                                          'last': '', 'tier': 0})
        # The counter's own numbers include the fights a player only helped
        # with - the Naga had eleven fights and the counter's three rows added
        # to fourteen - so where the log knows a player it replaces their
        # count rather than being weighed against it. A player the log has
        # never heard of keeps what the counter gave them, so a log that only
        # began recording halfway through a season erases nothing.
        hit['kills'] = max(hit['kills'], seen['kills']) \
            if not seen['kills'] else seen['kills']
        logged = set(seen['leads']) | set(seen['helped'])
        hit['killers'] = [k for k in hit['killers'] if k['name'] not in logged]

        for name, tally in seen['leads'].items():
            hit['killers'].append({
                'name': name,
                # a name is all the log carries, and a killer with no uuid
                # has no face to put beside it
                'uuid': who.get(name) or name,
                'kills': tally['kills'], 'last': tally['last']})

        for name, tally in seen['helped'].items():
            if name in seen['leads']:
                continue                     # led one fight, helped another
            hit['helpers'].append({
                'name': name, 'uuid': who.get(name) or name,
                'fights': tally['fights'], 'last': tally['last']})

        for key in ('first', 'last'):
            when = seen[key]
            if when and (not hit[key] or
                         (when < hit[key] if key == 'first' else when > hit[key])):
                hit[key] = when

    out = []
    for boss in known:
        hit = scored.get(boss['id'])
        killers = sorted(hit['killers'], key=lambda k: -k['kills']) if hit else []
        # whoever was in on a kill without leading it: not a killer of this
        # boss, but not nobody either
        helpers = sorted(hit.get('helpers') or [],
                         key=lambda h: -h['fights']) if hit else []
        for who in killers + helpers:
            who.update((faces or {}).get(who['uuid'], {}))
            # the two files have finished being weighed against each other by
            # here, so the ISO the weighing needed can become the reading
            who['last'] = _date(who['last'])
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
            'helpers': helpers,
            'first':   _date(hit['first']) if hit else '',
            'last':    _date(hit['last']) if hit else '',
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


def fish(season_path, faces=None):
    """The legendary fish board: one entry per catchable fish, landed or not.

    tools/fish.py has already worked out which of Starcatcher's legendaries
    this pack can actually produce - a fish gated on a mod nobody has
    installed is a slot that could never be filled - so the index is the whole
    board. What the export adds is who has landed each one and the best
    specimen anybody has pulled out of the water.

    The mod records the best catch per species per player rather than every
    individual one, so "best" here is the best of those bests: the biggest
    fish on the server, and whose it is.
    """
    known = _known(FISH_INDEX)
    if not known:
        return []

    hooked = _load(os.path.join(season_path, DATA_DIR, FISH))
    reeled = hooked.get('players') if isinstance(hooked, dict) else {}

    landed = {}
    for name, record in (reeled or {}).items():
        if not isinstance(record, dict):
            continue
        who = record.get('name') or name
        for fish_id, entry in (record.get('fish') or {}).items():
            if not isinstance(entry, dict):
                continue
            count = _int(entry.get('count'))
            if count <= 0:
                continue
            hit = landed.setdefault(fish_id, {'count': 0, 'anglers': [],
                                              'best': None, 'first': ''})
            hit['count'] += count
            hit['anglers'].append({
                'name':  who,
                'uuid':  record.get('uuid') or who,
                'count': count,
            })
            when = _caught_on(entry.get('firstCatch'))
            if when and (not hit['first'] or when < hit['first']):
                hit['first'] = when
            # a lower percentile is a bigger fish - see _fish() - so the
            # record holder is whoever has the smallest one
            top = _float(entry.get('bestPercentile'))
            best = hit['best']
            if best is None or top < best['top']:
                hit['best'] = {
                    'by':      who,
                    'size':    _int(entry.get('bestSizeCm')),
                    'weight':  _weight(entry.get('bestWeightG')),
                    'top':     top,
                    'golden':  bool(entry.get('golden')),
                    'perfect': bool(entry.get('perfect')),
                }

    out = []
    for entry in known:
        hit = landed.get(entry.get('id'))
        anglers = sorted(hit['anglers'], key=lambda a: -a['count']) if hit else []
        for angler in anglers:
            angler.update((faces or {}).get(angler['uuid'], {}))
        out.append({
            'key':    entry.get('key'),
            'id':     entry.get('id'),
            'name':   entry.get('name') or 'UNKNOWN',
            'mod':    entry.get('mod', ''),
            'rarity': entry.get('rarity') or 'LEGENDARY',
            # the mtime rides along so a re-extracted icon is never served
            # from a browser cache still holding the old one
            'icon':   f'{FISH_URL}/{entry["icon"]}?v={_stamp(FISH_DIR, entry["icon"])}',
            'caught':  bool(hit),
            'count':   hit['count'] if hit else 0,
            'anglers': anglers,
            'best':    hit['best'] if hit else None,
            'first':   _date(hit['first']) if hit else '',
        })
    # what has been landed leads, so a board that is mostly silhouettes still
    # opens on the ones somebody has actually pulled out
    out.sort(key=lambda f: (not f['caught'], -f['count'], f['name']))
    return out


def _server_up(age, checked):
    """Was the game server writing, as of our last look at it?

    `age` counts from the export's own timestamp and `checked` from the moment
    we last fetched, both to now, so the difference is how stale the export
    already was when it reached us. A small skew the wrong way is normal and
    still counts as up: the two numbers come off two different clocks.
    """
    if age is None or checked is None:
        return {'online': None, 'lag': None}
    lag = age - checked
    return {'online': lag < SERVER_WINDOW, 'lag': lag}


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
    school = fish(season_path)
    return {
        'players': order,
        'bosses':  line,
        'fish':    school,
        # the silhouette a fish nobody has landed is drawn as, sent once
        # rather than repeated on every tile that needs it
        'fish_unknown': f'{FISH_URL}/unknown.png?v={_stamp(FISH_DIR, "unknown.png")}',
        'updated': raw.get('updated', ''),
        'read':    stamped.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if stamped else '',
        'age':     age,
        'age_txt': _span(age) if age is not None else '',
        'server':      _server_up(age, checked),
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
            'fish':     sum(1 for f in school if f['caught']),
            'fish_all': len(school),
            'blocks':  int(sum(p['travelled'] for p in order)),
        },
    }


def stamp(season_path):
    """When the export last changed, so a cached roster knows to rebuild."""
    data_dir = os.path.join(season_path, DATA_DIR)
    marks = []
    for name in (PLAYERS, BOSSES, FIGHTS, FIELDGUIDE, FISH):
        try:
            marks.append(os.path.getmtime(os.path.join(data_dir, name)))
        except OSError:
            marks.append(0)
    return tuple(marks)
