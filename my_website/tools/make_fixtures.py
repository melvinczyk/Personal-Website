"""Local dev fixtures for the live season's data folder.

season5/data/ is gitignored and written by the sync worker on a real deploy;
locally there is no worker, so the live stage has nothing to read. This
writes a plausible snapshot of every file live.py/chat.py/activity.py expect,
so the portal can be previewed without a game server.

Run from my_website/:  python tools/make_fixtures.py
"""
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'season5', 'data')
os.makedirs(DATA, exist_ok=True)

NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat().replace('+00:00', 'Z')


def write(name, payload):
    path = os.path.join(DATA, name)
    with open(path, 'w') as fh:
        json.dump(payload, fh, indent=1)
    print(f'wrote {path}')


PLAYERS = [
    ('melvin0czyk',     '02433a22-8588-4003-bae0-9deded0cde52'),
    ('mysteriousmex21', '1c7c89c8-3d83-456a-a3fe-6933ab1d2cd0'),
    ('Hey_Zeus77',      'cade3f4e-f148-44ca-a8ee-9355768329cf'),
    ('blindhustler',    '8c3c2ce5-c48e-40e3-99fd-a6d83fba4d40'),
    ('st_kip',          '751208c0-4d61-4292-a3e5-f1e1f0c7d0f2'),
    ('DonMonk141414',   '0761957b-8af9-4f17-8dd7-e7800ff9f9af'),
    ('Zerobarbecue117', '6694d52c-0985-4a24-9789-05df23c45059'),
    ('FastboiOG',       '89e6e4f8-a399-4e23-8e56-d104f5b38e20'),
]

# ── world_data.json ──────────────────────────────────────────────────────────

MOB_KILLS = ['minecraft:zombie', 'minecraft:skeleton', 'minecraft:spider',
             'minecraft:creeper', 'minecraft:enderman', 'minecraft:witch']
MOB_DEATHS = ['minecraft:zombie', 'minecraft:creeper', 'minecraft:fall',
              'minecraft:drowned', 'minecraft:lava']

# Pulled straight off the real server's own world_data.json, a few minutes
# into the same restart - now with dimensionDetail, which is where the
# Twilight Forest and Aether's own weather comes from (see live.py's
# _dim_weather - the nether, the end and the rest never roll any).
REAL_WORLD = {
    'updated': '2026-09-01T16:13:25.601Z',
    'tickCount': 1199,
    'uptimeSeconds': 60,
    'time': {'day': 336, 'timeOfDay': 4151, 'clock': '10:09', 'isDay': True,
              'phase': 'day', 'gameTime': 7464219, 'moonPhase': 0},
    'weather': {'raining': False, 'thundering': False, 'state': 'clear',
                 'forecast': {'rainChangeTicks': 4265, 'rainChangeSeconds': 213,
                              'thunderChangeTicks': 4265, 'thunderChangeSeconds': 213,
                              'clearLocked': False, 'clearLockedTicks': 0,
                              'clearLockedSeconds': 0}},
    'difficulty': 'HARD',
    'spawn': {'x': 0, 'y': 72, 'z': 0},
    # the solar-term calendar that replaced Serene Seasons outright - 24 named
    # terms, two to a sub-season, each lasting lastingDaysOfEachTerm days
    'season': {'enabled': True, 'season': 'autumn', 'subSeason': 'early_autumn',
                'solarTerm': 'beginning_of_autumn', 'gregorianMonth': 'month_8',
                'gregorianYear': 1, 'solarYear': 1, 'solarDays': 87,
                'dayInTerm': 3, 'lastingDaysOfEachTerm': 7,
                'termProgress': 0.43, 'daysUntilNextTerm': 4,
                'hasLocalWeather': True},
    'invasions': {'invasionTime': 8064000, 'xpMultiplier': 0, 'active': None},
    'online': {'count': 0, 'max': 20, 'names': []},
    'dimensionDetail': [
        {'id': 'minecraft:overworld', 'loadedChunks': 2209, 'forcedChunks': 1,
         'entities': 369, 'players': 0, 'dayTime': 4151, 'raining': False, 'thundering': False},
        {'id': 'aquamirae:the_maelstrom', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': True, 'thundering': False},
        {'id': 'aether:the_aether', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 18217, 'raining': False, 'thundering': False},
        {'id': 'roaring:dark_world', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': False, 'thundering': False},
        {'id': 'minecraft:the_end', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': False, 'thundering': False},
        {'id': 'graveyard:past', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': False, 'thundering': False},
        {'id': 'twilightforest:twilight_forest', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': True, 'thundering': False},
        {'id': 'minecraft:the_nether', 'loadedChunks': 0, 'forcedChunks': 0,
         'entities': 0, 'players': 0, 'dayTime': 4151, 'raining': False, 'thundering': False},
    ],
    'dimensions': ['minecraft:overworld', 'aquamirae:the_maelstrom', 'aether:the_aether',
                   'roaring:dark_world', 'minecraft:the_end', 'graveyard:past',
                   'twilightforest:twilight_forest', 'minecraft:the_nether'],
}

# nobody is back on the server yet in this snapshot - the restart is thirty
# seconds old - so every player reads as last seen rather than online
online_flags = [False] * len(PLAYERS)

players_raw = {}
online_names = []
for i, (name, uuid) in enumerate(PLAYERS):
    online = online_flags[i]
    recorded = NOW - timedelta(seconds=random.randint(5, 90)) if online \
        else NOW - timedelta(hours=random.randint(2, 30))
    if online:
        online_names.append(name)
    hours = round(random.uniform(4, 60), 2)
    seconds = int(hours * 3600)
    dead = (i == 4)  # st_kip, same as the last real snapshot on record
    killed = {mob: random.randint(0, 180) for mob in random.sample(MOB_KILLS, 4)}
    killed_by = {mob: random.randint(0, 12) for mob in random.sample(MOB_DEATHS, 3)}
    players_raw[name] = {
        'name': name,
        'uuid': uuid,
        'health': 0.0 if dead else round(random.uniform(8, 20), 1),
        'maxHealth': 20.0,
        'food': 0.0 if dead else round(random.uniform(10, 20), 1),
        'xpLevel': random.randint(0, 30),
        'dimension': random.choice([
            'minecraft:overworld', 'minecraft:overworld', 'minecraft:overworld',
            'minecraft:the_nether', 'twilightforest:twilight_forest',
        ]) if not dead else None,
        'playTimeTicks': seconds * 20,
        'playTimeSeconds': seconds,
        'playTimeHours': round(seconds / 3600, 2),
        'deaths': random.randint(2, 90),
        'mobKills': random.randint(30, 700),
        'playerKills': random.randint(0, 2),
        'damageDealt': random.randint(2000, 150000),
        'damageTaken': random.randint(1500, 90000),
        'jumps': random.randint(400, 20000),
        'timeSinceDeath': random.randint(0, 200000),
        'walkBlocks': round(random.uniform(2000, 80000), 1),
        'sprintBlocks': round(random.uniform(1000, 55000), 1),
        'swimBlocks': round(random.uniform(50, 5000), 1),
        'recorded': iso(recorded),
        'statsRecorded': iso(NOW),
        'stats': {'killed': killed, 'killedBy': killed_by},
    }

world_data = {
    'updated': REAL_WORLD['updated'],
    'players': players_raw,
    'world': {**REAL_WORLD, 'performance': {'tps': 19.8, 'mspt': 12.4}},
}
write('world_data.json', world_data)

# ── boss_kills.json / boss_fights.json ──────────────────────────────────────

WEAPONS = ['simplyswords:diamond_halberd', 'minecraft:netherite_sword',
           'simplyswords:runic_greatsword', 'minecraft:trident']

# (player, boss id, category key, tier, fights: list of participant shares)
FIGHTS_PLAN = [
    ('melvin0czyk', 'dungeonnowloading:fairkeeper_boros', 'bosses', 3,
     [{'melvin0czyk': 0.62, 'Zerobarbecue117': 0.30}]),
    ('melvin0czyk', 'dungeonnowloading:fairkeeper_ouros', 'bosses', 3,
     [{'melvin0czyk': 0.91}]),
    ('melvin0czyk', 'legendary_monsters:skeletosaurus', 'minibosses', 1,
     [{'melvin0czyk': 1.0}]),
    ('Zerobarbecue117', 'illagerinvasion:invoker', 'minibosses', 2,
     [{'Zerobarbecue117': 0.87}, {'Zerobarbecue117': 0.55, 'blindhustler': 0.40}]),
    ('Zerobarbecue117', 'wkcr:king', 'minibosses', 2,
     [{'Zerobarbecue117': 0.70, 'DonMonk141414': 0.25}]),
    ('Zerobarbecue117', 'arkane_domains:warlock', 'bosses', 2,
     [{'Zerobarbecue117': 0.48, 'mysteriousmex21': 0.44}]),
    ('mysteriousmex21', 'minecraft:evoker', 'minibosses', 1,
     [{'mysteriousmex21': 1.0}]),
    ('blindhustler', 'wkcr:king', 'minibosses', 2,
     [{'blindhustler': 0.66, 'Zerobarbecue117': 0.30}]),
]

CATALOGUE = {}
for path in ('bosses/index.json', 'minibosses/index.json'):
    with open(os.path.join(os.path.dirname(HERE), 'static', 'minecraft', path)) as fh:
        for e in json.load(fh):
            CATALOGUE[e['id']] = e

kills = {}
fights = {}
fight_start = NOW - timedelta(days=6)

for finisher, boss_id, cat, tier, fight_list in FIGHTS_PLAN:
    entry = CATALOGUE.get(boss_id, {})
    boss_fights = fights.setdefault(boss_id, [])
    total_kills_by_player = {}
    last_time = None
    for n, shares in enumerate(fight_list):
        when = fight_start + timedelta(days=n * 2, hours=random.randint(0, 20))
        last_time = when
        max_health = float(random.choice([200, 300, 400, 600, 1000]))
        duration = random.randint(45, 260)
        finisher_name = max(shares, key=shares.get)
        discarded = round(max_health * (1 - sum(shares.values())), 1)
        participants = {name: {'damage': round(max_health * share, 1), 'share': share}
                         for name, share in shares.items()}
        boss_fights.append({
            'time': iso(when),
            'maxHealth': max_health,
            'threshold': 20.0,
            'durationSeconds': float(duration),
            'discardedDamage': max(discarded, 0),
            'finisher': finisher_name,
            'finisherWeapon': random.choice(WEAPONS),
            'participants': participants,
        })
        for name in shares:
            total_kills_by_player[name] = total_kills_by_player.get(name, 0) + \
                (1 if name == finisher_name else 0)

    for name, n_kills in total_kills_by_player.items():
        if n_kills <= 0:
            continue
        uuid = dict(PLAYERS).get(name, name)
        record = kills.setdefault(name, {'uuid': uuid, 'bossesDefeated': 0,
                                         'totalKills': 0, 'bosses': {}, 'minibosses': {}})
        record[cat][boss_id] = {
            'name': entry.get('name') or boss_id.split(':')[-1],
            'tier': tier,
            'first': iso(fight_start),
            'kills': n_kills,
            'last': iso(last_time),
            'lastDamage': boss_fights[-1]['participants'].get(name, {}).get('damage', 0),
            'lastShare': boss_fights[-1]['participants'].get(name, {}).get('share', 0),
        }

for name, record in kills.items():
    record['totalKills'] = sum(b['kills'] for b in record['bosses'].values()) + \
        sum(b['kills'] for b in record['minibosses'].values())
    record['bossesDefeated'] = len(record['bosses']) + len(record['minibosses'])

write('boss_kills.json', kills)
write('boss_fights.json', fights)

# ── fieldguide_counts.json ──────────────────────────────────────────────────

fieldguide = {}
for name, uuid in PLAYERS:
    monster = random.randint(10, 48)
    animal = random.randint(8, 30)
    plant = random.randint(5, 22)
    boss = random.randint(0, 12)
    intro = 6
    fieldguide[name] = {
        'total': monster + animal + plant + boss + intro,
        'categories': {'monster': monster, 'animal': animal, 'plant': plant,
                       'boss': boss, 'intro': intro},
    }
write('fieldguide_counts.json', fieldguide)

# ── fish_caught.json ─────────────────────────────────────────────────────────

with open(os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'fish', 'index.json')) as fh:
    FISH = json.load(fh)

anglers = {
    'melvin0czyk': ['starcatcher:aurora', 'starcatcher:vesani'],
    'Zerobarbecue117': ['starcatcher:cerberay'],
    'blindhustler': ['starcatcher:boreal', 'starcatcher:lush_pike', 'minecraft:nether_star'],
    'mysteriousmex21': ['starcatcher:ward'],
}

fish_players = {}
for name, ids in anglers.items():
    uuid = dict(PLAYERS)[name]
    rows = {}
    for fid in ids:
        spec = next((f for f in FISH if f['id'] == fid), None)
        if not spec:
            continue
        caught_at = NOW - timedelta(days=random.randint(1, 20))
        rows[fid] = {
            'count': random.randint(1, 4),
            'firstCatch': int(caught_at.timestamp()),
            'bestPercentile': round(random.uniform(0.2, 8.0), 1),
            'bestSizeCm': round(spec['size'] * random.uniform(0.8, 1.15)),
            'bestWeightG': round(spec['weight'] * random.uniform(0.8, 1.2)),
            'golden': random.random() < 0.15,
            'perfect': random.random() < 0.08,
        }
    fish_players[name] = {
        'name': name, 'uuid': uuid,
        'totalCaught': sum(r['count'] for r in rows.values()) + random.randint(20, 90),
        'caught': len(rows) + random.randint(5, 15),
        'legendaryCaught': len(rows),
        'fish': rows,
    }

write('fish_caught.json', {'rarities': ['legendary'], 'players': fish_players})

# ── chat_history.json ───────────────────────────────────────────────────────

LINES = [
    "anyone want to hit the twilight forest boss", "gg on the fairkeeper fight",
    "does anyone have spare netherite", "watch out there's a warlock camp near spawn",
    "lol i fell in lava again", "finally got a legendary fish!!", "who's got the map open",
    "brb dying to a creeper probably", "new boss dropped some good loot",
    "can someone tp me to base", "nice pull on that cerberay", "server feels smooth today",
    "anyone selling emeralds", "the mid autumn skin on the calendar is nice",
    "anyone seen the king miniboss yet", "anyone up for a boss run tonight",
]

messages = []
seq = 0
t = NOW - timedelta(minutes=random.randint(5, 40))
for i in range(18):
    name, uuid = random.choice(PLAYERS)
    seq += 1
    messages.append({'at': iso(t), 'name': name, 'uuid': uuid,
                      'text': random.choice(LINES), 'seq': seq})
    t += timedelta(seconds=random.randint(20, 240))

chat_history = {'seq': seq, 'updated': iso(t), 'checked': time.time(), 'messages': messages}
write('chat_history.json', chat_history)

# ── activity.json ────────────────────────────────────────────────────────────

hours = {}
days = {}
downdays = {}
last = {}
since = NOW - timedelta(days=14)

day_cursor = since
while day_cursor <= NOW:
    weekday = day_cursor.weekday()
    day_key = day_cursor.strftime('%Y-%m-%d')
    day_total = {}
    for hour in range(24):
        stamp = day_cursor.replace(hour=hour, minute=0, second=0, microsecond=0)
        if stamp > NOW:
            continue
        # busier on weekend evenings, quiet overnight
        base = 0.05
        if 17 <= hour <= 23:
            base = 0.55 if weekday >= 4 else 0.35
        elif 12 <= hour < 17:
            base = 0.25
        if random.random() > base:
            continue
        who = {}
        n_players = random.randint(1, min(4, len(PLAYERS)))
        for name, _uuid in random.sample(PLAYERS, n_players):
            secs = round(random.uniform(300, 3200), 1)
            who[name] = {'s': secs, 'n': random.randint(1, 3)}
            day_total[name] = round(day_total.get(name, 0) + secs, 1)
        played = round(sum(v['s'] for v in who.values()), 1)
        hours[stamp.strftime('%Y-%m-%dT%H')] = {
            'played': played, 'samples': random.randint(1, 4),
            'down': 0.0, 'who': who,
        }
    if day_total:
        days[day_key] = day_total
    day_cursor += timedelta(days=1)

# one short, unremarkable outage a few days back
outage_day = (NOW - timedelta(days=3)).strftime('%Y-%m-%d')
downdays[outage_day] = 640.0

for name, uuid in PLAYERS:
    last[name] = players_raw[name]['playTimeSeconds']

activity = {
    'hours': hours, 'days': days, 'downdays': downdays, 'profile': {},
    'last': last, 'at': iso(NOW), 'since': iso(since),
    'downto': iso(NOW - timedelta(hours=1)),
}
write('activity.json', activity)

print('\ndone.')
