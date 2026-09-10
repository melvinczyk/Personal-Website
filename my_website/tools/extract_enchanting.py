"""Pull Apotheosis' enchanting module out of the game's own files.

Run from my_website/:
    python tools/extract_enchanting.py ["<path to a pack instance>"]

Sibling of extract_apotheosis.py, which does the same job for reforging and
gem socketing. The asset walk, the layer merge and the pack discovery are all
imported from it rather than copied - the two extractors read the same jars in
the same order and differ only in what they take out of them.

Where the numbers come from
---------------------------
Three sources, and it matters which is which:

  1. **Datapack json** - the enchanting stats of every block (data/apotheosis/
     enchanting_stats/) and the infusion recipes (data/apotheosis/recipes/
     enchanting/). These are data, they are merged across our packs the same
     way the game merges them, and our overrides win. One of ours matters: the
     Superior Sigil of Socketing's infusion recipe is switched off outright
     with a forge:false condition, so on this server that item has no infusion
     at all - and a page that read only the mod would say otherwise.

  2. **config/apotheosis/enchantments.cfg** - the per-enchantment table: max
     level, max loot level, rarity, and the treasure/discoverable/lootable/
     tradeable flags. This is a config file rather than a datapack, so it is
     parsed out of the instance directly. Every max level on this pack is the
     mod's raised value, not vanilla's - Protection goes to 8, Feather Falling
     to 11 - which is the single most useful thing this page can say.

  3. **The mod's own bytecode** - the enchanting maths. None of it is data:
     the slot level bands, the quanta distribution, the arcana weight ladder
     and the extra-enchantment loop are all constants in RealEnchantmentHelper
     and ApothEnchantmentMenu$Arcana. They were read out with javap and are
     written down in CONSTANTS and ARCANA below, with the method each one came
     from named beside it, because a number you cannot trace is a number
     nobody can check.

What it writes
--------------
    static/minecraft/apotheosis/enchanting.json
    static/minecraft/apotheosis/icons/*.png   (shared with the forge's icons)
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from extract_apotheosis import (           # noqa: E402
    APOTH_JAR, AR_JAR, ATTR_JAR, INSTANCES, VANILLA_JARS, PACKS, LAYERED,
    Assets, Layers, ICON_DIR, OUT_DIR,
)

# ── the maths, read out of the jar with javap ────────────────────────────────
#
# Every one of these is a literal in the mod's code rather than anything a
# datapack can reach, so each carries the method it was read from.

CONSTANTS = {
    # EnchantingStatRegistry.absoluteMaxEterna. 50 is only the field's
    # *initialiser*; computeAbsoluteMaxEterna overwrites it on every datapack
    # reload with the largest maxEterna in the whole enchanting_stats
    # registry. So this is a floor to fall back on, not the answer - the real
    # value is worked out from the blocks below and written over this one, and
    # power_ceiling with it. On this pack the two agree, because the Draconic
    # Endshelf's ceiling is exactly 50; on a pack that adds a higher shelf
    # they would not, and every power number on the page would be wrong.
    'max_eterna': 50.0,
    # RealEnchantmentHelper.getEnchantmentCost: maxLevel = round(eterna * 2).
    # "Each point of Eterna increases the maximum enchanting level by two."
    'levels_per_eterna': 2,
    # ...and the same method clamps the *modified* power to maxEterna * 4.
    'power_ceiling': 200,
    # getEnchantmentCost again. Slot 2 (the third) returns maxLevel outright;
    # the other two roll uniformly inside a band of it:
    #   min = 0.6 - 0.4 * (1 - slot),  max = 0.8 - 0.4 * (1 - slot)
    'slot_bands': [
        {'min': 0.2, 'max': 0.4},
        {'min': 0.6, 'max': 0.8},
        {'min': 1.0, 'max': 1.0, 'exact': True},
    ],
    # RealEnchantmentHelper.getQuantaFactor(rand, quanta, rectification):
    #   f = clamp(gaussian() / 3, -1, 1)
    #   r = rectification / 100
    #   if (f < r - 1) f = uniform(r - 1, 1)
    #   return quanta * f / 100
    # and the caller uses (1 + that) as the multiplier on the base power.
    'quanta_gaussian_divisor': 3,
    # RealEnchantmentHelper.selectEnchantment's tail, the vanilla extra-roll
    # loop with Apotheosis' cap on it:
    #   int n = modifiedPower;
    #   if (n > 45) n = (int) (basePower * 1.15f);
    #   while (rand.nextInt(50) <= n) { pick(); n /= 2; }
    'extra_roll_die': 50,
    'extra_roll_cap': 45,
    'extra_roll_scale': 1.15,
    # The book's Enchanting Stats chapter, on arcana: "At 25% you will always
    # receive at least two enchantments. At 75%, three."
    'arcana_guarantee_two': 25,
    'arcana_guarantee_three': 75,
    # ApothEnchantmentMenu$TableStats$Builder's constructor, which is where a
    # bare table's stats actually come from. It is not zeroes:
    #     Builder(int enchantmentValue) {
    #         addQuanta(15.0f);
    #         addArcana(enchantmentValue / 2.0f);
    #         addClues(1);
    #     }
    # So every table starts with fifteen quanta and one clue before a single
    # shelf is placed - and the item's enchantability feeds ARCANA, not eterna.
    # The mod's own book says only "is increased by 50% of an item's
    # enchantability" with the stat's name inside a formatting macro; the
    # bytecode is the thing that says which stat.
    'base_quanta': 15.0,
    'base_clues': 1,
    'enchantability_to_arcana': 0.5,
    # Builder.build(): eterna is not one sum against one ceiling. Blocks are
    # bucketed by their own maxEterna, the buckets are walked in ascending
    # order of cap, and each capped bucket clamps the running total to its own
    # cap (buckets with no cap add freely):
    #     for (entry : sortedByCapAscending)
    #         total = entry.cap > 0 ? min(entry.cap, total + entry.sum)
    #                               : total + entry.sum;
    # Which is why twenty dormant deepshelves and one draconic endshelf give
    # 25 rather than 30: the deepshelves' own ceiling throws the excess away
    # before the endshelf's higher ceiling is ever considered.
    'eterna_buckets_by_cap': True,
}

# ApothEnchantmentMenu$Arcana, from the enum's static initialiser. Each tier
# is a threshold and the four rarity weights that apply at or above it, in
# registry order: common, uncommon, rare, very rare. The ladder inverts as it
# climbs, which is the whole point of the stat.
ARCANA = [
    {'name': 'EMPTY',  'threshold': 0,  'weights': [10, 5, 2, 1]},
    {'name': 'LITTLE', 'threshold': 10, 'weights': [8, 5, 3, 1]},
    {'name': 'FEW',    'threshold': 20, 'weights': [7, 5, 4, 2]},
    {'name': 'SOME',   'threshold': 30, 'weights': [5, 5, 4, 2]},
    {'name': 'LESS',   'threshold': 40, 'weights': [5, 5, 4, 3]},
    {'name': 'MEDIUM', 'threshold': 50, 'weights': [5, 5, 5, 5]},
    {'name': 'MORE',   'threshold': 60, 'weights': [3, 4, 5, 5]},
    {'name': 'VALUE',  'threshold': 70, 'weights': [2, 4, 5, 5]},
    {'name': 'EXTRA',  'threshold': 80, 'weights': [2, 4, 5, 7]},
    {'name': 'ALMOST', 'threshold': 90, 'weights': [1, 3, 5, 8]},
    {'name': 'MAX',    'threshold': 99, 'weights': [1, 2, 5, 10]},
]

RARITIES = ['COMMON', 'UNCOMMON', 'RARE', 'VERY_RARE']

# -- what power each enchantment needs ---------------------------------------
#
# Apotheosis does not use vanilla's cost window. EnchantmentInfo's single-arg
# constructor - the one every enchantment here gets, because every Min/Max
# Power Function in enchantments.cfg is blank - builds its own pair:
#
#   defaultMax = level -> (int)(getAbsoluteMaxEterna() * 4)      // a flat 200
#   defaultMin = level -> {
#       if (level > ench.getMaxLevel() && level > 1) {
#           int step = ench.getMinCost(max) - ench.getMinCost(max - 1);
#           if (step == 0) step = 15;
#           return ench.getMinCost(level)
#                + step * (int)Math.pow(level - ench.getMaxLevel(), 1.6);
#       }
#       return ench.getMinCost(level);
#   }
#
# Two things follow, and both matter. There is no upper bound any more: max
# power is 200 for everything, so an enchantment stays in the pool once you
# can afford it rather than dropping out again the way it does in vanilla.
# And the levels Apotheosis adds past an enchantment's natural maximum cost
# *superlinearly* - the 1.6 exponent - which is why Protection VIII wants 177
# power rather than the 78 a straight line would ask for.
#
# So each entry below is vanilla's own getMinCost as (a, b) evaluated a + b*L,
# plus `vmax`, the enchantment's natural maximum level, which is where the
# extrapolation starts. The curves are transcribed - the vanilla jar is
# obfuscated and cannot be read the way the Apotheosis constants were.
VANILLA_COSTS = {
    'minecraft:protection':            {'min': [-10, 11], 'vmax': 4},
    'minecraft:fire_protection':       {'min': [2, 8],    'vmax': 4},
    'minecraft:feather_falling':       {'min': [-1, 6],   'vmax': 4},
    'minecraft:blast_protection':      {'min': [-3, 8],   'vmax': 4},
    'minecraft:projectile_protection': {'min': [-3, 6],   'vmax': 4},
    'minecraft:respiration':           {'min': [0, 10],   'vmax': 3},
    'minecraft:aqua_affinity':         {'min': [1, 0],    'vmax': 1},
    'minecraft:thorns':                {'min': [-10, 20], 'vmax': 3},
    'minecraft:depth_strider':         {'min': [0, 10],   'vmax': 3},
    'minecraft:frost_walker':          {'min': [0, 10],   'vmax': 2},
    'minecraft:binding_curse':         {'min': [25, 0],   'vmax': 1},
    'minecraft:soul_speed':            {'min': [0, 10],   'vmax': 3},
    'minecraft:swift_sneak':           {'min': [0, 25],   'vmax': 3},
    'minecraft:sharpness':             {'min': [-10, 11], 'vmax': 5},
    'minecraft:smite':                 {'min': [-3, 8],   'vmax': 5},
    'minecraft:bane_of_arthropods':    {'min': [-3, 8],   'vmax': 5},
    'minecraft:knockback':             {'min': [-15, 20], 'vmax': 2},
    'minecraft:fire_aspect':           {'min': [-10, 20], 'vmax': 2},
    'minecraft:looting':               {'min': [6, 9],    'vmax': 3},
    'minecraft:sweeping':              {'min': [-4, 9],   'vmax': 3},
    'minecraft:efficiency':            {'min': [-9, 10],  'vmax': 5},
    'minecraft:silk_touch':            {'min': [15, 0],   'vmax': 1},
    'minecraft:unbreaking':            {'min': [-3, 8],   'vmax': 3},
    'minecraft:fortune':               {'min': [6, 9],    'vmax': 3},
    'minecraft:power':                 {'min': [-9, 10],  'vmax': 5},
    'minecraft:punch':                 {'min': [-8, 20],  'vmax': 2},
    'minecraft:flame':                 {'min': [20, 0],   'vmax': 1},
    'minecraft:infinity':              {'min': [20, 0],   'vmax': 1},
    'minecraft:luck_of_the_sea':       {'min': [6, 9],    'vmax': 3},
    'minecraft:lure':                  {'min': [6, 9],    'vmax': 3},
    'minecraft:loyalty':               {'min': [5, 7],    'vmax': 3},
    'minecraft:impaling':              {'min': [-7, 8],   'vmax': 5},
    'minecraft:riptide':               {'min': [10, 7],   'vmax': 3},
    'minecraft:channeling':            {'min': [25, 0],   'vmax': 1},
    'minecraft:multishot':             {'min': [20, 0],   'vmax': 1},
    'minecraft:quick_charge':          {'min': [-8, 20],  'vmax': 3},
    'minecraft:piercing':              {'min': [-9, 10],  'vmax': 4},
    'minecraft:mending':               {'min': [0, 25],   'vmax': 1},
    'minecraft:vanishing_curse':       {'min': [25, 0],   'vmax': 1},
}

# The curve an enchantment that overrides nothing gets. Enchantment's own base
# class is
#     getMinCost(level) { return 1 + level * 10; }
# and a modded enchantment that never overrides it uses exactly that - which
# is a great many of them. It is still an assumption per enchantment rather
# than a reading, so everything using it is flagged `assumed` and the page
# marks those rows rather than passing them off as measured.
BASE_CLASS_MIN = [1, 10]

# -- what each enchantment goes on, and what it will not sit beside ----------
#
# From the server's UniversalEnchants config, checked in under tools/data.
# It is one file per enchantment giving the items it applies to and the
# enchantments it refuses to share with - and unlike everything else available
# here it covers the modded ones too, which is the whole reason it is worth
# having. Without it a modded enchantment has no knowable target and the page
# had to either leave it out or offer it on everything.
#
# `items` entries are either a plain item id or a tag with a $ prefix. The tags
# resolve to the gear kinds this page knows about; a tag naming one specific
# modded weapon (there are a lot: sea_staff, raygun, ortholance) resolves to
# "other", which is not gear anyone is enchanting on this page.
UE_DIR = os.path.join(HERE, 'data', 'universalenchants')

KINDS = ['sword', 'axe', 'pickaxe', 'shovel', 'hoe', 'shears', 'bow', 'crossbow',
         'trident', 'fishing_rod', 'shield', 'elytra', 'horse_armor',
         'helmet', 'chestplate', 'leggings', 'boots', 'other']
ARMOR = ['helmet', 'chestplate', 'leggings', 'boots']
DIGGER = ['pickaxe', 'shovel', 'axe', 'hoe']
# everything with a durability bar, which is what minecraft:breakable means
BREAKABLE = [k for k in KINDS if k != 'other']

TAG_KINDS = {
    'minecraft:breakable': BREAKABLE,
    'minecraft:vanishable': KINDS,
    'minecraft:wearable': ARMOR + ['elytra', 'horse_armor'],
    'minecraft:weapon': ['sword'],
    'minecraft:digger': DIGGER,
    'minecraft:armor': ARMOR,
    'minecraft:core_armor': ARMOR,
    'minecraft:armor_head': ['helmet'],
    'minecraft:armor_chest': ['chestplate'],
    'minecraft:armor_legs': ['leggings'],
    'minecraft:armor_feet': ['boots'],
    'minecraft:axe': ['axe'],
    'minecraft:universal_enchants_axe': ['axe'],
    'minecraft:pickaxe': ['pickaxe'],
    'minecraft:hoe': ['hoe'],
    'minecraft:shears': ['shears'],
    'minecraft:bow': ['bow'],
    'minecraft:crossbow': ['crossbow'],
    'minecraft:trident': ['trident'],
    'minecraft:fishing_rod': ['fishing_rod'],
    'minecraft:shield': ['shield'],
    'minecraft:universal_enchants_shield': ['shield'],
    'minecraft:universal_enchants_horse_armor': ['horse_armor'],
}

# a plain item id, read by its own name - the same suffix rules the forge
# extractor uses to sort gear into slots
ITEM_KIND_SUFFIX = [
    ('crossbow', ('crossbow',)), ('bow', ('bow',)),
    ('pickaxe', ('_pickaxe',)), ('shovel', ('_shovel',)),
    ('hoe', ('_hoe',)), ('shears', ('shears',)), ('axe', ('_axe',)),
    ('helmet', ('_helmet',)), ('chestplate', ('_chestplate',)),
    ('leggings', ('_leggings',)), ('boots', ('_boots',)),
    ('shield', ('shield',)), ('trident', ('trident',)),
    ('fishing_rod', ('fishing_rod',)), ('elytra', ('elytra',)),
    ('sword', ('_sword',)),
]


def kind_of_item(item_id):
    name = item_id.split(':', 1)[-1]
    for kind, suffixes in ITEM_KIND_SUFFIX:
        if any(name.endswith(sfx) for sfx in suffixes):
            return kind
    return 'other'


def read_universal_enchants():
    """{enchant id: {fits: [kind], items: [raw], clashes: [enchant id]}}."""
    out = {}
    if not os.path.isdir(UE_DIR):
        return out
    for ns in sorted(os.listdir(UE_DIR)):
        folder = os.path.join(UE_DIR, ns)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith('.json'):
                continue
            try:
                data = json.load(open(os.path.join(folder, fname), encoding='utf-8'))
            except Exception:
                continue
            fits = set()
            for entry in data.get('items') or []:
                if entry.startswith('$'):
                    fits.update(TAG_KINDS.get(entry[1:], ['other']))
                else:
                    fits.add(kind_of_item(entry))
            out['%s:%s' % (ns, fname[:-5])] = {
                'fits': sorted(fits),
                'clashes': sorted(data.get('incompatible') or []),
            }
    return out


# The positions the table reads, straight from vanilla: Apotheosis' gatherStats
# iterates EnchantmentTableBlock.BOOKSHELF_OFFSETS rather than a list of its
# own. That list is every position in a 5x5x2 box around the table whose x or z
# is +/-2 - the outer ring of a five-wide square, at the table's own height and
# one above it. Sixteen positions a layer, thirty-two in all.
#
# Each one only counts if the block halfway between it and the table is air,
# which is canReadStatsFrom's whole job and the reason a shelf pressed right up
# against the table does nothing.
BOOKSHELF_OFFSETS = [
    {'x': x, 'y': y, 'z': z}
    for y in (0, 1)
    for z in range(-2, 3)
    for x in range(-2, 3)
    if abs(x) == 2 or abs(z) == 2
]

# The gear the page offers to enchant. Kept here rather than in the script so
# the icons and the picker cannot drift apart: everything in this list gets an
# icon pulled for it.
ENCHANTABLE_GEAR = [
    'minecraft:diamond_sword', 'minecraft:netherite_sword',
    'minecraft:golden_sword', 'minecraft:diamond_axe',
    'minecraft:diamond_pickaxe', 'minecraft:diamond_shovel',
    'minecraft:diamond_helmet', 'minecraft:diamond_chestplate',
    'minecraft:diamond_leggings', 'minecraft:diamond_boots',
    'minecraft:bow', 'minecraft:crossbow', 'minecraft:trident',
    'minecraft:fishing_rod', 'minecraft:shield', 'minecraft:elytra',
    'minecraft:book', 'minecraft:lapis_lazuli',
]

STAT_KEYS = ['eterna', 'maxEterna', 'quanta', 'arcana', 'rectification', 'clues']


# ── block faces, for drawing a block rather than an item ─────────────────────

FACE_KEYS = {
    'top': ('up', 'end', 'top', 'all', 'texture', 'particle'),
    'side': ('side', 'north', 'all', 'texture', 'particle'),
}


def resolve_faces(assets, block_id):
    """The textures a block shows on its top and its side.

    The isometric builder draws real cubes, so an item icon is no use: it needs
    the two faces the camera can see. Every shelf in this mod is a cube_column
    - an `end` texture on the caps and a `side` texture round the middle - so
    the model chain is walked once and both slots are read off it, falling back
    through the usual aliases for blocks that are a plain cube instead.
    """
    ns, _, name = block_id.partition(':')
    if not name:
        ns, name = 'minecraft', ns
    ref = (assets.models.get((ns, 'block/' + name))
           or assets.models.get((ns, 'item/' + name)))
    seen, found = set(), {}
    while ref and ref[1] not in seen:
        seen.add(ref[1])
        try:
            model = json.loads(ref[0].read(ref[1]).decode('utf-8-sig'))
        except Exception:
            break
        for key, value in (model.get('textures') or {}).items():
            found.setdefault(key, value)
        parent = model.get('parent')
        if not parent:
            break
        ref = assets.models.get(Assets.split(parent))

    def pick(keys):
        for key in keys:
            value = found.get(key)
            if value and not value.startswith('#'):
                return value
        return None

    return {face: pick(keys) for face, keys in FACE_KEYS.items()}


# ── the config file ──────────────────────────────────────────────────────────

def read_enchantment_config(instance):
    """config/apotheosis/enchantments.cfg, one block per enchantment.

    Forge's config format, not json: a quoted registry name, a brace, and
    typed lines like `I:"Max Level"=8`. Only the fields the page shows are
    pulled out; the power functions are read but are empty on every
    enchantment in this pack, which means each one falls back to its own
    class's getMinCost/getMaxCost and is therefore not knowable from data.
    """
    path = os.path.join(instance, 'config', 'apotheosis', 'enchantments.cfg')
    if not os.path.exists(path):
        return []
    text = open(path, encoding='utf-8', errors='replace').read()

    def field(body, key):
        m = re.search(r'^\s*[ISBD]:"?%s"?=(.*)$' % re.escape(key), body, re.M)
        return m.group(1).strip() if m else None

    out = []
    for eid, body in re.findall(r'"([^"]+)"\s*\{(.*?)\n\}', text, re.S):
        def num(key, default=0):
            raw = field(body, key)
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        def flag(key, default=False):
            raw = field(body, key)
            return default if raw is None else raw == 'true'

        # The enchantment's *natural* maximum level - what its own class
        # returns from getMaxLevel() before Apotheosis touched it.
        #
        # This matters more than anything else in the block, because it is
        # where EnchantmentInfo.defaultMin starts extrapolating: up to it, a
        # level costs vanilla's own getMinCost; past it, each extra level
        # costs another step * (levels past it) ^ 1.6. Get it wrong and every
        # power number for that enchantment is wrong with it.
        #
        # Apotheosis writes it into the comment above the field - "The max
        # level of this enchantment - originally 4." - and that comment is
        # the only place the number appears anywhere on disk. The mod's own
        # bytecode reads it off the live Enchantment object, which no file
        # can be asked; Apotheosis' ASM redirect of getMaxLevel does not
        # touch EnchantmentInfo, so it really is the class's own value and
        # not the configured one.
        #
        # It is missing on forty-nine of the two hundred here, all of them
        # modded and all of them written into the file by a run that emitted
        # no comments. Those keep the old fallback and stay flagged.
        natural = re.search(r'originally (\d+)', body)

        out.append({
            'id': eid,
            'max': num('Max Level', 1),
            'natural': int(natural.group(1)) if natural else None,
            'loot': num('Max Loot Level', 1),
            'rarity': field(body, 'Rarity') or 'COMMON',
            'treasure': flag('Treasure'),
            'discoverable': flag('Discoverable', True),
            'lootable': flag('Lootable', True),
            'tradeable': flag('Tradeable', True),
            # kept so the page can say "this one has a custom curve" if a
            # future config ever sets one; empty everywhere on this pack
            'min_power': field(body, 'Min Power Function') or '',
            'max_power': field(body, 'Max Power Function') or '',
        })
    return out


# ── the datapack ─────────────────────────────────────────────────────────────

def read_stat_blocks(layers):
    """Every block that contributes enchanting stats, merged across layers."""
    out = []
    for entry in layers.under('data/apotheosis/enchanting_stats/'):
        data = layers.json(entry)
        if not isinstance(data, dict) or 'stats' not in data:
            continue                       # the advancement of the same name
        stats = data['stats']
        row = {
            'id': data.get('block') or data.get('tag'),
            'is_tag': 'tag' in data and 'block' not in data,
        }
        if not row['id']:
            continue
        for key in STAT_KEYS:
            row[key] = float(stats.get(key, 0) or 0)
        out.append(row)
    out.sort(key=lambda r: (-r['eterna'], r['id']))
    return out


def read_infusion(layers):
    """The enchanting-table infusion recipes.

    `enabled` is the part worth having: a recipe whose conditions include
    forge:false is shipped but switched off, which is how our datapack removes
    the Superior Sigil's infusion. It stays in the list, marked, rather than
    being dropped - "you cannot make this here" is a more useful answer than
    silence.
    """
    out = []
    for entry in layers.under('data/apotheosis/recipes/enchanting/'):
        data = layers.json(entry)
        if not isinstance(data, dict):
            continue
        kind = str(data.get('type', ''))
        if 'enchanting' not in kind:
            continue
        conditions = data.get('conditions') or []
        enabled = not any(c.get('type') == 'forge:false' for c in conditions)
        modules = [c.get('module') for c in conditions
                   if c.get('type') == 'apotheosis:module' and c.get('module')]
        req = data.get('requirements') or {}
        cap = data.get('max_requirements') or {}
        result = data.get('result') or {}
        out.append({
            'key': os.path.basename(entry)[:-5],
            'type': kind,
            'input': (data.get('input') or {}).get('item'),
            'result': result.get('item'),
            'count': result.get('count', 1),
            'req': {k: float(req.get(k, 0) or 0) for k in ('eterna', 'quanta', 'arcana')},
            # -1 means "no ceiling"; kept as-is so the page can say so
            'max': {k: float(cap[k]) for k in ('eterna', 'quanta', 'arcana') if k in cap},
            'display_level': data.get('display_level'),
            'enabled': enabled,
            'modules': modules,
        })
    out.sort(key=lambda r: (not r['enabled'], r['req']['eterna'], r['key']))
    return out


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    instance = None
    for candidate in (sys.argv[1:] or []) + INSTANCES:
        if os.path.isdir(candidate):
            instance = candidate
            break
    if not instance:
        print(__doc__)
        return 1

    mods = os.path.join(instance, 'mods')
    packs = os.path.join(instance, 'global_packs', 'required_data')
    names = sorted(os.listdir(mods))

    def one(pattern):
        for name in names:
            if pattern.match(name):
                return os.path.join(mods, name)
        return None

    apoth, ancient, attrs = one(APOTH_JAR), one(AR_JAR), one(ATTR_JAR)
    if not apoth:
        print('missing the Apotheosis jar in', mods)
        return 1
    vanilla = next((p for p in VANILLA_JARS if os.path.exists(p)), None)
    if not vanilla:
        print('no vanilla 1.20.1 jar found')
        return 1

    # The same merge order the forge extractor uses, so both pages agree about
    # what this server actually runs.
    order = [apoth]
    if ancient:
        order.append(ancient)
    for pack in PACKS:
        path = os.path.join(packs, pack)
        if os.path.exists(path):
            order.append(path)
    layers = Layers(order)

    all_jars = [vanilla] + [os.path.join(mods, n) for n in names if n.endswith('.jar')]
    assets = Assets(all_jars)
    lang = assets.lang()

    # Blocks that give stats can come from any mod, not just Apotheosis - the
    # wither skull and the amethyst cluster are vanilla blocks the mod attaches
    # stats to - so the stat scan runs over every jar, not the merged layers.
    blocks = read_stat_blocks(layers)
    seen = {b['id'] for b in blocks}
    import zipfile
    for jar in all_jars:
        try:
            zf = zipfile.ZipFile(jar)
        except Exception:
            continue
        for entry in zf.namelist():
            if '/enchanting_stats/' not in entry or not entry.endswith('.json'):
                continue
            try:
                data = json.loads(zf.read(entry).decode('utf-8-sig'))
            except Exception:
                continue
            if not isinstance(data, dict) or 'stats' not in data:
                continue
            key = data.get('block') or data.get('tag')
            if not key or key in seen:
                continue
            seen.add(key)
            row = {'id': key, 'is_tag': 'tag' in data and 'block' not in data}
            for stat in STAT_KEYS:
                row[stat] = float(data['stats'].get(stat, 0) or 0)
            blocks.append(row)

    # The plain bookshelf, which is in no datapack and still works.
    #
    # EnchantingStatRegistry.getEterna falls through to Forge's
    # BlockState.getEnchantPowerBonus for any block it has no entry for, and
    # that is 1.0 on a vanilla bookshelf; getMaxEterna falls through to
    # IEnchantingBlock.getMaxEnchantingPower, whose default is the vanilla cap
    # of 15. So a ring of ordinary bookshelves still gives 1 eterna each and
    # still stops at 15 - which is exactly vanilla's thirty levels, and the
    # reason everyone remembers "fifteen bookshelves". It is synthesised here
    # rather than read, and flagged, because there is no file to read it from.
    if not any(b['id'] == 'minecraft:bookshelf' for b in blocks):
        blocks.append({
            'id': 'minecraft:bookshelf', 'is_tag': False, 'fallback': True,
            'eterna': 1.0, 'maxEterna': 15.0,
            'quanta': 0.0, 'arcana': 0.0, 'rectification': 0.0, 'clues': 0.0,
        })

    # The Treasure Shelf, which is in no datapack and is the only way to get a
    # treasure enchantment out of a table.
    #
    # ApothEnchantmentMenu.gatherStats asks every block in range for
    # IEnchantingBlock.allowsTreasure, and one block answers yes:
    # TreasureShelfBlock. It contributes no stats at all - which is why it has
    # no enchanting_stats file and why it was missing from this list - but with
    # one in range the pool stops filtering treasure enchantments out, and
    # Mending, Frost Walker and the curses become rollable. Without one they
    # are unobtainable at a table no matter how much eterna you have.
    if not any(b['id'] == 'apotheosis:treasure_shelf' for b in blocks):
        blocks.append({
            'id': 'apotheosis:treasure_shelf', 'is_tag': False,
            'fallback': True, 'allows_treasure': True,
            'eterna': 0.0, 'maxEterna': 0.0,
            'quanta': 0.0, 'arcana': 0.0, 'rectification': 0.0, 'clues': 0.0,
        })
    blocks.sort(key=lambda r: (-r['eterna'], -r['maxEterna'], r['id']))

    infusion = read_infusion(layers)
    enchants = read_enchantment_config(instance)
    universal = read_universal_enchants()

    # ── icons ───────────────────────────────────────────────────────────────
    os.makedirs(ICON_DIR, exist_ok=True)
    icons, anims, unresolved = {}, {}, []

    # a wall-mounted block is the same item as the block it mounts, so it
    # borrows that item's icon rather than going looking for one of its own
    ALIAS = {'minecraft:wither_skeleton_wall_skull': 'minecraft:wither_skeleton_skull'}

    def pull(item_id):
        if not item_id or item_id in icons:
            return
        out_name = item_id.replace(':', '__')
        # the sigils resolve through Forge's separate_transforms loader and
        # have to be composited by hand - the forge extractor already knows how
        if item_id in LAYERED:
            if assets.save_layered(item_id, os.path.join(ICON_DIR, out_name + '.png')):
                icons[item_id] = out_name + '.png'
            else:
                unresolved.append(item_id)
            return
        ref = assets.texture_of(item_id)
        got = ref and assets.save(ref, os.path.join(ICON_DIR, out_name + '.png'))
        if got:
            icons[item_id] = out_name + '.png'
            if isinstance(got, dict):
                anims[item_id] = got
        else:
            unresolved.append(item_id)

    faces = {}
    face_anims = {}

    def pull_faces(block_id):
        """The block's own top and side - and, where the game animates one of
        them, how long the filmstrip is.

        Assets.save writes a *baked filmstrip* rather than a tile for any
        texture with a .mcmeta beside it, and returns {frames, seconds} when
        it does. That return value used to be thrown away here, which is how
        the Blazing Hellshelf ended up with its twenty-one frames squashed
        into one 16x16 face: the png the page was handed was 16x336 and
        nothing told the page so. The top of that block is a still tile and
        the side is not, so this has to be recorded per face rather than per
        block - the item-level `anims` map cannot say which half moves.
        """
        got, moving = {}, {}
        for face, ref in resolve_faces(assets, block_id).items():
            if not ref:
                continue
            out_name = '%s__%s.png' % (block_id.replace(':', '__'), face)
            saved = assets.save(ref, os.path.join(ICON_DIR, out_name))
            if not saved:
                continue
            got[face] = out_name
            if isinstance(saved, dict):
                moving[face] = saved
        # a block with only one resolvable face wears it on both, which is
        # what a plain cube does anyway
        if len(got) == 1:
            only_face, only = next(iter(got.items()))
            for face in ('top', 'side'):
                got.setdefault(face, only)
                if only_face in moving:
                    moving.setdefault(face, moving[only_face])
        if got:
            faces[block_id] = got
        if moving:
            face_anims[block_id] = moving

    for block in blocks:
        if block['is_tag']:
            continue
        pull(ALIAS.get(block['id'], block['id']))
        if block['id'] in ALIAS and ALIAS[block['id']] in icons:
            icons[block['id']] = icons[ALIAS[block['id']]]
        pull_faces(ALIAS.get(block['id'], block['id']))
        if block['id'] in ALIAS and ALIAS[block['id']] in faces:
            faces[block['id']] = faces[ALIAS[block['id']]]
        if block['id'] in ALIAS and ALIAS[block['id']] in face_anims:
            face_anims[block['id']] = face_anims[ALIAS[block['id']]]

    # the table itself, and the block it stands on, so the builder can draw them
    for extra in ('minecraft:enchanting_table', 'minecraft:obsidian',
                  'minecraft:bookshelf', 'apotheosis:treasure_shelf'):
        pull_faces(extra)
        pull(extra)

    # and the gear you can put in the table, so the picker can show it rather
    # than name it - a row of items you recognise beats a dropdown you have to
    # go looking for
    for gear in ENCHANTABLE_GEAR:
        pull(gear)

    # The vanilla enchanting screen's own sheet, copied whole the way the forge
    # copies the reforging one: the page blits the container and its three
    # offer rows out of it at the coordinates the game uses, so the panel is
    # the game's own window rather than a drawing of one.
    gui_dir = os.path.join(OUT_DIR, 'gui')
    os.makedirs(gui_dir, exist_ok=True)
    sheets = {}
    image = assets._open('minecraft:gui/container/enchanting_table')
    if image is not None:
        image.save(os.path.join(gui_dir, 'enchanting.png'))
        sheets['enchanting'] = 'enchanting.png'
    else:
        unresolved.append('gui/container/enchanting_table')

    # ── the runes ───────────────────────────────────────────────────────────
    #
    # The Standard Galactic Alphabet, which is the alphabet the enchanting
    # table writes its offers in. It is a font rather than a gui sheet:
    # assets/minecraft/textures/font/ascii_sga.png, a 128x128 grid of sixteen
    # by sixteen cells, each an 8x8 glyph laid out in ASCII order.
    #
    # The page blits glyphs out of it the same way it blits the container, so
    # the widths matter: Minecraft advances by the glyph's own drawn width plus
    # one, not by a fixed cell, and a fixed advance makes the runes read as a
    # monospaced code rather than as writing. Each cell is measured here for
    # its rightmost non-transparent column and the advances go out with it.
    sga = assets._open('minecraft:font/ascii_sga')
    widths = {}
    if sga is not None:
        sga.save(os.path.join(gui_dir, 'sga.png'))
        sheets['sga'] = 'sga.png'
        px = sga.convert('RGBA').load()
        cell = sga.width // 16
        for code in range(32, 127):
            col, row = code % 16, code // 16
            right = -1
            for x in range(cell):
                for y in range(cell):
                    if px[col * cell + x, row * cell + y][3] > 8:
                        right = max(right, x)
                        break
            # a space has nothing drawn in it and still has to take room
            widths[code] = (right + 2) if right >= 0 else 4
    else:
        unresolved.append('font/ascii_sga')
    for recipe in infusion:
        pull(recipe['input'])
        pull(recipe['result'])

    # ── names ───────────────────────────────────────────────────────────────
    def pretty(item_id):
        ns, _, name = item_id.partition(':')
        if not name:
            ns, name = 'minecraft', ns
        return (lang.get('block.%s.%s' % (ns, name))
                or lang.get('item.%s.%s' % (ns, name))
                or name.replace('_', ' ').title())

    names_out = {}
    for block in blocks:
        names_out[block['id']] = (pretty(block['id']) if not block['is_tag']
                                  else block['id'].split(':')[-1].replace('_', ' ').title())
    for recipe in infusion:
        for key in (recipe['input'], recipe['result']):
            if key:
                names_out[key] = pretty(key)
    for ench in enchants:
        ns, _, name = ench['id'].partition(':')
        ench['name'] = (lang.get('enchantment.%s.%s' % (ns, name))
                        or name.replace('_', ' ').title())
        ench['mod'] = ns
        # what it goes on and what it clashes with, from UniversalEnchants
        ue = universal.get(ench['id'])
        ench['fits'] = ue['fits'] if ue else []
        ench['clashes'] = ue['clashes'] if ue else []
        # the curve this one rolls on, and how much of it was read
        #
        # Two independent things go into a curve and they are known to
        # different degrees, so they are tracked separately:
        #
        #   `min`  - the (a, b) of vanilla's getMinCost. Transcribed for the
        #            vanilla enchantments; for a modded one it is
        #            Enchantment's own base-class default, which is a genuine
        #            default rather than an invention - a modded enchantment
        #            that overrides nothing uses exactly it - but is still an
        #            assumption per enchantment.
        #
        #   `vmax` - the natural maximum level, where extrapolation starts.
        #            This is *read*, from the config's own comment, for every
        #            enchantment that records one, modded ones included.
        #
        # It used to be neither for a modded enchantment: vmax was set to the
        # configured max, which meant nothing ever extrapolated and every
        # modded enchantment was priced as though its Apotheosis levels were
        # free. Thunder Strike goes to 7 here and is natural to 3; on the old
        # reading Thunder Strike VII asked for 71 power, where the mod asks
        # for 71 + 10 * trunc(4 ^ 1.6) = 161. Enchantments were turning up in
        # the pool a hundred power before the game would have offered them.
        natural = ench.pop('natural', None)
        known = VANILLA_COSTS.get(ench['id'])
        if known:
            ench['min'] = known['min']
            # the config agrees with the transcription on every vanilla
            # enchantment in this pack; where it speaks, it is the authority
            ench['vmax'] = natural if natural else known['vmax']
            ench['assumed'] = False
        else:
            ench['min'] = BASE_CLASS_MIN
            ench['vmax'] = natural if natural else ench['max']
            ench['assumed'] = True
        # the natural max was read rather than guessed - said separately from
        # `assumed`, which is about the curve, so the page can be honest about
        # which half of a modded enchantment's cost it actually knows
        ench['natural_read'] = natural is not None

    # computeAbsoluteMaxEterna, run against the blocks we actually loaded:
    #   absoluteMaxEterna = max(stats.maxEterna for every registered block)
    # and defaultMax, and therefore the power ceiling, is four times it.
    constants = dict(CONSTANTS)
    ceilings = [b['maxEterna'] for b in blocks if b.get('maxEterna')]
    if ceilings:
        constants['max_eterna'] = max(ceilings)
        constants['power_ceiling'] = int(max(ceilings) * 4)

    payload = {
        'constants': constants,
        'arcana': ARCANA,
        'base_min': BASE_CLASS_MIN,
        'kinds': KINDS,
        'rarities': RARITIES,
        'blocks': blocks,
        'enchants': enchants,
        'infusion': infusion,
        'icons': icons,
        'anims': anims,
        'faces': faces,
        'face_anims': face_anims,
        'gui': sheets,
        'sga_widths': widths,
        'offsets': BOOKSHELF_OFFSETS,
        'names': names_out,
        'source': {
            'jars': [os.path.basename(p) for p in order],
            'config': 'config/apotheosis/enchantments.cfg',
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'enchanting.json')
    with open(out_path, 'w') as fh:
        json.dump(payload, fh, separators=(',', ':'), sort_keys=True)

    layers.close()
    print('%d stat blocks, %d enchantments, %d infusion recipes, %d icons, %d faces'
          % (len(blocks), len(enchants), len(infusion), len(icons), len(faces)))
    print('%d of them have UniversalEnchants targets; %d have none'
          % (sum(1 for e in enchants if e['fits']),
             sum(1 for e in enchants if not e['fits'])))
    off = [r['key'] for r in infusion if not r['enabled']]
    if off:
        print('switched off by our packs:', ', '.join(off))
    if unresolved:
        print('no icon for:', ', '.join(sorted(set(unresolved))))
    print('wrote', out_path, os.path.getsize(out_path), 'bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
