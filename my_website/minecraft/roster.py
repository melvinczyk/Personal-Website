"""Turn a season's playerdata .dat files into a roster the gallery can render.

Each season folder may hold a stats/ directory of <uuid>.dat files copied off
the server. Names and skins come from static/minecraft/skins/players.json,
which tools/fetch_player_skins.py builds from the Mojang API.
"""

import json
import os

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


def season_roster(season_path):
    """Every player with a .dat in <season>/stats, newest save first."""
    stats_dir = os.path.join(season_path, 'stats')
    if not os.path.isdir(stats_dir):
        return []

    profiles = _load_json(PLAYERS_JSON)
    textures = _load_json(ARMOR_JSON)
    icons    = _load_json(ITEMS_JSON)
    roster   = []
    # the cache key covers the two index files too: re-running either fetcher
    # has to take effect even though the .dat files themselves never changed
    profile_stamp = []
    for index in (PLAYERS_JSON, ARMOR_JSON, ITEMS_JSON):
        try:
            profile_stamp.append(os.path.getmtime(index))
        except OSError:
            profile_stamp.append(0)
    profile_stamp = tuple(profile_stamp)

    for filename in sorted(os.listdir(stats_dir)):
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
        _cache[path] = (stamp, player)
        roster.append(player)

    roster.sort(key=lambda p: p['name'].lower())
    return roster
