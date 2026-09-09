"""Pull the Apotheosis reforging and gem socketing systems out of the game's
own files, so the page can run them rather than describe them.

Run from my_website/:
    python tools/extract_apotheosis.py ["<path to a pack instance>"]

The instance defaults to Groid Pack OG, which is the season being played.

What this reads, and why all four layers matter
-----------------------------------------------
A mod's behaviour is not in the mod. Apotheosis ships every affix, gem, rarity
and recipe as a datapack inside its own jar, and *our* datapack overrides a
good deal of it - reforging costs are two to ten times the mod's defaults,
Ancient was reweighted, the plain Sigil of Socketing is switched off entirely
and its replacement adds one socket where the mod gives three. Reading only
the jar would produce a page describing a game nobody here is playing. So
four layers are merged, later winning:

  1. Apotheosis' own jar
  2. ancientreforging's jar (adds the Ancient tier's reforge recipe)
  3. required_data/Apotheosis.zip        - our overrides
  4. required_data/Ancient Reforging.zip - our overrides

Precedence is by resource path, exactly as the game resolves it: a file at
data/apotheosis/gems/core/ballast.json in a later layer replaces the earlier
one whole. There is no field-level merging in Minecraft datapacks and there is
none here.

Two more jars are read for the vocabulary the systems are written in:
ApothicAttributes, whose attributes most affixes and gems modify and whose
tooltips are percentages or flat numbers depending on how each one was
registered, and the vanilla jar for item, effect and enchantment names.

What it writes
--------------
    static/minecraft/apotheosis/data.json   the whole model, one file
    static/minecraft/apotheosis/icons/*.png every icon the GUIs need

Everything the simulator needs is in data.json. Nothing is computed here that
the page could compute itself: value curves are emitted as the mod's own
{min, steps, step} triples rather than as expanded tables, because the page
has to evaluate them at an arbitrary roll anyway.
"""

import json
import os
import re
import sys
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'static', 'minecraft', 'apotheosis')
ICON_DIR = os.path.join(OUT_DIR, 'icons')

# CurseForge lands in a different place on each machine this has been run
# from, so both are tried and the first that exists wins - the same pair the
# other extractors in this folder carry.
INSTANCES = [os.path.expanduser(p) for p in (
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG',
    '~/curseforge/minecraft/Instances/Groid Pack OG',
)]
VANILLA_JARS = [os.path.expanduser(p) for p in (
    '~/Documents/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar',
    '~/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar',
)]

APOTH_JAR = re.compile(r'^Apotheosis-.*\.jar$')
AR_JAR    = re.compile(r'^ancientreforging-.*\.jar$')
ATTR_JAR  = re.compile(r'^ApothicAttributes-.*\.jar$')

PACKS = ['Apotheosis.zip', 'Ancient Reforging.zip']

# ── the affix type of each affix class ───────────────────────────────────────
#
# Which pool a rarity's "stat" and "ability" rules draw from. This is not in
# any json: it is the AffixType each affix class passes to super() in its
# constructor, read out of the jar with javap. Worth stating because the
# obvious guess is wrong - damage_reduction reads like a stat and is filed as
# an ability, which is why Dwarven and friends never appear on a Common item.
AFFIX_TYPES = {
    'apotheosis:attribute':        'STAT',
    'apotheosis:damage_reduction': 'ABILITY',
    'apotheosis:mob_effect':       'ABILITY',
    'apotheosis:catalyzing':       'ABILITY',
    'apotheosis:cleaving':         'ABILITY',
    'apotheosis:enlightened':      'ABILITY',
    'apotheosis:executing':        'ABILITY',
    'apotheosis:festive':          'ABILITY',
    'apotheosis:magical':          'ABILITY',
    'apotheosis:omnetic':          'ABILITY',
    'apotheosis:psychic':          'ABILITY',
    'apotheosis:radial':           'ABILITY',
    'apotheosis:retreating':       'ABILITY',
    'apotheosis:spectral':         'ABILITY',
    'apotheosis:telepathic':       'ABILITY',
    'apotheosis:thunderstruck':    'ABILITY',
    'apotheosis:durable':          'DURABILITY',
    'apotheosis:socket':           'SOCKET',
}

# Category restrictions the affix classes hardcode in canApplyTo, over and
# above the "types" list in the json. Every one of these is a method on
# LootCategory rather than a set, so the json has nothing to say about them:
# an affix with no "types" is not unrestricted, it is restricted in code.
# Spelled as a predicate name the page also implements.
AFFIX_GATES = {
    'apotheosis:catalyzing':    'shield',
    'apotheosis:psychic':       'shield',
    'apotheosis:retreating':    'shield',
    'apotheosis:cleaving':      'heavy_weapon',
    'apotheosis:executing':     'heavy_weapon',
    'apotheosis:festive':       'light_weapon',
    'apotheosis:thunderstruck': 'light_weapon',
    'apotheosis:enlightened':   'breaker',
    'apotheosis:omnetic':       'breaker',
    'apotheosis:radial':        'breaker',
    'apotheosis:magical':       'ranged',
    'apotheosis:spectral':      'ranged',
    'apotheosis:telepathic':    'ranged_light_or_breaker',
}

# LootCategory, in registration order, because forItem returns the first match
# and an axe is a heavy weapon rather than a sword only because heavy_weapon
# is registered first. The predicates are ItemStack tests in the mod; here
# they are suffix rules over the item ids that can actually reach the system,
# which is the finite list the affix loot entries name.
CATEGORY_ORDER = ['bow', 'crossbow', 'pickaxe', 'shovel', 'heavy_weapon',
                  'helmet', 'chestplate', 'leggings', 'boots', 'shield',
                  'trident', 'sword']
CATEGORY_SUFFIX = [
    # crossbow before bow: the mod separates these on the item class rather
    # than the name, and a crossbow is not a BowItem, so matching "bow" as a
    # suffix first would file every crossbow under bows and hand it the wrong
    # affix pool
    ('crossbow',     ('crossbow',)),
    ('bow',          ('bow',)),
    ('pickaxe',      ('_pickaxe',)),
    ('shovel',       ('_shovel',)),
    ('heavy_weapon', ('_axe',)),
    ('helmet',       ('_helmet',)),
    ('chestplate',   ('_chestplate',)),
    ('leggings',     ('_leggings',)),
    ('boots',        ('_boots',)),
    ('shield',       ('shield',)),
    ('trident',      ('trident',)),
    ('sword',        ('_sword',)),
]

# Which equipment slots a category's modifiers apply in. Straight from
# LootCategory's own arrays: it decides whether a gem or affix on a held item
# does anything at all.
CATEGORY_SLOTS = {
    'bow': ['mainhand', 'offhand'], 'crossbow': ['mainhand', 'offhand'],
    'pickaxe': ['mainhand'], 'shovel': ['mainhand'], 'heavy_weapon': ['mainhand'],
    'helmet': ['head'], 'chestplate': ['chest'], 'leggings': ['legs'],
    'boots': ['feet'], 'shield': ['mainhand', 'offhand'],
    'trident': ['mainhand'], 'sword': ['mainhand'],
}

# Three gem bonuses carry no "gem_class" in their json because they hardcode
# one in their constructor: the codec for those classes takes only "values".
# Without these the page has no idea a Blood Lord's arrow bonus is for bows,
# and Gem.getBonus would never find it. Copied from each class's super() call.
IMPLIED_GEM_CLASS = {
    'apotheosis:bloody_arrow': {'key': 'ranged_weapon', 'types': ['bow', 'crossbow']},
    'apotheosis:leech_block':  {'key': 'shield',        'types': ['shield']},
    'apotheosis:mageslayer':   {'key': 'helmet',        'types': ['helmet']},
}

# Base stats for the vanilla gear, so the page can show what a piece is worth
# before an affix touches it.
#
# These are constructor arguments, not data: a sword's damage is
# `3 + tier.getAttackDamageBonus()` and an axe's is whatever number Mojang
# typed into that item's own `new AxeItem(...)`. There is no file in the jar
# to read them out of, so the table is transcribed for 1.20.1 - it is small,
# it is fixed, and the alternative is disassembling Item.class to recover
# constants that have not moved in years.
#
# Modded gear is deliberately absent. Twilight Forest keeps its tiers in its
# own enums and reading them would want a second disassembler for four sets of
# armour; those items show their affixes and gems with no base block, which is
# honest, where a guessed 8.0 would not be.
TOOL_DAMAGE = {          # final attack damage, the tier's bonus already folded in
    'sword':   {'iron': 6, 'golden': 4, 'diamond': 8, 'netherite': 9},
    'axe':     {'iron': 9, 'golden': 7, 'diamond': 9, 'netherite': 10},
    'pickaxe': {'iron': 4, 'golden': 2, 'diamond': 6, 'netherite': 7},
    'shovel':  {'iron': 4.5, 'golden': 2.5, 'diamond': 6.5, 'netherite': 7.5},
}
TOOL_SPEED = {           # 4.0 plus the item's own negative modifier
    'sword': 1.6, 'pickaxe': 1.2, 'shovel': 1.0,
    'axe': {'iron': 0.9, 'golden': 1.0, 'diamond': 1.0, 'netherite': 1.0},
}
TIER_DURABILITY = {'iron': 250, 'golden': 32, 'diamond': 1561, 'netherite': 2031}

# protection by slot, toughness, knockback resistance, durability factor
ARMOR_MATERIAL = {
    'chainmail': ({'helmet': 2, 'chestplate': 5, 'leggings': 4, 'boots': 1}, 0, 0, 15),
    'iron':      ({'helmet': 2, 'chestplate': 6, 'leggings': 5, 'boots': 2}, 0, 0, 15),
    'golden':    ({'helmet': 2, 'chestplate': 5, 'leggings': 3, 'boots': 1}, 0, 0, 7),
    'diamond':   ({'helmet': 3, 'chestplate': 8, 'leggings': 6, 'boots': 3}, 2, 0, 33),
    'netherite': ({'helmet': 3, 'chestplate': 8, 'leggings': 6, 'boots': 3}, 3, 0.1, 37),
    'turtle':    ({'helmet': 2}, 0, 0, 25),
}
# ArmorItem's own per-slot durability multipliers
ARMOR_SLOT_BASE = {'helmet': 11, 'chestplate': 16, 'leggings': 15, 'boots': 13}

# gear with no attack modifiers of its own but a durability worth naming
FIXED_STATS = {
    'minecraft:bow':      {'durability': 384},
    'minecraft:crossbow': {'durability': 465},
    'minecraft:shield':   {'durability': 336},
    'minecraft:trident':  {'attack_damage': 9, 'attack_speed': 1.1,
                           'durability': 250},
}


def base_stats(item_id):
    """What the item is worth with nothing rolled on it, or {} if unknown."""
    if item_id in FIXED_STATS:
        return dict(FIXED_STATS[item_id])
    if not item_id.startswith('minecraft:'):
        return {}
    name = item_id.split(':', 1)[1]
    if name == 'turtle_helmet':
        material, kind = 'turtle', 'helmet'
    else:
        material, _, kind = name.partition('_')
    if not kind:
        return {}
    if kind in ARMOR_SLOT_BASE:
        armour = ARMOR_MATERIAL.get(material)
        if not armour:
            return {}
        defense, toughness, knockback, factor = armour
        out = {'armor': defense.get(kind, 0),
               'durability': factor * ARMOR_SLOT_BASE[kind]}
        if toughness:
            out['armor_toughness'] = toughness
        if knockback:
            out['knockback_resistance'] = knockback
        return out
    if kind in TOOL_DAMAGE:
        damage = TOOL_DAMAGE[kind].get(material)
        if damage is None:
            return {}
        speed = TOOL_SPEED[kind]
        return {
            'attack_damage': damage,
            'attack_speed': speed[material] if isinstance(speed, dict) else speed,
            'durability': TIER_DURABILITY[material],
        }
    return {}


# The items the icon extractor has to find a texture for beyond the gear:
# everything the three GUIs put in a slot or a cost line.
FIXED_ITEMS = [
    'apotheosis:gem_dust', 'apotheosis:common_material',
    'apotheosis:uncommon_material', 'apotheosis:rare_material',
    'apotheosis:epic_material', 'apotheosis:mythic_material',
    'apotheosis:ancient_material', 'apotheosis:sigil_of_socketing',
    'apotheosis:superior_sigil_of_socketing', 'apotheosis:vial_of_expulsion',
    'apotheosis:vial_of_extraction', 'apotheosis:vial_of_unnaming',
    'apotheosis:reforging_table', 'apotheosis:simple_reforging_table',
    'apotheosis:gem_cutting_table', 'apotheosis:salvaging_table',
    'ancientreforging:ancient_reforging_table', 'minecraft:smithing_table',
]

FACES = ('layer0', 'all', 'texture', 'side', 'north', 'front', 'end',
         'particle', 'top')

# The reforging table's background, copied out whole. It is a 256x256 sheet
# the screen blits rectangles out of - the panel, the three offer strips in
# their three states, the numeral badges - so the page gets the sheet and does
# its own blitting at the coordinates ReforgingScreen uses.
#
# Only this one. Socketing and gem cutting are shown as dropdowns and a cost
# table rather than as containers, so their sheets would ship unread.
GUI_SHEETS = {
    'reforge': 'apotheosis:gui/reforge',
}

# The sigils are the one pair of icons the model walk cannot resolve on its
# own. They use Forge's separate_transforms loader: a rune base under a glyph
# that the model tints per perspective, and the inventory perspective's colour
# is not the one the base model carries. Composited by hand with the colour
# the gui block names, because a flat layer0 would be the blank rune.
LAYERED = {
    'apotheosis:sigil_of_socketing': (
        'apotheosis:items/rune_base', 'apotheosis:items/sigil_of_socketing',
        (0x7C, 0x81, 0xFF)),
    'apotheosis:superior_sigil_of_socketing': (
        'apotheosis:items/rune_base', 'apotheosis:items/sigil_of_socketing',
        (0x7C, 0x81, 0xFF)),
}

# How each ApothicAttributes attribute renders, from ALObjects' registrations.
#
# This is not in any data file and it cannot be read out of the jar: whether
# "+0.05 Life Steal" or "+5% Life Steal" is correct depends on whether the
# attribute was constructed as a PercentBasedAttribute or a plain
# RangedAttribute, and that is a constructor call in bytecode. Transcribed,
# with a check below that every attribute the lang file names appears here, so
# a mod update that adds one is reported rather than rendered wrong.
AL_PERCENT = {
    'armor_shred', 'arrow_damage', 'arrow_velocity', 'crit_chance',
    'crit_damage', 'current_hp_damage', 'dodge_chance', 'draw_speed',
    'experience_gained', 'healing_received', 'life_steal', 'mining_speed',
    'overheal', 'prot_shred',
}
AL_FLAT = {
    'armor_pierce', 'cold_damage', 'fire_damage', 'ghost_health', 'prot_pierce',
}
AL_BOOLEAN = {'elytra_flight', 'creative_flight'}

# Forge's own attributes ship no lang file in this pack, and three of them are
# reachable from affixes. Named here rather than left blank on the page.
FORGE_ATTRIBUTES = {
    'forge:block_reach':          ('Block Reach', False),
    'forge:entity_reach':         ('Entity Reach', False),
    'forge:entity_gravity':       ('Gravity', False),
    'forge:step_height_addition': ('Step Height', False),
    'forge:swim_speed':           ('Swim Speed', True),
}


# ── layered resource lookup ──────────────────────────────────────────────────

class Layers:
    """The four data sources, resolved the way the game resolves them.

    Each layer is a zip. A path present in more than one comes from the last,
    which is what "our datapack overrides the mod" means mechanically.
    """

    def __init__(self, paths):
        self.zips = []
        for path in paths:
            self.zips.append((path, zipfile.ZipFile(path)))

    def get(self, entry):
        for _, zf in reversed(self.zips):
            try:
                return zf.read(entry)
            except KeyError:
                continue
        return None

    def json(self, entry):
        raw = self.get(entry)
        return None if raw is None else json.loads(raw.decode('utf-8-sig'))

    def under(self, prefix):
        """Every path under `prefix` across all layers, deduplicated."""
        seen = set()
        for _, zf in self.zips:
            for name in zf.namelist():
                if name.startswith(prefix) and name.endswith('.json'):
                    seen.add(name)
        return sorted(seen)

    def close(self):
        for _, zf in self.zips:
            zf.close()


def enabled(payload):
    """False if a datapack switched this recipe off.

    Our pack disables the plain Sigil of Socketing with a forge:false
    condition rather than deleting the file, so the file is still there and
    still parses. Reading it without checking would put a craftable item on
    the page that cannot be crafted.
    """
    for cond in payload.get('conditions') or []:
        if cond.get('type') == 'forge:false':
            return False
    return True


# ── textures ─────────────────────────────────────────────────────────────────

class Assets:
    """Item model and texture lookup across every jar in the pack.

    An item's icon is not a file named after the item: the item names a model,
    the model may inherit another, and the texture is somewhere up that chain.
    The same walk extract_item_icons.py does, kept here rather than imported
    because that one is wired to the season stats folders.
    """

    def __init__(self, jars):
        self.models, self.textures, self.langs = {}, {}, []
        self.metas = {}
        for path in jars:
            try:
                zf = zipfile.ZipFile(path)
            except Exception:
                continue
            for entry in zf.namelist():
                parts = entry.split('/')
                if len(parts) < 4 or parts[0] != 'assets':
                    continue
                ns, kind = parts[1], parts[2]
                rest = '/'.join(parts[3:])
                if kind == 'models' and entry.endswith('.json'):
                    self.models.setdefault((ns, rest[:-5]), (zf, entry))
                elif kind == 'textures' and entry.endswith('.png.mcmeta'):
                    self.metas.setdefault((ns, rest[:-11]), (zf, entry))
                elif kind == 'textures' and entry.endswith('.png'):
                    self.textures.setdefault((ns, rest[:-4]), (zf, entry))
                elif kind == 'lang' and rest == 'en_us.json':
                    # parts[3:] is already relative to the lang folder, so the
                    # file's own name is the whole of it
                    self.langs.append((zf, entry))

    def lang(self):
        merged = {}
        for zf, entry in self.langs:
            try:
                merged.update(json.loads(zf.read(entry).decode('utf-8-sig')))
            except Exception:
                continue
        return merged

    @staticmethod
    def split(ref, fallback='minecraft'):
        ns, _, path = ref.partition(':')
        return (ns, path) if path else (fallback, ns)

    def texture_of(self, item_id):
        ns, name = self.split(item_id)
        ref = (self.models.get((ns, f'item/{name}'))
               or self.models.get((ns, f'block/{name}')))
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
            ref = self.models.get(self.split(parent))
        for face in FACES:
            if face in found and not found[face].startswith('#'):
                return found[face]
        for value in found.values():
            if not value.startswith('#'):
                return value
        return None

    def save(self, texture_ref, out_path):
        """One tile on disk, or - where the game animates it - the filmstrip.

        A .mcmeta beside a texture means the png is a filmstrip: Inferno,
        Endersurge, gem dust and the Mythic and Ancient materials are all 16
        wide and several hundred tall, and every one of them moves in the
        player's hand. Cropping to frame one, which is what this did, threw
        away the thing that makes them recognisable across a room.

        What goes out is not the source strip. The mcmeta's `frames` list is
        an arbitrary playback order with repeats - Mythic's is eight copies of
        frame 0 and then eight more frames - and `interpolate` asks for a
        cross-fade the browser cannot do over a sprite sheet. So the sequence
        is *baked*: the tiles are written in playback order, one tile per unit
        of time, which leaves the page with a plain constant-rate strip it can
        run with a single steps() keyframe and no per-texture logic at all.

        Returns None for a still texture, or {frames, seconds} for a baked one.
        """
        ref = self.textures.get(self.split(texture_ref))
        if not ref:
            return False
        zf, entry = ref
        try:
            image = Image.open(zipfile.ZipFile.open(zf, entry)).convert('RGBA')
        except Exception:
            return False

        width, height = image.size
        anim = self._anim_meta(texture_ref)
        if anim and width and height > width and height % width == 0:
            baked = self._bake(image, anim)
            if baked:
                strip, count, ticks = baked
                strip.save(out_path)
                return {'frames': count, 'seconds': round(ticks / 20.0, 3)}

        if height > width and width and height % width == 0:
            image = image.crop((0, 0, width, width))
        image.save(out_path)
        return True

    def _anim_meta(self, texture_ref):
        ref = self.metas.get(self.split(texture_ref))
        if not ref:
            return None
        try:
            meta = json.loads(ref[0].read(ref[1]).decode('utf-8-sig'))
        except Exception:
            return None
        return meta.get('animation')

    # A texture that would bake to more tiles than this is left still rather
    # than shipped as a megabyte of sprite sheet. Nothing in this pack comes
    # close - the longest is Royalty at fifty - but the ceiling means a mod
    # update cannot quietly turn one icon into the largest file on the page.
    MAX_BAKED_FRAMES = 96

    @staticmethod
    def _bake(image, anim):
        """The mcmeta's playback order as a constant-rate strip.

        Minecraft's model: `frames` is the order (an int, or {index, time} for
        a frame that holds longer than the default), `frametime` is how many
        ticks each entry holds, and `interpolate` cross-fades from each frame
        into the next over that hold. Without interpolation one tile per entry
        is exact; with it the hold is cut into single-tick tiles and the blend
        is done here, in Pillow, once - rather than asked of every browser
        that opens the page.
        """
        size = image.size[0]
        total = image.size[1] // size
        tile = lambda i: image.crop((0, size * (i % total), size,
                                     size * (i % total) + size))

        default = int(anim.get('frametime') or 1)
        order = anim.get('frames')
        if order:
            steps = []
            for entry in order:
                if isinstance(entry, dict):
                    steps.append((int(entry.get('index', 0)),
                                  int(entry.get('time') or default)))
                else:
                    steps.append((int(entry), default))
        else:
            steps = [(i, default) for i in range(total)]
        if not steps:
            return None

        smooth = bool(anim.get('interpolate'))
        frames, ticks = [], 0
        for pos, (index, hold) in enumerate(steps):
            hold = max(1, hold)
            ticks += hold
            if not smooth:
                frames.append(tile(index))
                continue
            nxt = steps[(pos + 1) % len(steps)][0]
            for sub in range(hold):
                # Minecraft blends toward the *next* frame across the hold, and
                # the first sub-tick is the frame itself
                frames.append(tile(index) if sub == 0 else
                              Image.blend(tile(index), tile(nxt), sub / hold))
            if len(frames) > Assets.MAX_BAKED_FRAMES:
                return None

        if len(frames) < 2 or len(frames) > Assets.MAX_BAKED_FRAMES:
            return None
        strip = Image.new('RGBA', (size, size * len(frames)), (0, 0, 0, 0))
        for i, frame in enumerate(frames):
            strip.paste(frame, (0, size * i))
        return strip, len(frames), ticks

    def save_layered(self, item_id, out_path):
        """A rune base with its glyph tinted over it, the way the gui draws it."""
        base_ref, glyph_ref, colour = LAYERED[item_id]
        base = self._open(base_ref)
        glyph = self._open(glyph_ref)
        if base is None or glyph is None:
            return False
        red, green, blue = colour
        pixels = glyph.load()
        for y in range(glyph.height):
            for x in range(glyph.width):
                r, g, b, a = pixels[x, y]
                pixels[x, y] = (r * red // 255, g * green // 255,
                                b * blue // 255, a)
        base.alpha_composite(glyph)
        base.save(out_path)
        return True

    def _open(self, texture_ref):
        ref = self.textures.get(self.split(texture_ref))
        if not ref:
            return None
        try:
            return Image.open(zipfile.ZipFile.open(ref[0], ref[1])).convert('RGBA')
        except Exception:
            return None


# ── the model ────────────────────────────────────────────────────────────────

def category_of(item_id):
    name = item_id.split(':', 1)[-1]
    for cat, suffixes in CATEGORY_SUFFIX:
        if any(name.endswith(s) for s in suffixes):
            return cat
    return 'none'


def rarity_key(ref):
    """'apotheosis:mythic' or 'mythic' -> 'mythic'."""
    return str(ref).split(':')[-1].split('/')[-1]


def read_rarities(layers):
    out = []
    for entry in layers.under('data/apotheosis/rarities/'):
        key = os.path.basename(entry)[:-5]
        data = layers.json(entry)
        out.append({
            'id': key,
            'ordinal': data['ordinal'],
            'color': data['color'],
            'material': data['material'],
            'weight': data.get('weight', 0),
            'quality': data.get('quality', 0),
            'rules': [
                {'type': r['type'].upper(), 'chance': r['chance'],
                 'backup': ({'type': r['backup']['type'].upper(),
                             'chance': r['backup']['chance']}
                            if r.get('backup') else None)}
                for r in data.get('rules', [])
            ],
        })
    out.sort(key=lambda r: r['ordinal'])
    return out


def read_affixes(layers):
    out = []
    for entry in layers.under('data/apotheosis/affixes/'):
        rel = entry[len('data/apotheosis/affixes/'):-5]
        data = layers.json(entry)
        kind = data.get('type')
        if kind is None:
            continue
        affix = {
            'id': f'apotheosis:{rel}',
            'kind': kind,
            'type': AFFIX_TYPES.get(kind, 'ABILITY'),
            'categories': data.get('types') or [],
            'gate': AFFIX_GATES.get(kind),
            'values': data.get('values'),
        }
        for extra in ('attribute', 'operation', 'damage_type', 'mob_effect',
                      'target', 'stack_on_reapply', 'min_rarity'):
            if extra in data:
                affix[extra] = data[extra]
        if 'min_rarity' in affix:
            affix['min_rarity'] = rarity_key(affix['min_rarity'])
        out.append(affix)
    out.sort(key=lambda a: a['id'])
    return out


def read_gems(layers):
    out = []
    for entry in layers.under('data/apotheosis/gems/'):
        rel = entry[len('data/apotheosis/gems/'):-5]
        data = layers.json(entry)
        gem = {
            'id': f'apotheosis:{rel}',
            'variant': data.get('variant') or rel.split('/')[-1],
            'weight': data.get('weight', 0),
            'quality': data.get('quality', 0),
            'dimensions': data.get('dimensions') or [],
            'unique': bool(data.get('unique')),
            'bonuses': data.get('bonuses') or [],
        }
        for bonus in gem['bonuses']:
            if 'gem_class' not in bonus and bonus.get('type') in IMPLIED_GEM_CLASS:
                bonus['gem_class'] = dict(IMPLIED_GEM_CLASS[bonus['type']])
        if 'min_rarity' in data:
            gem['min_rarity'] = rarity_key(data['min_rarity'])
        if 'max_rarity' in data:
            gem['max_rarity'] = rarity_key(data['max_rarity'])
        out.append(gem)
    out.sort(key=lambda g: g['id'])
    return out


def read_items(layers):
    """Every base item that can carry affixes, from the loot entries.

    The mod has no list of "reforgeable items" - anything with a LootCategory
    qualifies, which in a pack this size is thousands of items. What it does
    have is the pool it rolls affix loot out of, and that is a curated list of
    real gear across every dimension. It is the honest set to offer.
    """
    seen = {}
    for namespace in ('apotheosis', 'ancientreforging'):
        prefix = f'data/{namespace}/affix_loot_entries/'
        for entry in layers.under(prefix):
            data = layers.json(entry)
            item = (data.get('stack') or {}).get('item')
            if not item:
                continue
            realm = entry[len(prefix):].split('/')[0]
            row = seen.setdefault(item, {
                'id': item,
                'category': category_of(item),
                'realms': [],
                'weight': data.get('weight', 0),
                'quality': data.get('quality', 0),
            })
            if realm not in row['realms']:
                row['realms'].append(realm)
            row['stats'] = base_stats(item)
            row['min_rarity'] = rarity_key(data.get('min_rarity', 'common'))
            row['max_rarity'] = rarity_key(data.get('max_rarity', 'ancient'))
    return sorted(seen.values(), key=lambda i: (i['category'], i['id']))


def read_recipes(layers):
    """Reforging costs, socket sigils and gem salvage, after our overrides.

    Reforging lives under two namespaces because the Ancient tier is a
    separate mod, so both are swept; the rarity each recipe names is the key
    the page looks it up by, not the filename.
    """
    reforging, sigils, salvage = {}, [], []
    for namespace in ('apotheosis', 'ancientreforging'):
        for entry in layers.under(f'data/{namespace}/recipes/reforging/'):
            data = layers.json(entry)
            if not enabled(data):
                continue
            reforging[rarity_key(data['rarity'])] = {
                'material_cost': data.get('material_cost', 0),
                'dust_cost': data.get('dust_cost', 0),
                'level_cost': data.get('level_cost', 0),
            }
        for entry in layers.under(f'data/{namespace}/recipes/'):
            data = layers.json(entry)
            if data.get('type') == 'apotheosis:add_sockets' and enabled(data):
                sigils.append({
                    'item': (data.get('input') or {}).get('item'),
                    'max_sockets': data.get('max_sockets', 0),
                })
        for entry in layers.under(f'data/{namespace}/recipes/salvaging/'):
            data = layers.json(entry)
            if not enabled(data):
                continue
            source = data.get('input') or {}
            outputs = data.get('outputs') or []
            if not outputs:
                continue
            salvage.append({
                'from': source.get('type'),
                'rarity': rarity_key(source.get('rarity', '')),
                'item': (outputs[0].get('stack') or {}).get('item'),
                'min': outputs[0].get('min_count', 1),
                'max': outputs[0].get('max_count', 1),
            })
    sigils.sort(key=lambda s: s['max_sockets'])
    salvage.sort(key=lambda s: (s['from'] or '', s['rarity']))
    return {'reforging': reforging, 'sigils': sigils, 'salvage': salvage}


def read_attributes(attr_lang):
    """Every attribute, and whether its tooltip is a percentage.

    ApothicAttributes decides this at registration rather than in data: a
    PercentBasedAttribute always renders value x 100 with a % sign, a plain
    RangedAttribute renders the raw number when the modifier is an addition.
    Two vanilla attributes are special-cased inside the mod itself and are
    carried here for the same reason - knockback resistance is a percentage,
    and movement speed is x1000 rather than x100 because its base value is a
    hundredth of a block per tick and nobody would read 0.1% as "fast".

    Returns the table, and any attribute AL_PERCENT/AL_FLAT/AL_BOOLEAN missed.
    """
    out, unknown = {}, []
    for key, value in attr_lang.items():
        if not key.startswith('attributeslib:') or key.endswith('.desc'):
            continue
        stem = key.split(':', 1)[1]
        if stem not in AL_PERCENT and stem not in AL_FLAT and stem not in AL_BOOLEAN:
            unknown.append(key)
        out[key] = {
            'name': value,
            'desc': attr_lang.get(key + '.desc', ''),
            'percent': stem in AL_PERCENT,
            'boolean': stem in AL_BOOLEAN,
        }
    out['minecraft:generic.knockback_resistance'] = {
        'name': 'Knockback Resistance', 'percent': True, 'boolean': False,
        'desc': attr_lang.get('attribute.name.generic.knockback_resistance.desc', ''),
    }
    out['minecraft:generic.movement_speed'] = {
        'name': 'Speed', 'percent': True, 'boolean': False, 'addition_scale': 1000,
        'desc': attr_lang.get('attribute.name.generic.movement_speed.desc', ''),
    }
    return out, unknown


def vanilla_attributes(vanilla_lang, attr_lang, extra_ids):
    """Names for the vanilla attributes affixes and gems reach for."""
    out = {}
    for attr in extra_ids:
        if attr in FORGE_ATTRIBUTES:
            name, percent = FORGE_ATTRIBUTES[attr]
            out[attr] = {'name': name, 'desc': '', 'percent': percent,
                         'boolean': False}
            continue
        if not attr.startswith('minecraft:'):
            continue
        stem = attr.split(':', 1)[1]
        key = f'attribute.name.{stem}'
        out[attr] = {
            'name': vanilla_lang.get(key, stem.replace('generic.', '').replace('_', ' ').title()),
            'desc': attr_lang.get(key + '.desc', ''),
            'percent': attr == 'minecraft:generic.knockback_resistance',
            'boolean': False,
        }
        if attr == 'minecraft:generic.movement_speed':
            out[attr]['percent'] = True
            out[attr]['addition_scale'] = 1000
    return out


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
    if not (apoth and ancient and attrs):
        print('missing a required jar in', mods)
        return 1
    vanilla = next((p for p in VANILLA_JARS if os.path.exists(p)), None)
    if not vanilla:
        print('no vanilla 1.20.1 jar found')
        return 1

    order = [apoth, ancient]
    for pack in PACKS:
        path = os.path.join(packs, pack)
        if os.path.exists(path):
            order.append(path)
        else:
            print('note: no', pack)
    layers = Layers(order)

    all_jars = [vanilla] + [os.path.join(mods, n) for n in names if n.endswith('.jar')]
    assets = Assets(all_jars)
    lang = assets.lang()

    with zipfile.ZipFile(vanilla) as zf:
        vanilla_lang = json.loads(zf.read('assets/minecraft/lang/en_us.json'))
    with zipfile.ZipFile(attrs) as zf:
        attr_lang = json.loads(zf.read('assets/attributeslib/lang/en_us.json'))

    rarities = read_rarities(layers)
    affixes = read_affixes(layers)
    gems = read_gems(layers)
    items = read_items(layers)
    recipes = read_recipes(layers)

    # which attributes anything in the model actually touches
    touched = set()
    for affix in affixes:
        if affix.get('attribute'):
            touched.add(affix['attribute'])
    for gem in gems:
        for bonus in gem['bonuses']:
            if bonus.get('attribute'):
                touched.add(bonus['attribute'])
            for mod in bonus.get('modifiers') or []:
                if mod.get('attribute'):
                    touched.add(mod['attribute'])

    attributes, unknown = read_attributes(attr_lang)
    attributes.update(vanilla_attributes(vanilla_lang, attr_lang, touched))
    missing = sorted(a for a in touched if a not in attributes)

    # ── the strings the tooltips are built from ──────────────────────────────
    wanted = {}
    for key, value in lang.items():
        if key.startswith(('affix.', 'gem_class.', 'bonus.', 'rarity.apotheosis',
                           'text.apotheosis.', 'misc.apotheosis.', 'socket.',
                           'item.apotheosis.', 'block.apotheosis.', 'gem.apotheosis')):
            wanted[key] = value
    for key in ('item.modifiers.socket', 'item.modifiers.socket_in',
                'block.ancientreforging.ancient_reforging_table',
                'block.ancientreforging.ancient_reforging_table.desc'):
        if key in lang:
            wanted[key] = lang[key]
    for key in ('potion.withAmplifier', 'potion.withDuration', 'item.modifiers.mainhand'):
        wanted[key] = vanilla_lang.get(key, '%s')
    for level in range(0, 10):
        got = vanilla_lang.get(f'potion.potency.{level}')
        if got is not None:
            wanted[f'potion.potency.{level}'] = got
    for key, value in attr_lang.items():
        if key.startswith('attributeslib.'):
            wanted[key] = value

    # effects and enchantments named by affixes and gems, with their names
    effects, enchants = {}, {}
    for source in [a for a in affixes] + [b for g in gems for b in g['bonuses']]:
        effect = source.get('mob_effect')
        if effect:
            ns, name = Assets.split(effect)
            effects[effect] = lang.get(f'effect.{ns}.{name}', name.replace('_', ' ').title())
        ench = source.get('enchantment')
        if ench:
            ns, name = Assets.split(ench)
            enchants[ench] = lang.get(f'enchantment.{ns}.{name}', name.replace('_', ' ').title())

    # ── icons ───────────────────────────────────────────────────────────────
    os.makedirs(ICON_DIR, exist_ok=True)
    icons, unresolved = {}, []
    # {item id: {frames, seconds}} for the dozen textures the game animates.
    # The png beside it is the baked filmstrip; this is how to run it.
    anims = {}

    def pull(item_id, out_name):
        if item_id in LAYERED:
            if assets.save_layered(item_id, os.path.join(ICON_DIR, out_name + '.png')):
                icons[item_id] = out_name + '.png'
                return True
            unresolved.append(item_id)
            return False
        ref = assets.texture_of(item_id)
        got = ref and assets.save(ref, os.path.join(ICON_DIR, out_name + '.png'))
        if got:
            icons[item_id] = out_name + '.png'
            if isinstance(got, dict):
                anims[item_id] = got
            return True
        unresolved.append(item_id)
        return False

    for item in items:
        pull(item['id'], item['id'].replace(':', '__'))
    for item_id in FIXED_ITEMS:
        pull(item_id, item_id.replace(':', '__'))
    for gem in gems:
        name = 'gem__' + gem['variant']
        got = assets.save(f'apotheosis:items/gems/{gem["variant"]}',
                          os.path.join(ICON_DIR, name + '.png'))
        if got:
            icons[gem['id']] = name + '.png'
            if isinstance(got, dict):
                anims[gem['id']] = got
        else:
            unresolved.append(gem['id'])

    gui_dir = os.path.join(OUT_DIR, 'gui')
    os.makedirs(gui_dir, exist_ok=True)
    sheets = {}
    for name, ref in GUI_SHEETS.items():
        image = assets._open(ref)
        if image is None:
            unresolved.append(ref)
            continue
        image.save(os.path.join(gui_dir, name + '.png'))
        sheets[name] = name + '.png'

    # names for everything with an icon, so the page never has to guess one
    item_names = {}
    for item_id in list(icons) + FIXED_ITEMS:
        ns, name = Assets.split(item_id)
        item_names[item_id] = (lang.get(f'item.{ns}.{name}')
                               or lang.get(f'block.{ns}.{name}')
                               or name.replace('_', ' ').title())

    payload = {
        'source': {
            'mods': [os.path.basename(apoth), os.path.basename(ancient),
                     os.path.basename(attrs)],
            'packs': [os.path.basename(p) for p in order[2:]],
        },
        'rarities': rarities,
        'categories': [
            {'id': cat,
             'name': lang.get(f'text.apotheosis.category.{cat}', cat),
             'plural': lang.get(f'text.apotheosis.category.{cat}.plural', cat),
             'slots': CATEGORY_SLOTS[cat]}
            for cat in CATEGORY_ORDER
        ],
        'affixes': affixes,
        'gems': gems,
        'items': items,
        'recipes': recipes,
        'attributes': attributes,
        'effects': effects,
        'enchantments': enchants,
        'icons': icons,
        'anims': anims,
        'gui': sheets,
        'names': item_names,
        'lang': wanted,
        # the smithing-table recipes are code rather than data in the mod, so
        # they are named here for the page to switch on
        'smithing': [
            {'id': 'socketing', 'addition': 'apotheosis:gem'},
            {'id': 'expulsion', 'addition': 'apotheosis:vial_of_expulsion'},
            {'id': 'extraction', 'addition': 'apotheosis:vial_of_extraction'},
            {'id': 'unnaming', 'addition': 'apotheosis:vial_of_unnaming'},
        ],
        # GemCuttingMenu's own constants: dust is 1 + 10 per rarity ordinal,
        # and the rarity material can be one tier below (9), the same tier (3)
        # or one above (5), with the cheaper two barred from reaching the top
        # tier at all
        'cutting': {'dust_base': 1, 'dust_per_ordinal': 10,
                    'mat_prev': 9, 'mat_same': 3, 'mat_next': 5},
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'data.json')
    with open(out_path, 'w') as fh:
        json.dump(payload, fh, separators=(',', ':'), sort_keys=True)

    layers.close()
    print(f'{len(rarities)} rarities, {len(affixes)} affixes, {len(gems)} gems, '
          f'{len(items)} base items, {len(icons)} icons, {len(anims)} animated')
    print('reforge tiers:', ', '.join(sorted(recipes['reforging'])))
    print('sigils:', recipes['sigils'])
    if missing:
        print('no name for attributes:', ', '.join(missing))
    if unknown:
        print('NOT IN AL_PERCENT/AL_FLAT/AL_BOOLEAN, rendered as flat:',
              ', '.join(unknown))
    if unresolved:
        print('no texture for:', ', '.join(sorted(set(unresolved))))
    print('wrote', out_path, os.path.getsize(out_path), 'bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
