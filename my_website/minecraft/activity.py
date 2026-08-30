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

from . import sync
from .live import SERVER_WINDOW

WORLD = 'world_data.json'
LOG = 'activity.json'

# How stale the export may be before the server counts as down: live.SERVER_WINDOW,
# the same 300 seconds behind the ONLINE/OFFLINE badge at the top of the page.
# Imported rather than repeated - two definitions of "down" on one page will
# eventually disagree in front of somebody.

# Downtime under this in a given hour is not drawn at all. A modded server
# restart is a couple of minutes and happens on purpose; painting the grid red
# for one is how the colour stops meaning anything. Five minutes needs two or
# three bad looks in a row at the current sync interval, so a single slow
# export write cannot trigger it either.
DOWN_FLOOR = 5 * 60

# How many hourly buckets to keep. A bucket is no longer a single number - it
# carries a row per player who was on in that hour - so this is shorter than it
# was: four months of them on a nine-player server is a file in the hundreds of
# kilobytes, and the heatmap folds them into a week anyway.
KEEP_HOURS = 24 * 120

# Per-day, per-player totals are kept effectively for ever. A day is one small
# number per player, so a decade of them on a nine-player server is a file
# measured in low hundreds of kilobytes - cheaper than throwing away the only
# record of the season that will exist. Weeks and months are rolled up from
# these on demand rather than stored: a sum of exact numbers is exact, and a
# second copy of the same truth is a second thing to keep in step.
KEEP_DAYS = 366 * 10


def log_path(data_dir):
    return os.path.join(data_dir, LOG)


def _blank():
    return {'hours': {}, 'days': {}, 'downdays': {}, 'profile': {},
            'last': {}, 'at': '', 'since': '', 'downto': ''}


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
    hour.setdefault('down', 0.0)
    if not isinstance(hour.get('who'), dict):
        hour['who'] = {}
    return hour


def load(data_dir):
    """The log, or an empty one. Never raises on a bad file.

    A file that will not parse is set aside rather than read past. This log is
    the only copy of a history that cannot be rebuilt from anywhere - the game
    kept none of it - so the one thing that must not happen is a bad read
    quietly becoming an empty log that the next write then makes permanent.
    Moving it aside costs a filename and keeps the bytes for a later look.
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
    for key, empty in (('hours', {}), ('days', {}), ('downdays', {}),
                      ('profile', {}), ('last', {})):
        if not isinstance(data.get(key), dict):
            data[key] = empty
    data.setdefault('at', '')
    data.setdefault('since', '')
    data.setdefault('downto', '')
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


def lock_path(data_dir):
    return os.path.join(data_dir, '.activity.lock')


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

    # One sampler at a time. A page load starts a pull on a background thread
    # and a scheduled sync runs in its own process, and both end up here; two
    # of them reading the log, adding to it and writing it back will silently
    # drop whichever finished first.
    #
    # Losing a sample to the lock costs nothing, which is what makes giving up
    # the right move rather than waiting: the counters are cumulative and the
    # baseline is whatever was last written, so the next sample measures from
    # there and banks the seconds this one would have.
    with sync.Lock(lock_path(data_dir)) as guard:
        if not guard.held:
            return 0, 0.0
        return _sample(data_dir, world, players)


def _downtime(log, updated, looked):
    """Bank whatever the server has been down for since we last accounted.

    Measured from the export's own timestamp against the wall clock, not from
    our sampling continuity, and that distinction is the whole design:

      * A dead server is exactly a server whose export stops changing. The
        sample below gives up early when the export has not moved, so an
        outage recorded from *our* rhythm would record nothing at all - the
        thing being measured is the thing that stops the measuring.
      * Our own gaps are not the server's. If the website is off for six hours
        while the game is fine, the export comes back fresh and none of it
        counts. If the game was down for four of those six, the export is four
        hours stale and the whole outage is recovered retroactively.

    `downto` is how far the accounting has reached, so an outage spanning many
    samples is banked once rather than once per look.
    """
    if updated is None or looked is None:
        return 0.0
    if (looked - updated).total_seconds() <= SERVER_WINDOW:
        # Writing normally: nothing owed. The ledger catches up to the export's
        # own timestamp rather than to now, because that is the last moment the
        # server is known to have been alive - anything after it is not yet
        # accounted for either way.
        #
        # Advancing to `now` instead would silently eat the start of every
        # outage: a look taken inside the grace period would mark the ledger
        # past the moment the server actually stopped, and those minutes could
        # never be claimed back.
        log['downto'] = updated.isoformat().replace('+00:00', 'Z')
        return 0.0

    # Down since the export stopped moving, which is the truth of it - the
    # grace period is how long we wait before saying so, not when it began.
    since = _when(log.get('downto')) or updated
    start = max(since, updated)
    if start >= looked:
        return 0.0

    banked = 0.0
    for hour, day, seconds in _slice(start, looked):
        bucket = _bucket(log, hour)
        bucket['down'] = round(bucket['down'] + seconds, 1)
        log.setdefault('downdays', {})[day] = round(
            log['downdays'].get(day, 0) + seconds, 1)
        banked += seconds
    log['downto'] = looked.isoformat().replace('+00:00', 'Z')
    return banked


def _sample(data_dir, world, players):
    """One sample, with the lock already held."""

    now = _when(world.get('updated'))
    if now is None:
        return 0, 0.0

    log = load(data_dir)
    before = _when(log.get('at'))

    # Downtime first, and outside the early return below. A server that has
    # stopped writing produces the same export every time we look, which is
    # what that return is for - so anything measured after it would never see
    # an outage at all.
    _downtime(log, now, datetime.now(timezone.utc))

    # the same export twice is not a new sample: the counters in it have not
    # moved, and treating it as one would bank a window with nothing in it
    if before is not None and now <= before:
        _write(data_dir, log)
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
    """Age the detail out, but fold its shape into something permanent first.

    An hour bucket carries a row per player and cannot be kept for ever. What
    can be kept for ever is what those buckets say about the *week*: which hour
    of which weekday the server tends to be alive. So a bucket about to be
    dropped is added into a 168-slot profile on the way out, and the heatmap
    keeps its all-time shape on a file that never grows past 168 rows.

    The profile is keyed by UTC weekday and hour, and a reader sees it shifted
    by their offset today. Old buckets recorded on the other side of a daylight
    saving change therefore land an hour out. That is a real inaccuracy and it
    only touches data older than four months, which is being kept for its shape
    rather than for its minutes.
    """
    stale = sorted(log['hours'])[:max(0, len(log['hours']) - KEEP_HOURS)]
    for key in stale:
        bucket = log['hours'].pop(key)
        when = _when(f'{key}:00:00Z')
        if when is None or not isinstance(bucket, dict):
            continue
        slot = _profile(log, f'{when.weekday()}-{when.hour}')
        slot['played'] = round(slot['played'] + (bucket.get('played') or 0), 1)
        slot['samples'] += bucket.get('samples') or 0
        slot['down'] = round(slot.get('down', 0) + (bucket.get('down') or 0), 1)
        for name, row in (bucket.get('who') or {}).items():
            keep = slot['who'].setdefault(name, {'s': 0.0, 'n': 0})
            keep['s'] = round(keep['s'] + (row.get('s') or 0), 1)
            keep['n'] += row.get('n') or 0

    if len(log['days']) > KEEP_DAYS:
        for key in sorted(log['days'])[:len(log['days']) - KEEP_DAYS]:
            del log['days'][key]
    downdays = log.setdefault('downdays', {})
    if len(downdays) > KEEP_DAYS:
        for key in sorted(downdays)[:len(downdays) - KEEP_DAYS]:
            del downdays[key]


def _profile(log, key):
    slot = log.setdefault('profile', {}).get(key)
    if not isinstance(slot, dict):
        slot = {'played': 0.0, 'samples': 0, 'down': 0.0, 'who': {}}
        log['profile'][key] = slot
    slot.setdefault('played', 0.0)
    slot.setdefault('samples', 0)
    if not isinstance(slot.get('who'), dict):
        slot['who'] = {}
    return slot


def _write(data_dir, log):
    """Atomically, so a page reading mid-write sees the old file, not half.

    The temporary name carries the process id. A shared one is not a temporary
    file at all: two writers land on the same path, and one of them renames it
    out from under the other while that one is still writing into it. The
    result is a log with half of one write and none of the other.
    """
    path = log_path(data_dir)
    part = f'{path}.{os.getpid()}.part'
    os.makedirs(data_dir, exist_ok=True)
    try:
        with open(part, 'w') as fh:
            json.dump(log, fh)
        os.replace(part, path)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise


# ── what the page reads ──────────────────────────────────────────────────────

def _periods(by_day):
    """Per-day totals rolled into days, ISO weeks and calendar months.

    Derived rather than stored. Summing exact per-day numbers gives an exact
    week, and a stored copy would be a second version of the same truth to keep
    in step with the first - which is how a total ends up disagreeing with the
    days it is made of.

    ISO weeks, so a week is Monday to Sunday and the turn of the year does not
    produce a two-day week. The label is what a person would call it.
    """
    out = {'day': {}, 'week': {}, 'month': {}}
    for day, who in by_day.items():
        when = _when(f'{day}T00:00:00Z')
        if when is None:
            continue
        iso = when.isocalendar()
        for scale, key in (('day', day),
                           ('week', f'{iso[0]}-W{iso[1]:02d}'),
                           ('month', day[:7])):
            row = out[scale].setdefault(key, {'total': 0.0, 'who': {}})
            for name, seconds in (who or {}).items():
                if not isinstance(seconds, (int, float)):
                    continue
                row['total'] += seconds
                row['who'][name] = round(row['who'].get(name, 0) + seconds, 1)

    for scale in out:
        out[scale] = [
            {'key': key,
             'total': round(row['total']),
             'who': dict(sorted(row['who'].items(),
                                key=lambda kv: -kv[1]))}
            for key, row in sorted(out[scale].items())]
    return out


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
                  'down': round((log.get('downdays') or {}).get(day, 0)),
                  'who': log['days'][day]}
                 for day in recent],
        # the page draws nothing under this, and gets it from here rather than
        # keeping its own copy of the number
        'down_floor': DOWN_FLOOR,
        # Every day, week and month on record, not just the window the heatmap
        # draws. These are small - one number per player per period - and they
        # are the part worth keeping for the whole season, so they all go.
        'periods': _periods(log['days']),
        # the all-time shape of the week, including hours too old to still be
        # kept in full - see _trim
        'profile': log.get('profile') or {},
        'since': log.get('since') or '',
        'at': log.get('at') or '',
        # how much is actually in here, so a page a week old can say it is a
        # week old rather than drawing a confident-looking empty grid
        'samples': len(log['hours']),
    }
