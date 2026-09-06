"""What each player's numbers were, one sample at a time.

The same gap activity.py was written for, one level down. The export carries
sixty-two fields per player and every one of them is a reading of *now*:
`walkBlocks` is a counter that only climbs, `health` and `armor` are whatever
they happen to be this second, and nothing behind any of them is kept. The
site could say a player had walked 129,542 blocks and could not say whether a
thousand of them were yesterday; it could draw a health bar and could not say
whether that player had spent the week at four hearts.

So it is built rather than read, and it starts the day it is switched on.
There is no back-fill because there is nothing to back-fill from - which is
also why this collects more than anything currently draws. A field left
unsampled today is a field with no history in a month, and the cost of
carrying one more number per player per day is a few kilobytes a year.

Two kinds of reading, kept apart because they mean different things:

  * COUNTERS climb and never fall - blocks walked, deaths, damage dealt. What
    is worth keeping is the difference between samples, banked into the day it
    happened on. Same treatment activity.py gives playtime: a player seen for
    the first time becomes a baseline rather than a day with a whole season in
    it, and a counter that has gone backwards is a reset world.
  * GAUGES are a level, not a total - health, armour, attack damage, XP. What
    is worth keeping is the value itself over time, so these are sampled into
    hourly buckets. Health keeps its low and high as well as its last: how
    close somebody came to dying in an hour is the reading, and an hourly last
    would miss every near miss between two samples.

A gauge is only recorded for a player whose row kept pace with the export -
the same test live.py uses for who is online. The export keeps rewriting a
logged-off player's last known health, and sampling that would draw a flat
line across every hour they were not there, which is not a reading of
anything.

Times are bucketed in UTC and shifted into the reader's own zone by the page,
for the same reason activity.py does it.
"""

import json
import os

from datetime import datetime, timedelta, timezone

from . import live
from . import sync

WORLD = 'world_data.json'
LOG = 'history.json'

# ── what is worth keeping ───────────────────────────────────────────────────
# Counters, as short name -> export field. Grouped only by comment; they are
# all banked the same way.
COUNTERS = {
    # how the ground got covered, which is the whole of a playstyle: the
    # sprinter, the boat traveller, the one who fell down every hole
    'walk':     'walkBlocks',
    'sprint':   'sprintBlocks',
    'swim':     'swimBlocks',
    'boat':     'boatBlocks',
    'climb':    'climbBlocks',
    'crouch':   'crouchBlocks',
    'fall':     'fallBlocks',
    'horse':    'horseBlocks',
    'elytra':   'elytraBlocks',
    'minecart': 'minecartBlocks',
    # what happened while they were out there
    'deaths':   'deaths',
    'mobs':     'mobKills',
    'pvp':      'playerKills',
    'dealt':    'damageDealt',
    'taken':    'damageTaken',
    'blocked':  'damageBlocked',
    'jumps':    'jumps',
    'bred':     'animalsBred',
    'slept':    'sleepInBed',
    'fish':     'fishCaught',
    'raids':    'raidsWon',
    'enchants': 'itemsEnchanted',
}

# Which of those are distances. Kept apart because the travel chart wants
# exactly this set and in this order, and a chart deciding that for itself
# would drift from the sampler the moment either changed.
TRAVEL = ('walk', 'sprint', 'swim', 'boat', 'climb', 'crouch',
          'fall', 'horse', 'elytra', 'minecart')

# Gauges: short name -> where to read it. A tuple means it is inside
# `attributes`, which is the whole of a player's build and none of which the
# export gives any history for.
GAUGES = {
    'hp':     'health',
    'hpmax':  'maxHealth',
    'food':   'food',
    'level':  'xpLevel',
    'armor':  ('attributes', 'armor'),
    'tough':  ('attributes', 'armor_toughness'),
    'attack': ('attributes', 'attack_damage'),
    'speed':  ('attributes', 'movement_speed'),
    'luck':   ('attributes', 'luck'),
}

# Which gauges keep a low and a high through the hour as well as a last. Only
# the ones that swing: armour steps when gear changes and a last is the whole
# of it, where health's low is the reading that matters most and is exactly
# the one a last would miss.
SWINGY = ('hp', 'food')

# How many hourly buckets to keep. A bucket is a row per player who was
# actually in the world that hour, so a fortnight of them on a nine-player
# server is a file in the low hundreds of kilobytes. The fine-grained chart
# only ever looks back this far; anything older is read off the days.
KEEP_HOURS = 24 * 21

# Days are kept effectively for ever, for the reason activity.py keeps them:
# a day is a couple of dozen small numbers per player, and it is the only
# record of the season that will exist.
KEEP_DAYS = 366 * 10


def log_path(data_dir):
    return os.path.join(data_dir, LOG)


def lock_path(data_dir):
    return os.path.join(data_dir, '.history.lock')


def _blank():
    return {'hours': {}, 'days': {}, 'last': {}, 'at': '', 'since': ''}


def load(data_dir):
    """The log, or an empty one. Never raises on a bad file.

    A file that will not parse is moved aside rather than read past, for the
    reason activity.load gives: this is the only copy of a history nothing can
    rebuild, and the one thing that must not happen is a bad read quietly
    becoming an empty log that the next write makes permanent.
    """
    path = log_path(data_dir)
    try:
        with open(path) as fh:
            data = json.load(fh)
    except OSError:
        return _blank()
    except ValueError:
        try:
            os.replace(path, path + '.corrupt')
        except OSError:
            pass
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    for key in ('hours', 'days', 'last'):
        if not isinstance(data.get(key), dict):
            data[key] = {}
    data.setdefault('at', '')
    data.setdefault('since', '')
    # The last day that was simulated rather than sampled, if any - written by
    # tools/seed_history.py and never by this module. Sampling only ever adds
    # days after it, so a real sample can never land on a made-up one.
    data.setdefault('seeded', '')
    return data


def _when(text):
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _num(value):
    return float(value) if isinstance(value, (int, float)) \
        and not isinstance(value, bool) else None


def _gauge(raw, where):
    """One gauge off a player's row, whether it is top level or in attributes."""
    if isinstance(where, tuple):
        holder = raw.get(where[0])
        return _num(holder.get(where[1])) if isinstance(holder, dict) else None
    return _num(raw.get(where))


def _hour_key(when):
    return when.strftime('%Y-%m-%dT%H')


def _day_key(when):
    return when.strftime('%Y-%m-%d')


def _slice(start, end):
    """The window broken into (hour key, day key, seconds) pieces.

    The same split activity.py makes and for the same reason: a sample at ten
    past covering the previous twenty minutes straddles two hours, and the
    blocks walked in it belong to both. Dropping the whole delta on the hour
    the sample landed in would bias every window that crosses an hour.
    """
    out = []
    edge = start
    while edge < end:
        top = (edge + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0)
        stop = min(top, end)
        out.append((_hour_key(edge), _day_key(edge),
                    (stop - edge).total_seconds()))
        edge = stop
    return out


def _day(log, key):
    """One day's row, made if it is not there yet."""
    day = log['days'].get(key)
    if not isinstance(day, dict):
        day = {}
        log['days'][key] = day
    return day


def _day_player(log, day_key, name):
    row = _day(log, day_key).setdefault(name, {})
    if not isinstance(row, dict):
        row = {}
        log['days'][day_key][name] = row
    return row


def _hour(log, key, name):
    """One player's row in one hour, made if it is not there yet."""
    hour = log['hours'].get(key)
    if not isinstance(hour, dict):
        hour = {}
        log['hours'][key] = hour
    row = hour.get(name)
    if not isinstance(row, dict):
        row = {'n': 0}
        hour[name] = row
    row.setdefault('n', 0)
    return row


def _bank(log, name, before, now, moved):
    """Spread one player's counter deltas across the hours and days they span.

    `moved` is short name -> how much that counter climbed over the window.

    All twenty-two go into the day, which is the long record. Only the ten
    distances also go into the hour: a chart that can be asked for the last
    twelve hours needs a grain finer than a day to answer with, and ten more
    numbers in an hourly bucket is worth that where all twenty-two would be
    twelve more nobody has asked a question of.
    """
    window = _slice(before, now) if before is not None else []
    span = sum(seconds for _h, _d, seconds in window)
    if not window or span <= 0:
        window = [(_hour_key(now), _day_key(now), 1.0)]
        span = 1.0

    # a window can cross midnight, so the same delta lands in two days in
    # proportion to how much of the window fell in each
    by_day = {}
    for _hour_k, day_k, seconds in window:
        by_day[day_k] = by_day.get(day_k, 0.0) + seconds

    for day_k, seconds in by_day.items():
        row = _day_player(log, day_k, name)
        for kind, delta in moved.items():
            share = delta * seconds / span
            if share <= 0:
                continue
            row[kind] = round(row.get(kind, 0.0) + share, 1)

    for hour_k, _day_k, seconds in window:
        part = {kind: moved[kind] * seconds / span
                for kind in TRAVEL if moved.get(kind)}
        if not any(part.values()):
            continue
        row = _hour(log, hour_k, name)
        went = row.setdefault('m', {})
        for kind, share in part.items():
            if share > 0:
                went[kind] = round(went.get(kind, 0.0) + share, 1)


def _mark(log, name, now, gauges):
    """Record what a player's levels were at this moment.

    Into the hour the sample was taken in, never spread: a gauge is an
    observation of one instant and spreading it across a window would be
    inventing readings for moments nobody looked at. The day keeps the same
    thing rolled up, so a chart looking back past KEEP_HOURS still has the
    shape of it.
    """
    row = _hour(log, _hour_key(now), name)
    row['n'] += 1
    day = _day_player(log, _day_key(now), name)

    for kind, value in gauges.items():
        row[kind] = value
        day[kind] = value                       # last of the day wins
        if kind not in SWINGY:
            continue
        # the low and the high through the hour, and through the day. A last
        # would show a player who was on one heart at 3am and healed by 4am as
        # having had a quiet night.
        lo, hi = f'{kind}lo', f'{kind}hi'
        for holder in (row, day):
            holder[lo] = value if holder.get(lo) is None else min(holder[lo], value)
            holder[hi] = value if holder.get(hi) is None else max(holder[hi], value)


def _trim(log):
    for key, keep in (('hours', KEEP_HOURS), ('days', KEEP_DAYS)):
        stale = sorted(log[key])[:-keep] if len(log[key]) > keep else []
        for old in stale:
            log[key].pop(old, None)
    # a player the export has stopped carrying should not keep a baseline for
    # ever; the next time they appear they become a baseline again, which is
    # the correct treatment for a counter nobody has watched in the meantime
    for name in [n for n, v in log['last'].items() if not isinstance(v, dict)]:
        log['last'].pop(name, None)


def _write(data_dir, log):
    """Write the log the way sync writes a fetched file: aside, then in place.

    A crash halfway through writing this leaves the old log intact rather than
    a truncated one, which for the only copy of an unrebuildable history is
    the difference between losing a sample and losing the season.
    """
    path = log_path(data_dir)
    part = path + '.part'
    try:
        with open(part, 'w') as fh:
            json.dump(log, fh, separators=(',', ':'))
        os.replace(part, path)
    except OSError:
        try:
            os.remove(part)
        except OSError:
            pass


def _read_world(data_dir):
    try:
        with open(os.path.join(data_dir, WORLD)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def sample(data_dir, world=None):
    """Read the export and record whatever has moved since the last look.

    Returns (players sampled, counters banked). Doing nothing is ordinary:
    a sample taken twice off the same export finds nothing to bank.
    """
    if world is None:
        world = _read_world(data_dir)
    if not isinstance(world, dict):
        return 0, 0
    players = world.get('players')
    if not isinstance(players, dict):
        return 0, 0

    # One sampler at a time, for activity.sample's reason: a page load starts
    # a pull on a background thread and the worker runs in its own process,
    # and two of them reading this log, adding to it and writing it back would
    # silently drop whichever finished first. Losing a sample to the lock
    # costs nothing - the counters are cumulative and the baseline is whatever
    # was last written, so the next sample measures from there instead.
    with sync.Lock(lock_path(data_dir)) as guard:
        if not guard.held:
            return 0, 0
        return _sample(data_dir, world, players)


def _sample(data_dir, world, players):
    """One sample, with the lock already held."""
    now = _when(world.get('updated'))
    if now is None:
        return 0, 0

    log = load(data_dir)
    before = _when(log.get('at'))
    # the same export twice is not a new sample: nothing in it has moved
    if before is not None and now <= before:
        return 0, 0

    seen = banked = 0
    counters = {}
    for name, raw in players.items():
        if not isinstance(raw, dict):
            continue
        seen += 1

        # ── the counters ────────────────────────────────────────────────
        here = {}
        for kind, field in COUNTERS.items():
            value = _num(raw.get(field))
            if value is not None:
                here[kind] = value
        counters[name] = here

        was = log['last'].get(name)
        if isinstance(was, dict):
            moved = {}
            for kind, value in here.items():
                had = was.get(kind)
                # A counter we have never seen has a value and no history
                # behind it: it becomes a baseline and nothing else, or a
                # season of somebody's walking lands on the day we first
                # looked. One that has gone backwards is a reset world or a
                # restored backup, and gets the same treatment.
                if not isinstance(had, (int, float)) or value < had:
                    continue
                delta = value - had
                if delta > 0:
                    moved[kind] = delta
            if moved:
                _bank(log, name, before, now, moved)
                banked += len(moved)

        # ── the gauges ──────────────────────────────────────────────────
        # Only for a player whose row kept pace with the export, which is the
        # same test live.py uses for who is online. The export goes on
        # rewriting a logged-off player's last known health, and recording
        # that would draw a flat line across every hour they were not there.
        recorded = _when(raw.get('recorded') or raw.get('lastSeen'))
        behind = (now - recorded).total_seconds() if recorded else None
        if behind is None or behind > live.ONLINE_WINDOW:
            continue
        gauges = {}
        for kind, where in GAUGES.items():
            value = _gauge(raw, where)
            if value is not None:
                gauges[kind] = round(value, 2)
        if gauges:
            _mark(log, name, now, gauges)

    log['last'] = counters
    log['at'] = world.get('updated') or ''
    if not log['since']:
        log['since'] = log['at']
    _trim(log)
    _write(data_dir, log)
    return seen, banked


def board(data_dir, days=60):
    """The history, shaped for the page.

    `travel` is one row per day per player, in TRAVEL's order, so the chart
    can stack them without deciding the order itself. `levels` is the hourly
    gauge series, newest last, one list per player.
    """
    log = load(data_dir)
    keys = sorted(log['days'])[-days:]

    travel, totals = [], {}
    for key in keys:
        row = {'day': key, 'who': {}}
        for name, stats in (log['days'].get(key) or {}).items():
            if not isinstance(stats, dict):
                continue
            moved = {kind: stats[kind] for kind in TRAVEL
                     if isinstance(stats.get(kind), (int, float))}
            if not moved:
                continue
            row['who'][name] = moved
            totals[name] = round(totals.get(name, 0.0) + sum(moved.values()), 1)
        travel.append(row)

    # The hourly series carries both readings for a player: their levels at
    # that hour, and whatever ground they covered during it. One series rather
    # than two because they share an x-axis and a range picker, and two lists
    # keyed the same way is two things to keep in step.
    levels = {}
    for key in sorted(log['hours']):
        for name, row in (log['hours'].get(key) or {}).items():
            if not isinstance(row, dict):
                continue
            levels.setdefault(name, []).append({'at': key, **row})

    return {
        'since':  log.get('since', ''),
        'at':     log.get('at', ''),
        # so the charts can draw the made-up part as made up - see
        # tools/seed_history.py
        'seeded': log.get('seeded', ''),
        'kinds':  list(TRAVEL),
        'gauges': list(GAUGES),
        'travel': travel,
        'totals': totals,
        'levels': levels,
        # how much record there is yet, which is the one thing a chart drawn
        # off two hours of history has to be able to say for itself
        'days':   len(log['days']),
        'hours':  len(log['hours']),
    }
