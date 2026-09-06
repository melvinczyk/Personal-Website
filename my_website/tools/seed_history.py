"""Back-fill history.json with simulated days, so the charts read now.

Run from my_website/:
    python tools/seed_history.py [season5] [--days 14] [--undo]

history.py starts empty and grows a sample at a time, which is correct and
slow: the charts in a player's card have nothing to draw on the day it is
switched on. This writes a plausible past in front of that so the block can
be looked at and judged, and marks every day of it as made up.

What it is NOT is noise. Two things ground it in the record that does exist:

  * activity.json already knows how many seconds each player really played on
    each of the days it covers. Distance is spread in proportion to that, so
    a day somebody did not log in stays empty and a long evening is a tall
    bar. Days before activity's own record get a plausible shape instead.
  * world_data.json knows what each player's counters and gauges are right
    now. The seeded days are carved out of the real totals rather than
    invented on top of them, and the health and armour wander around each
    player's real current values rather than around a guess.

Everything it writes is bounded by `seeded`, the last day that is simulated.
history.py only ever appends days after that, the charts draw anything up to
it faded and hatched, and --undo removes exactly those days and nothing else.
"""

import json
import os
import random
import sys

from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)

# the same short names history.py banks under - imported rather than repeated
sys.path.insert(0, SITE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_website.settings')
from minecraft import history                                   # noqa: E402

# how a day's blocks divide between the ten ways of covering ground, roughly
# as they do in the real totals. Sprinting dominates, and the rest are the
# texture that makes the stack worth stacking.
MIX = {
    'walk': 0.20, 'sprint': 0.52, 'swim': 0.04, 'boat': 0.05, 'climb': 0.02,
    'crouch': 0.03, 'fall': 0.04, 'horse': 0.06, 'elytra': 0.02, 'minecart': 0.02,
}

# what a player's own history is carved out of: this much of their real
# lifetime total is spread across the seeded window, the rest being the season
# they played before it
SHARE = 0.35


def data_dir(season):
    return os.path.join(SITE, 'static', 'minecraft', season, 'data')


def read(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def undo(log):
    """Drop exactly the seeded range and leave everything real."""
    mark = log.get('seeded')
    if not mark:
        return 0
    gone = 0
    for key in [k for k in log['days'] if k <= mark]:
        log['days'].pop(key)
        gone += 1
    for key in [k for k in log['hours'] if k[:10] <= mark]:
        log['hours'].pop(key)
    log.pop('seeded', None)
    return gone


def main(season='season5', days=14, wipe=False):
    folder = data_dir(season)
    log = history.load(folder)

    if wipe:
        gone = undo(log)
        history._write(folder, log)
        print(f'removed {gone} seeded days from {season}')
        return

    if log.get('seeded'):
        print('already seeded - run with --undo first')
        return

    world = read(os.path.join(folder, 'world_data.json'))
    players = world.get('players') or {}
    if not players:
        print('no world_data.json to base a simulation on')
        return
    played = (read(os.path.join(folder, 'activity.json')).get('days')) or {}

    # The window runs up to now rather than stopping short of the real record,
    # because the whole point of seeding is that the charts can be judged
    # before there is a record - and half of the ranges a reader can pick are
    # narrower than a day. Whatever is already in the window is cleared first,
    # so a day is either simulated or sampled and never a mixture of the two.
    now = datetime.now(timezone.utc)
    window = [(now - timedelta(days=n)).strftime('%Y-%m-%d')
              for n in range(days - 1, -1, -1)]
    for key in [k for k in log['days'] if k >= window[0]]:
        log['days'].pop(key)
    for key in [k for k in log['hours'] if k[:10] >= window[0]]:
        log['hours'].pop(key)

    rng = random.Random(f'{season}:{window[0]}')
    seeded_days = 0

    for name, raw in players.items():
        if not isinstance(raw, dict):
            continue
        # how much of the window this player was actually about for, from the
        # real activity log where it reaches and a plausible shape where not
        weights = {}
        for day in window:
            real = (played.get(day) or {}).get(name)
            weights[day] = float(real) if isinstance(real, (int, float)) \
                else (0.0 if rng.random() < 0.25 else rng.uniform(1800, 21600))
        total_weight = sum(weights.values()) or 1.0

        far = sum(float(raw.get(field) or 0) for field in
                  ('walkBlocks', 'sprintBlocks', 'swimBlocks', 'boatBlocks',
                   'climbBlocks', 'crouchBlocks', 'fallBlocks', 'horseBlocks',
                   'elytraBlocks', 'minecartBlocks')) * SHARE

        hp_max = float(raw.get('maxHealth') or 20)
        armour = float(((raw.get('attributes') or {}).get('armor')) or 0)

        for day in window:
            share = weights[day] / total_weight
            if share <= 0:
                continue
            row = history._day_player(log, day, name)
            spent = {}
            for kind, part in MIX.items():
                blocks = far * share * part * rng.uniform(0.6, 1.4)
                if blocks >= 1:
                    row[kind] = round(blocks, 1)
                    spent[kind] = blocks
            seeded_days += 1

            # the hours they were on, and what their levels did through them.
            # Armour steps rather than drifts - it only changes when gear
            # does - and health wanders with a low under it, which is the
            # reading the chart exists for.
            hours = max(1, min(10, int(weights[day] / 3600)))
            start = rng.randint(13, 22)
            # today only runs as far as the clock has: seeding hours that have
            # not happened yet would draw a future
            if day == window[-1]:
                start = max(0, min(start, now.hour - hours + 1))
            # the day's distance divided over the hours they were on, so the
            # chart says the same thing whichever grain it is asked at
            slices = [rng.uniform(0.5, 1.5) for _ in range(hours)]
            weightsum = sum(slices) or 1.0
            for n in range(hours):
                when = datetime.strptime(day, '%Y-%m-%d').replace(
                    tzinfo=timezone.utc) + timedelta(hours=start + n)
                if when > now:
                    break
                went = history._hour(log, history._hour_key(when),
                                     name).setdefault('m', {})
                for kind, blocks in spent.items():
                    part = blocks * slices[n] / weightsum
                    if part >= 1:
                        went[kind] = round(went.get(kind, 0.0) + part, 1)
                if rng.random() < 0.12:
                    armour = max(0.0, armour + rng.choice((-6, -3, 3, 6, 9)))
                hp = max(1.0, hp_max * rng.uniform(0.35, 1.0))
                low = max(1.0, hp * rng.uniform(0.35, 0.95))
                history._mark(log, name, when, {
                    'hp': round(hp, 1), 'hpmax': hp_max,
                    'food': float(rng.randint(6, 20)),
                    'level': float(raw.get('xpLevel') or 0),
                    'armor': round(armour, 2),
                    'tough': float(((raw.get('attributes') or {})
                                    .get('armor_toughness')) or 0),
                    'attack': float(((raw.get('attributes') or {})
                                     .get('attack_damage')) or 0),
                })

    log['seeded'] = window[-1]
    if not log.get('since'):
        log['since'] = window[0] + 'T00:00:00.000Z'
    history._write(folder, log)
    print(f'seeded {len(window)} days ({window[0]} .. {window[-1]}) '
          f'across {len(players)} players, {seeded_days} player-days')
    print('the charts draw everything up to and including '
          f'{log["seeded"]} as simulated; --undo removes exactly that')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    n = 14
    if '--days' in sys.argv:
        n = int(sys.argv[sys.argv.index('--days') + 1])
    main(args[0] if args else 'season5', n, '--undo' in sys.argv)
