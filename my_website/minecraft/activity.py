"""When the server is actually being played, recorded one sample at a time.

Nothing the game exports carries this. `playTimeSeconds` is a counter that only
ever climbs, `recorded` is the last moment a player was seen, and
`world.online` is who is on this second: three readings of the present, and no
history behind any of them. The day this module was written the site could say
that somebody had played for two and a half days, and could not say whether any
of it was a Tuesday.

So it is built rather than read. Every sync writes two things into the same
hourly bucket, and they answer different questions:

  * How long each player was in the world, from the difference between their
    counter now and at the last sample. This is the accurate one, and it lags:
    the export refreshes a player's stats on its own schedule, so a counter can
    sit still for a minute while somebody is plainly online.
  * Who was standing in the world when we looked, straight off
    `world.online.names`. Coarse - it is a snapshot, and somebody who logged in
    and out between two samples is invisible to it - but immediate, and it is
    the only one that can say who was on *at the same time as* whom.

Kept per player rather than only as a total, because "when is the server busy"
and "when is melvin0czyk on" and "when are all of you on together" are three
different questions and the last one is the one people actually want answered.

The consequences of building it that way, stated plainly:

  * It starts empty and only grows forwards. There is no back-fill, because
    there is nothing to back-fill from.
  * Its resolution is the sync interval, which the always-on worker now runs
    at two minutes rather than fifteen. A player who logged in and out inside
    one window still has their minutes counted - the counter caught them - but
    they land in whichever hours the window spans rather than the exact minute
    they were on. A shorter window mostly sharpens the second reading, the
    snapshot of who was standing there when we looked.
  * A gap in the syncing is not a gap in the record. The counter kept climbing
    while nobody was looking, so the next sample sees all of it; the seconds
    are spread across the hours the gap covered rather than dropped on the one
    hour we happened to come back in.

Times are bucketed in UTC. Which hour of the evening that is depends on who is
reading, so the page shifts the buckets into the reader's own zone: a heatmap
of the server's day is only useful in the timezone of the person looking at it.
"""

import json
import os
from datetime import datetime, timedelta, timezone

WORLD = 'world_data.json'
LOG = 'activity.json'

# How many hourly buckets to keep. A bucket is no longer a single number - it
# carries a row per player who was on in that hour - so this is shorter than it
# was: four months of them on a nine-player server is a file in the hundreds of
# kilobytes, and the heatmap folds them into a week anyway.
KEEP_HOURS = 24 * 120

# Per-day, per-player totals are kept for as long, and are what "who made this
# the biggest day of the season" is answered from.
KEEP_DAYS = 180


def log_path(data_dir):
    return os.path.join(data_dir, LOG)


def _blank():
    return {'hours': {}, 'days': {}, 'last': {}, 'at': '', 'since': ''}


def _bucket(log, key):
    """One hour's row, made if it is not there yet.

    `played` is player-seconds banked from the counters; `samples` is how many
    times we looked during that hour; `who` carries both per player - `s` for
    seconds played, `n` for the number of those looks they were online for.
    Presence is n/samples, which is what lets a bucket say somebody was around
    for half an hour without their counter having moved.
    """
    hour = log['hours'].get(key)
    if not isinstance(hour, dict):
        # a bucket written by the version of this file that stored a bare
        # number keeps its total and starts carrying the rest from here
        played = float(hour) if isinstance(hour, (int, float)) else 0.0
        hour = {'played': played, 'samples': 0, 'who': {}}
        log['hours'][key] = hour
    hour.setdefault('played', 0.0)
    hour.setdefault('samples', 0)
    if not isinstance(hour.get('who'), dict):
        hour['who'] = {}
    return hour


def load(data_dir):
    """The log, or an empty one. Never raises on a bad file."""
    try:
        with open(log_path(data_dir)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    for key, empty in (('hours', {}), ('days', {}), ('last', {})):
        if not isinstance(data.get(key), dict):
            data[key] = empty
    data.setdefault('at', '')
    data.setdefault('since', '')
    return data


def _when(text):
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _hour_key(when):
    return when.strftime('%Y-%m-%dT%H')


def _day_key(when):
    return when.strftime('%Y-%m-%d')


def _slice(start, end):
    """The window broken into (hour key, day key, seconds) pieces.

    A sample taken at ten past the hour covering the previous twenty minutes
    straddles two hours, and the seconds in it belong to both. Splitting on the
    hour boundary is what keeps a 7pm spike from being an artifact of when the
    sync happened to run.
    """
    out = []
    edge = start
    while edge < end:
        top = (edge + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0)
        piece = min(top, end)
        out.append((_hour_key(edge), _day_key(edge),
                    (piece - edge).total_seconds()))
        edge = piece
    return out


def sample(data_dir, world=None):
    """Read the export's counters and bank whatever has been played since.

    Returns (players seen, seconds banked). Doing nothing is the ordinary
    case: the export is rewritten once a minute and the sync reads it every
    fifteen, so most samples find some seconds, and a sample taken twice off
    the same file finds none at all.
    """
    if world is None:
        world = _read_world(data_dir)
    if not isinstance(world, dict):
        return 0, 0.0
    players = world.get('players')
    if not isinstance(players, dict):
        return 0, 0.0

    now = _when(world.get('updated'))
    if now is None:
        return 0, 0.0

    log = load(data_dir)
    before = _when(log.get('at'))
    # the same export twice is not a new sample: the counters in it have not
    # moved, and treating it as one would bank a window with nothing in it
    if before is not None and now <= before:
        return 0, 0.0

    # Who was standing in the world at this instant. Recorded against the hour
    # the sample was taken in rather than spread across the window: it is an
    # observation of one moment, and spreading it would be inventing moments we
    # did not look at.
    online = (((world.get('world') or {}).get('online') or {}).get('names'))
    here = _bucket(log, _hour_key(now))
    here['samples'] += 1
    for name in (online if isinstance(online, list) else []):
        if not isinstance(name, str):
            continue
        row = here['who'].setdefault(name, {'s': 0.0, 'n': 0})
        row['n'] += 1

    counters = {}
    banked = 0.0
    for name, raw in players.items():
        if not isinstance(raw, dict):
            continue
        played = raw.get('playTimeSeconds')
        if played is None:
            ticks = raw.get('playTimeTicks')
            played = (ticks / 20) if isinstance(ticks, (int, float)) else None
        if not isinstance(played, (int, float)):
            continue
        counters[name] = float(played)

        was = log['last'].get(name)
        # A player we have never sampled has a counter and no history behind
        # it. Their total so far was played at times nobody recorded, so it
        # becomes a baseline and nothing else - banking it would put a
        # season of somebody's evenings into whichever hour we first looked.
        #
        # A counter that has gone backwards is a reset world or a restored
        # backup, and is treated the same way.
        if not isinstance(was, (int, float)) or counters[name] < was:
            continue
        delta = counters[name] - was
        if delta <= 0:
            continue
        # nobody plays more seconds than have passed. A counter that says
        # otherwise is a glitch, and clamping is what stops one from writing
        # an impossible evening into the record for good.
        if before is not None:
            delta = min(delta, (now - before).total_seconds() * 1.05)
        banked += _bank(log, name, before, now, delta)

    log['last'] = counters
    log['at'] = world.get('updated') or ''
    if not log['since']:
        log['since'] = log['at']
    _trim(log)
    _write(data_dir, log)
    return len(counters), banked


def _bank(log, name, before, now, seconds):
    """Put one player's seconds into the hours and the day they belong to."""
    window = _slice(before, now) if before is not None else []
    span = sum(piece for _h, _d, piece in window)
    # Always split on the hour, however short the window. A quarter-hour sync
    # produces a window straddling the hour one time in four, and dropping the
    # whole delta on the hour the sample landed in would push those minutes
    # forward every single time - a bias the heatmap would show as a sharp
    # edge on the hour that is an artifact of the sync, not of anybody playing.
    if not window or span <= 0:
        pieces = [(_hour_key(now), _day_key(now), 1.0)]
        span = 1.0
    else:
        pieces = window

    for hour, day, weight in pieces:
        share = seconds * weight / span
        if share <= 0:
            continue
        bucket = _bucket(log, hour)
        bucket['played'] = round(bucket['played'] + share, 1)
        row = bucket['who'].setdefault(name, {'s': 0.0, 'n': 0})
        row['s'] = round(row['s'] + share, 1)
        by_day = log['days'].setdefault(day, {})
        by_day[name] = round(by_day.get(name, 0) + share, 1)
    return seconds


def _read_world(data_dir):
    try:
        with open(os.path.join(data_dir, WORLD)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _trim(log):
    if len(log['hours']) > KEEP_HOURS:
        for key in sorted(log['hours'])[:len(log['hours']) - KEEP_HOURS]:
            del log['hours'][key]
    if len(log['days']) > KEEP_DAYS:
        for key in sorted(log['days'])[:len(log['days']) - KEEP_DAYS]:
            del log['days'][key]


def _write(data_dir, log):
    """Atomically, so a page reading mid-write sees the old file, not half."""
    path = log_path(data_dir)
    part = path + '.part'
    os.makedirs(data_dir, exist_ok=True)
    with open(part, 'w') as fh:
        json.dump(log, fh)
    os.replace(part, path)


# ── what the page reads ──────────────────────────────────────────────────────

def board(data_dir, days=60):
    """The log as the page wants it: hours in UTC, and the recent days.

    The hour buckets are handed over as they are stored rather than rolled up
    here, because rolling them up means choosing a timezone and the only one
    worth choosing belongs to whoever is looking. The page shifts them.
    """
    log = load(data_dir)
    recent = sorted(log['days'])[-days:]
    # only the window the page draws. The log keeps four months; sending all of
    # it with a row per player in every bucket would be most of a megabyte to
    # render a grid that folds down to a single week.
    keep = sorted(log['hours'])[-(days * 24):]
    hours = {key: log['hours'][key] for key in keep}
    return {
        'hours': hours,
        # every player who appears anywhere in the window, so the picker can be
        # built without the page walking every bucket to find the names
        'players': sorted({name for bucket in hours.values()
                           if isinstance(bucket, dict)
                           for name in (bucket.get('who') or {})}),
        'days': [{'day': day,
                  'total': round(sum(log['days'][day].values())),
                  'who': log['days'][day]}
                 for day in recent],
        'since': log.get('since') or '',
        'at': log.get('at') or '',
        # how much is actually in here, so a page a week old can say it is a
        # week old rather than drawing a confident-looking empty grid
        'samples': len(log['hours']),
    }
