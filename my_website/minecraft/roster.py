"""Turn a season's playerdata .dat files into a roster the portal can render.

Each season folder may hold a stats/ directory of <uuid>.dat files copied off
the server. Names and skins come from static/minecraft/skins/players.json,
which tools/fetch_player_skins.py builds from the Mojang API.
"""

import collections
import colorsys
import json
import os

from . import live as live_data
from . import nbt

SKIN_DIR   = '/static/minecraft/skins'
ARMOR_DIR  = '/static/minecraft/armor'
ITEM_DIR   = '/static/minecraft/items'
ARMOR_SLOTS = {103: 'HELMET', 102: 'CHEST', 101: 'LEGS', 100: 'BOOTS'}
# which body part each slot dresses, and which of the two armor sheets carries
# it: layer 2 is the leggings sheet, layer 1 everything else
ARMOR_PARTS = {103: ('head', 'l1'), 102: ('chest', 'l1'),
               101: ('legs', 'l2'), 100: ('feet', 'l1')}
OFFHAND     = -106

# Vanilla caps, used to scale the meters. A modded server can push past these,
# so every bar is clamped rather than assumed to fit.
FOOD_MAX = 20
ARMOR_MAX = 20          # a full set of netherite
TOUGH_MAX = 12

_cache = {}


def humanize(item_id):
    """'dawnera:cooked_dodo' -> ('COOKED DODO', 'dawnera')"""
    if not item_id:
        return None, None
    namespace, _, path = item_id.partition(':')
    if not path:
        namespace, path = 'minecraft', namespace
    return path.replace('_', ' ').upper(), namespace


_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'static', 'minecraft')
PLAYERS_JSON = os.path.join(_STATIC, 'skins', 'players.json')
ARMOR_JSON   = os.path.join(_STATIC, 'armor', 'armor.json')
ITEMS_JSON   = os.path.join(_STATIC, 'items', 'items.json')


def _load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _attribute(data, name, default=0.0):
    """What one of the player's attributes came to, modifiers included.

    The base value and every lasting modifier are stored apart, and the game
    puts them together in a fixed order: the flat additions first, then the
    share of that sum, and last the multipliers on the running total.
    """
    for attr in data.get('Attributes', []):
        if attr.get('Name') != name:
            continue
        modifiers = attr.get('Modifiers') or []
        value = attr.get('Base', default)
        value += sum(m.get('Amount', 0) for m in modifiers if m.get('Operation') == 0)
        value += sum(value * m.get('Amount', 0) for m in modifiers
                     if m.get('Operation') == 1)
        for m in modifiers:
            if m.get('Operation') == 2:
                value *= 1 + m.get('Amount', 0)
        return value
    return default


def _item(entry):
    label, mod = humanize(entry.get('id'))
    return {
        'label': label,
        'mod':   mod,
        'count': entry.get('Count', 1),
        'enchants': len(entry.get('tag', {}).get('Enchantments', [])),
    }


def _worn(by_slot, textures):
    """What to lay over the model, keyed by body part: either a flat armor
    sheet or, for a mod that draws its own armor, a converted model."""
    worn = {}
    for slot, (part, layer) in ARMOR_PARTS.items():
        entry = by_slot.get(slot)
        record = textures.get(entry.get('id'), {}) if entry else {}
        sheet = record.get(layer)
        if sheet:
            worn[part] = {'url': f'{ARMOR_DIR}/{sheet["file"]}',
                          'tw': sheet['w'], 'th': sheet['h']}
        elif record.get('geo'):
            worn[part] = {'model': f'{ARMOR_DIR}/{record["geo"]["file"]}',
                          'slot': record['geo']['slot']}
    return worn


def _defence(by_slot, textures):
    """Armor points and toughness, added up from the pieces being worn.

    A player's save says nothing about either: the game works them out from
    the gear every time it loads them. tools/extract_armor_textures.py reads
    what each piece is worth out of the mod that added it, and the few pieces
    it cannot read leave the total a floor rather than an answer.
    """
    points = tough = 0.0
    whole = True
    for slot in ARMOR_SLOTS:
        entry = by_slot.get(slot)
        if not entry:
            continue
        record = textures.get(entry.get('id')) or {}
        if 'def' not in record:
            whole = False
            continue
        points += record['def']
        tough += record.get('tough', 0)
    return points, tough, whole


# the attributes worth putting first, and what to call them
CORE = ('minecraft:generic.max_health', 'minecraft:generic.armor',
        'minecraft:generic.armor_toughness', 'minecraft:generic.attack_damage',
        'minecraft:generic.attack_speed', 'minecraft:generic.movement_speed',
        'minecraft:generic.knockback_resistance', 'minecraft:generic.luck')


def _pretty(name):
    """'minecraft:generic.max_health' -> ('MAX HEALTH', '') """
    mod, _, rest = name.partition(':')
    rest = rest.split('.')[-1]
    return rest.replace('_', ' ').upper(), '' if mod == 'minecraft' else mod


def _attributes(data):
    """Every attribute the player actually has a value for.

    A modded save carries a hundred of them and most sit at nothing, so the
    ones left at zero are dropped: what is left is what the player earned.
    """
    rows = []
    for attr in data.get('Attributes', []):
        name = attr.get('Name')
        if not name:
            continue
        value = _attribute(data, name)
        if abs(value) < 1e-9 and name not in CORE:
            continue
        label, mod = _pretty(name)
        rows.append({
            'label': label,
            'mod':   mod,
            'value': round(value, 3),
            'core':  name in CORE,
            'rank':  CORE.index(name) if name in CORE else len(CORE),
        })
    rows.sort(key=lambda row: (row['rank'], row['label']))
    return rows


def _carried(inventory, icons):
    """The 36 slots the player carries, in the order the game lays them out."""
    by_slot = {e.get('Slot'): e for e in inventory if 0 <= e.get('Slot', -1) <= 35}
    rows = []
    for slot in list(range(9, 36)) + list(range(9)):
        entry = by_slot.get(slot)
        if not entry:
            rows.append(None)
            continue
        item = _item(entry)
        item['slot'] = slot
        item['hotbar'] = slot < 9
        icon = icons.get(entry.get('id'))
        item['icon'] = f'{ITEM_DIR}/{icon}' if icon else None
        rows.append(item)
    return rows


def read_player(dat_path, uuid, profile, textures, icons=None):
    data = nbt.load(dat_path)

    inventory = data.get('Inventory', [])
    held_slot = data.get('SelectedItemSlot', 0)
    by_slot   = {entry.get('Slot'): entry for entry in inventory}

    worn = _worn(by_slot, textures)
    # shown says whether the model is actually wearing it: a mod that draws its
    # armor with its own 3D model ships no flat sheet for us to lay over the skin
    armor = [{'slot': label, 'shown': ARMOR_PARTS[slot][0] in worn, **_item(by_slot[slot])}
             for slot, label in ARMOR_SLOTS.items() if slot in by_slot]

    # armor and offhand live in the same list as the 36 carried slots
    carried = [e for e in inventory if 0 <= e.get('Slot', -1) <= 35]

    health    = data.get('Health', 0.0)
    # worn gear raises the ceiling too, and none of that is written into the
    # save: the modifiers a mod's armor grants are worked out as it is put on.
    # The game never lets health past the maximum, though, so whatever the
    # player had left is a floor under what their maximum must have been.
    max_health = max(_attribute(data, 'minecraft:generic.max_health', 20.0), health)
    food      = data.get('foodLevel', 0)
    points, tough, whole = _defence(by_slot, textures)
    pos       = [int(round(v)) for v in data.get('Pos', [0, 0, 0])]
    death     = data.get('LastDeathLocation') or {}

    return {
        'uuid':       uuid,
        'name':       profile.get('name', uuid[:8]),
        'slim':       profile.get('slim', False),
        'skin':       f'{SKIN_DIR}/{profile["skin"]}' if profile.get('skin') else None,
        'health':     round(health, 1),
        'max_health': round(max_health, 1),
        'health_pct': min(100, round(health / max_health * 100)) if max_health else 0,
        'absorption': round(data.get('AbsorptionAmount', 0.0), 1),
        'food':       food,
        'food_pct':   min(100, round(food / FOOD_MAX * 100)),
        'defence':    round(points, 1),
        'defence_pct': min(100, round(points / ARMOR_MAX * 100)),
        'toughness':  round(tough, 1),
        'tough_pct':  min(100, round(tough / TOUGH_MAX * 100)),
        # false when a piece's mod keeps its armor value somewhere unreadable
        'defence_whole': whole,
        'level':      data.get('XpLevel', 0),
        'xp':         data.get('XpTotal', 0),
        'xp_pct':     round(data.get('XpP', 0.0) * 100),
        'dimension':  data.get('Dimension', '').split(':')[-1].replace('_', ' ').upper(),
        'pos':        {'x': pos[0], 'y': pos[1], 'z': pos[2]},
        'gamemode':   ['SURVIVAL', 'CREATIVE', 'ADVENTURE', 'SPECTATOR'][data.get('playerGameType', 0)],
        'held':       _item(by_slot[held_slot]) if held_slot in by_slot else None,
        'offhand':    _item(by_slot[OFFHAND]) if OFFHAND in by_slot else None,
        'armor':      armor,
        'worn':       worn,
        'slots_used': len(carried),
        'slots_pct':  round(len(carried) / 36 * 100),
        'effects':    len(data.get('ActiveEffects', [])),
        'died_at':    {'x': death['pos'][0], 'y': death['pos'][1], 'z': death['pos'][2]}
                      if death.get('pos') else None,
        'carried':    _carried(inventory, icons or {}),
        'attributes': _attributes(data),
    }


# ── a player's own colour ──────────────────────────────────────────────────

TONE_BINS = 24                 # fifteen degrees of hue apiece
_tones = {}                    # path, mtime -> the colour read off it


def _tone(path):
    """The one colour a skin is most obviously wearing.

    Not the commonest pixel, which is nearly always the black of an outline
    or the grey between two real colours. Every pixel with a colour worth the
    name is dropped into a bin by hue and the fullest bin wins, scored with
    its neighbours alongside it so a gradient - a skin made of fire runs from
    red through orange to amber - counts as the one colour a reader sees
    rather than being split three ways and losing to a flat patch of
    something else.

    Two things this gets wrong if done the obvious way, both learned from the
    skins on this server: weighting by how vivid a pixel is hands the answer
    to a few bright buckles over the whole suit of dark armour underneath
    them, and capping the brightness to keep white out throws away every
    fully saturated colour there is, since a pure hue is as bright as white.
    Area decides it, and white is kept out by having no saturation at all.
    """
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    held = _tones.get(path)
    if held and held[0] == stamp:
        return held[1]
    try:
        from PIL import Image
        with Image.open(path) as art:
            pixels = list(art.convert('RGBA').getdata())
    except Exception:                                        # noqa: BLE001
        _tones[path] = (stamp, None)
        return None

    fill = collections.defaultdict(int)
    sums = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for red, green, blue, alpha in pixels:
        if alpha < 200:
            continue
        hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        if val < 0.12 or sat < 0.18:      # shadow, outline, and every grey
            continue
        seat = int(hue * TONE_BINS) % TONE_BINS
        fill[seat] += 1
        for i, channel in enumerate((red, green, blue)):
            sums[seat][i] += channel
    if not fill:
        _tones[path] = (stamp, None)
        return None

    score = {seat: n + 0.5 * fill.get((seat - 1) % TONE_BINS, 0)
                     + 0.5 * fill.get((seat + 1) % TONE_BINS, 0)
             for seat, n in fill.items()}
    won = max(score, key=score.get)
    red, green, blue = (c / fill[won] for c in sums[won])
    hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    # A skin is looked at in daylight and this is going on a black chart, so
    # whatever it comes to is brought up to somewhere it can be seen. The hue
    # is what identifies the player; the rest is only legibility.
    red, green, blue = colorsys.hsv_to_rgb(hue, min(1, max(sat, 0.52)),
                                           min(1, max(val, 0.80)))
    found = '#%02x%02x%02x' % (int(red * 255), int(green * 255), int(blue * 255))
    _tones[path] = (stamp, found)
    return found


def faces():
    """uuid -> the head we have on file, for anything that draws a player."""
    out = {}
    for uuid, p in _load_json(PLAYERS_JSON).items():
        skin = f'{SKIN_DIR}/{p["skin"]}' if p.get('skin') else None
        art = os.path.join(_STATIC, 'skins', p['skin']) if p.get('skin') else None
        out[uuid] = {'skin': skin, 'slim': p.get('slim', False),
                     'tone': _tone(art) if art else None}
    return out


def _from_live(uuid, info, profile):
    """A card for someone the server knows about but who has no save here.

    A running season is the usual case: the export lands every minute while the
    playerdata is only copied off by hand. Everything the save would have told
    us is left empty rather than guessed at, and the card leans on what the
    server did send.
    """
    max_health = info['max_health'] or 20.0
    return {
        'uuid':       uuid,
        'name':       info['name'] or profile.get('name', uuid[:8]),
        'slim':       profile.get('slim', False),
        'skin':       f'{SKIN_DIR}/{profile["skin"]}' if profile.get('skin') else None,
        'health':     info['health'],
        'max_health': max_health,
        'health_pct': min(100, round(info['health'] / max_health * 100)),
        'absorption': 0,
        'food':       info['food'],
        'food_pct':   min(100, round(info['food'] / FOOD_MAX * 100)),
        # armor is worn gear, and worn gear only exists in a save
        'defence':    0, 'defence_pct': 0,
        'toughness':  0, 'tough_pct': 0,
        'defence_whole': True,
        'level':      info['level'],
        'xp':         0,
        'xp_pct':     0,
        'dimension':  info['dimension'],
        'pos':        None,
        'gamemode':   'DOWN' if info['dead'] else 'LIVE',
        'held':       None,
        'offhand':    None,
        'armor':      [],
        'worn':       {},
        'slots_used': 0,
        'slots_pct':  0,
        'effects':    0,
        'died_at':    None,
        'carried':    [],
        'attributes': [],
        'live':       info,
    }


def season_roster(season_path):
    """Every player in a season: saved bodies, server records, or both."""
    stats_dir = os.path.join(season_path, 'stats')
    served    = live_data.load(season_path)

    profiles = _load_json(PLAYERS_JSON)
    textures = _load_json(ARMOR_JSON)
    icons    = _load_json(ITEMS_JSON)
    roster   = []
    # the cache key covers the index files and the server export too: re-running
    # either fetcher has to take effect even though no .dat file changed
    profile_stamp = []
    for index in (PLAYERS_JSON, ARMOR_JSON, ITEMS_JSON):
        try:
            profile_stamp.append(os.path.getmtime(index))
        except OSError:
            profile_stamp.append(0)
    profile_stamp = tuple(profile_stamp) + live_data.stamp(season_path)

    for filename in sorted(os.listdir(stats_dir) if os.path.isdir(stats_dir) else []):
        if not filename.endswith('.dat'):
            continue
        uuid = os.path.splitext(filename)[0]
        path = os.path.join(stats_dir, filename)
        stamp = (os.path.getmtime(path), profile_stamp)

        cached = _cache.get(path)
        if cached and cached[0] == stamp:
            roster.append(cached[1])
            continue

        try:
            player = read_player(path, uuid, profiles.get(uuid, {}), textures, icons)
        except Exception:
            continue                       # a corrupt save should not 500 the page
        player['saved'] = stamp[0]
        player['live']  = served.get(uuid)
        _cache[path] = (stamp, player)
        roster.append(player)

    # anyone the server reported who has no save in this season
    seen = {p['uuid'] for p in roster}
    for uuid, info in served.items():
        if uuid not in seen:
            roster.append(_from_live(uuid, info, profiles.get(uuid, {})))

    roster.sort(key=lambda p: p['name'].lower())
    return roster
