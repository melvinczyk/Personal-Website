"""Build the portal's boss roster from a modpack.

The datapack says which entities count as bosses. This goes and finds each one
in the pack's own jars and turns it into something the portal can draw.

Mods build their models three different ways and only two are worth chasing:

  geckolib   a .geo.json in the jar, the same format the armor pipeline reads
  vanilla    a CubeListBuilder chain in Java, read back out of the bytecode

Anything built on another mod's model API (citadel's AdvancedModelBox, which
Cataclysm and Alex's mods use) is skipped and reported rather than guessed at.

    python tools/bosses.py            # build everything the tag lists
    python tools/bosses.py --list     # say what would happen, write nothing
"""

import json
import math
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import entity_model as em
import geo as geolib

MODS = os.path.expanduser(
    '~/curseforge/minecraft/Instances/Groid Pack OG/mods')
TAG = os.path.expanduser(
    '~/Desktop/Minecraft server stuff/Datapacks/Groid Pack OG/Groid Tags'
    '/data/groid/tags/entity_types/bosses.json')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'static', 'minecraft', 'bosses')

VANILLA_JAR = em.JAR
PNG = re.compile(rb'([a-z][a-z0-9_/]*\.png)')
# A mod ships overlays beside the skin proper: glow maps, eye layers, the
# emissive pass. They are the same size as the real sheet and mostly empty,
# so they have to be ranked below it rather than merely matched against.
OVERLAY = ('brillo', 'brille', 'glow', 'emissive', 'layer', 'eye', 'shine',
           'outline', 'overlay', 'light', 'crack', 'flare', 'shield', 'soul',
           'inner', 'outer', 'snake', 'particle', 'effect', 'trail',
           'beam', 'aura', 'damage', 'hurt')

# Classes that draw something on top of the mob rather than the mob: whatever
# they name is a coat of paint, not the skin underneath.
EXTRA = ('layer', 'flare', 'crack', 'shield', 'particle', 'effect', 'projectile',
         'item', 'arrow', 'beam', 'spawner', 'clone', 'fireball', 'ball',
         'halberd', 'weapon', 'bomb', 'orb', 'mine')
GEO = re.compile(rb'([a-z0-9_/-]+\.geo\.json)')
TEX_HINT = re.compile(r'textures/entit')

# Three ways a mob can be described, tried in turn and judged on what comes
# back: a route that reads nothing loses to one that reads a model.
ROUTES = ('geckolib', 'vanilla', 'advanced')

# Hand-pinned bosses.
#
# The general rules get most of the pack right and are wrong in ways no rule
# will fix: a mod that names its pharaoh's sheet olala.png, or ships an old
# model beside the one it actually draws. Rather than bend the heuristics
# further and break what already works, those are named here outright.
#
#   model    path inside the jar: a .geo.json or a .class
#   texture  path inside the jar, from assets/<namespace>/
#   mirror   honour each cube's mirror flag (geckolib only)
#   spin     which way to read the geo file's bone rotations, see SPINS
#   cubes    the same, for rotations a cube carries of its own
#   order    'xyz' where a cube's own three turns are composed the other way
#            round: geckolib builds a cube's from a quaternion and a bone's
#            from three turns, and the two do not agree
#   zoom     scale the model in its card, for anything the framing leaves small
#   pose     turn the whole mob before it is framed, x/y/z in degrees, for
#            a rig whose rest pose lies down when the mob does not
#   focus    the bone to put in the middle of the card, for a mob too long
#            to read at the size the whole of it would fit in
#   skin     a second sheet, and the bones that wear it instead of the first;
#            'veil' marks it a see-through shell and says how strongly, and
#            'size' the sheet those bones were laid out against, for the
#            layer that builds its part from a mesh measured its own way
#   train    a body segment to lay out behind the mob, for a boss that is
#            really a head with a line of part entities following it
#   ghost    a second sheet the game draws over the same bones, for a mob
#            worn over something: it goes on just inside the outer skin
#   coat     the same the other way about: armour the mob is wearing, laid
#            over the same bones just outside its own skin
#   parts    bones a model builds in a loop, which leaves nothing in the
#            bytecode to read: name, parent, where it sits, its box, its uv
#   keep     the only bones to draw, for a rig carrying more than one mob
#   drop     bones to leave undrawn, along with everything under them
#   hide     single boxes to drop, as (bone, place in that bone's list)
#   reparent bones whose real parent the reader could not see, name -> parent
#   rest     the pose a mob is drawn in where its model builds it flat and
#            bends it every frame: bone -> the three turns setupAnim assigns,
#            in the game's own axes and radians, put in place of the bone's
#   lean     the same where the mob's idle adds its turns rather than
#            assigning them: bone -> three turns in degrees, added to the
#            bone's own
#   graft    a second model the mob is holding, drawn by a layer of its own:
#            its class, its sheet, the bone it hangs off, and any rest pose
#            of its own. It keeps its sheet as a second skin.
OVERRIDES = {
    # Twilight Forest keeps its skins in textures/model and ships an older
    # model beside the one it draws, so both ends are named here.
    'twilightforest:naga': {
        'model': 'twilightforest/client/model/entity/NagaModel.class',
        'texture': 'textures/model/nagahead.png'},
    'twilightforest:lich': {
        'model': 'twilightforest/client/model/entity/LichModel.class',
        'texture': 'textures/model/twilightlich64.png'},
    # The phantom's armour is not part of its model: the renderer hangs the
    # game's own armour layer off the same bones, so it goes on as a coat.
    'twilightforest:knight_phantom': {
        'model': 'twilightforest/client/model/entity/KnightPhantomModel.class',
        'texture': 'textures/model/phantomskeleton.png',
        'coat': 'textures/armor/phantom_1.png'},
    # towerboss.png is what both of its renderers name. Its nine tentacles are
    # made in a loop from a fixed seed, so their lengths and places are worked
    # out from that loop rather than read off the class.
    'twilightforest:ur_ghast': {
        'model': 'twilightforest/client/model/entity/UrGhastModel.class',
        'texture': 'textures/model/towerboss.png',
        'parts': tuple(
            (f'tentacle{i}', 'body', (x, 7, z), (-1, 0, -1, 2, long, 2), (0, 0))
            for i, (x, z, long) in enumerate((
                (-3.75, -5.0, 8), (0.417, -3.333, 13), (4.583, -1.667, 9),
                (-6.25, 0.0, 11), (-2.083, 1.667, 11), (2.083, 3.333, 10),
                (-3.75, 5.0, 12), (0.417, 6.667, 9), (4.583, 8.333, 12))))},
    # hydra4.png is the classic sheet; the newmodels rework unwraps its boxes
    # somewhere else, so the old model is the one that reads it correctly.
    'twilightforest:hydra': {
        'model': 'twilightforest/client/model/entity/HydraModel.class',
        'texture': 'textures/model/hydra4.png'},
    'twilightforest:snow_queen': {
        'model': 'twilightforest/client/model/entity/SnowQueenModel.class',
        'texture': 'textures/model/snowqueen.png'},

    # Each Fairkeeper is a serpent built from a head entity and a train of body
    # segments, and the mod has a model for each. The segment is a shield and a
    # dispenser on a length of hide; the head is the mob.
    'dungeonnowloading:fairkeeper_boros': {
        'model': 'dev/hexnowloading/dungeonnowloading/entity/client/model/'
                 'FairkeeperBorosModel.class',
        'texture': 'textures/entity/fairkeeper_boros/fairkeeper_boros_head.png',
        'train': {
            'model': 'dev/hexnowloading/dungeonnowloading/entity/client/model/'
                     'FairkeeperBorosBodyModel.class',
            'texture': 'textures/entity/fairkeeper_boros/'
                       'fairkeeper_boros_body.png',
            'body': ('body',), 'tail': ('tail',)},
        'focus': 'head', 'zoom': 3.0},
    'dungeonnowloading:fairkeeper_ouros': {
        'model': 'dev/hexnowloading/dungeonnowloading/entity/client/model/'
                 'FairkeeperOurosModel.class',
        'texture': 'textures/entity/fairkeeper_ouros/fairkeeper_ouros_head.png',
        'train': {
            'model': 'dev/hexnowloading/dungeonnowloading/entity/client/model/'
                     'FairkeeperOurosBodyModel.class',
            'texture': 'textures/entity/fairkeeper_ouros/'
                       'fairkeeper_ouros_body.png',
            'body': ('body', 'cannon'), 'tail': ('tail',)},
        'focus': 'ouros', 'zoom': 3.0},

    # Block Factory's bosses are all geckolib, and every one of them draws a
    # side of itself from the other side's texture.
    'block_factorys_bosses:kraken': {
        'model': 'geo/entity/kraken.geo.json',
        'texture': 'textures/entity/kraken.png', 'mirror': True},
    'block_factorys_bosses:sandworm': {
        'model': 'geo/entity/sandworm.geo.json',
        'texture': 'textures/entity/sandworm.png',
        'mirror': True, 'spin': 'alt',
        'pose': [45, 0, 0], 'focus': 'head', 'zoom': 5},
    'block_factorys_bosses:yeti': {
        'model': 'geo/entity/yeti_boss.geo.json',
        'texture': 'textures/entity/yeti_boss.png',
        'mirror': True, 'spin': 'alt'},
    # One file, three knights: the one it wears, a bare skeleton, a shattered
    # phase, and a rack of spare swords the fight hands it.
    'block_factorys_bosses:underworld_knight': {
        'model': 'geo/entity/knight_boss.geo.json',
        'texture': 'textures/entity/knight_boss.png',
        'mirror': True, 'spin': 'alt',
        'keep': ('body', 'chest', 'head', 'helmet', 'head_under', 'jaw',
                 'eyes', 'phase0_eyes', 'cape', 'cape_001', 'cape_002',
                 'arm_L', 'arm_R', 'left_hand', 'right_hand',
                 'finger', 'finger2', 'fingers', 'fingers2',
                 'leg_L', 'leg_R'),
        # a flat sheet the size of a banner, parked over the left pauldron
        'hide': (('arm_L', 1),)},
    'block_factorys_bosses:infernal_dragon': {
        'model': 'geo/entity/dragon_phase1.geo.json',
        'texture': 'textures/entity/dragon_phase1.png',
        'mirror': True, 'spin': 'alt', 'focus': 'chest', 'zoom': 3.0},

    # Scylla throws her anchor on a chain as one of her attacks, and the rig
    # keeps the throw parked out behind her when she is not using it: taken in,
    # it is four times her size and she reads as a doll beside it.
    # Maledictus is a suit of armour with a ghost in it: the game draws the
    # same bones twice, the second pass in the ghost's own skin.
    # Chesed and Malkuth are each drawn in two passes: a dark solid body and a
    # sheet of lit detail over it. The detail goes on the outside, where the
    # game puts it, and the body sits just inside so it shows through the gaps.
    'fdbosses:chesed': {
        'model': 'bedrock/models/chesed.geo.json',
        'texture': 'textures/entities/chesed_full.png', 'spin': 'alt',
        'focus': 'core', 'zoom': 1.5},
    'fdbosses:malkuth': {
        'model': 'bedrock/models/malkuth.geo.json',
        'texture': 'textures/entities/malkuth/malkuth.png',
        'ghost': 'textures/entities/malkuth/malkuth_solid.png'},

    # A fossil the length of four cards: framed whole it is a hairline, so the
    # card takes its ribcage and crowned skull and lets the tail run off.
    'cataclysm:ancient_remnant': {'focus': 'spine2', 'zoom': 2.2},

    'cataclysm:maledictus': {
        'ghost': 'textures/entity/maledictus/maledictus_ghost.png',
        'focus': 'body', 'zoom': 2.0},

    'cataclysm:scylla': {'drop': ('chain_main', 'anchor2'),
                         'focus': 'body', 'zoom': 1.5},

    # The Shelterer is a head sitting inside a shell of light: the shell's
    # corner of its own sheet is blank, because the game draws it from the
    # glow sheet instead.
    'stalwart_dungeons:shelterer': {
        'skin': {'texture': 'textures/entities/shelterer_glow.png',
                 'bones': ('bone',), 'veil': 0.32}},

    # Azazel's left wing is drawn from the right one's corner of the sheet.
    'netherman:azazel': {'mirror': True},
    'netherman:azazel_human': {'mirror': True},
    # Both of these read their cube rotations the other way round; taken the
    # usual way they come out as a heap of loose boxes.
    'graveyard:lich': {'model': 'geo/lich.geo.json',
                       'texture': 'textures/entity/lich_texture.png',
                       'mirror': True, 'spin': 'alt'},

    # Arkane Domains names nothing after the mob it belongs to: faraoonon is
    # the pharaoh, texture333333w is the warlock.
    'arkane_domains:cursed_pharaoh': {
        'model': 'geo/faraong.geo.json',
        'texture': 'textures/entities/faraoonon.png', 'mirror': True},
    'arkane_domains:warlock': {
        'model': 'geo/warlock_gggeo.geo.json',
        'texture': 'textures/entities/texture333333w.png', 'mirror': True},

    # four hundred pixels of neck and tail: framed to fit it is a thin ribbon,
    # so it is allowed to run past the sides of its card
    'alexscaves:luxtructosaurus': {
        'model': 'com/github/alexmodguy/alexscaves/client/model/'
                 'LuxtructosaurusModel.class',
        'texture': 'textures/entity/luxtructosaurus.png', 'zoom': 2.2},
    'alexscaves:tremorzilla': {
        'model': 'com/github/alexmodguy/alexscaves/client/model/'
                 'TremorzillaModel.class',
        'texture': 'textures/entity/tremorzilla/tremorzilla.png', 'zoom': 1.6},
}


def norm(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def pretty(name):
    return ' '.join(word.capitalize() for word in name.split('_'))


# ── the pack ────────────────────────────────────────────────────────────────

def read_tag(path):
    with open(path) as fh:
        return [v['id'] for v in json.load(fh)['values']]


def index_jars(folder):
    """namespace -> the jar that carries its code, and every jar's file list."""
    owners, listing = {}, {}
    for name in sorted(os.listdir(folder)):
        if not name.endswith('.jar'):
            continue
        path = os.path.join(folder, name)
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            continue
        listing[path] = names
        classes = sum(1 for n in names if n.endswith('.class'))
        if not classes:
            continue
        seen = {m.group(1) for n in names
                for m in [re.match(r'assets/([a-z0-9_]+)/', n)] if m}
        for ns in seen:
            if ns == 'minecraft':
                continue
            # a namespace can appear in several jars; the one with the code wins
            if ns not in owners or classes > owners[ns][1]:
                owners[ns] = (path, classes)
    return {ns: jar for ns, (jar, _) in owners.items()}, listing


# ── textures ────────────────────────────────────────────────────────────────

def strings_in(jar, entry):
    """The asset paths a class names outright: its model, and its skin."""
    with zipfile.ZipFile(jar) as zf:
        blob = zf.read(entry)
    return ([m.group(1).decode() for m in PNG.finditer(blob)],
            [m.group(1).decode() for m in GEO.finditer(blob)])


def kin(names, ns, entity):
    """Every class in the jar that looks like it belongs to this mob.

    A mod is free to call its model file anything at all: Arkane Domains draws
    its cursed pharaoh from geo/faraong.geo.json. What does not vary is that
    the class named after the mob says which file that is, so the classes are
    what gets searched, not the file names.
    """
    target = norm(entity)
    if not target:
        return []

    def stem(path):
        base = norm(os.path.basename(path)[:-6])
        # MCreator writes Modelminoshroomtaur; everyone else writes NagaModel
        for tail in ('entitymodel', 'model', 'renderer', 'render', 'entity'):
            if base.endswith(tail):
                base = base[:-len(tail)]
        for head in ('model', 'new'):
            if base.startswith(head) and len(base) > len(head):
                base = base[len(head):]
        return base

    out = []
    for path in names:
        # a model is sometimes an inner class of its own renderer
        if not path.endswith('.class'):
            continue
        base = stem(path)
        if not base or (base != target and target not in base and base not in target):
            continue
        lower = path.lower()
        rank = (0 if base == target else 1,
                0 if '$' not in path else 1,
                0 if '/model' in lower else 1 if 'render' in lower else 2,
                len(path))
        out.append((rank, path))
    out.sort()
    return [path for _, path in out]


_sizes = {}


def png_size(jar, entry):
    """A png's dimensions, read from its header rather than decoded.

    Ranking a texture asks this of every sheet in the mod, so the answers are
    kept: reopening a jar a few thousand times is the difference between a
    build that takes seconds and one that takes minutes.
    """
    hit = _sizes.get((jar, entry))
    if hit is not None:
        return hit
    try:
        with zipfile.ZipFile(jar) as zf:
            head = zf.open(entry).read(24)
        size = struct.unpack('>II', head[16:24])
    except Exception:                                 # noqa: BLE001
        size = (0, 0)
    _sizes[(jar, entry)] = size
    return size


def pick_texture(jar, names, ns, entity, named=(), size=None):
    """The sheet this mob is drawn with.

    Mods keep a mob's skin beside a dozen things that are not it: the layer
    that makes its eyes glow, the boulder it throws, the bar over its head. So
    rather than trust any one signal, every png in the mod is ranked on all of
    them at once, hardest evidence first: does it fit the model's declared
    sheet, is it a coat of paint, is it named for the mob, is it in the mob's
    own folder. A class naming it outright only breaks a remaining tie.
    """
    target = entity.lower()
    tail = target.split('_')[-1]
    pool = [n for n in names
            if n.startswith(f'assets/{ns}/textures/') and n.endswith('.png')]
    if not pool:
        return None

    spoken = {f'assets/{ns}/{p}' for p in named}

    def rank(path):
        base = os.path.basename(path)[:-4].lower()
        return (
            0 if (not size or png_size(jar, path) == tuple(size)) else 1,
            1 if any(word in path.lower() for word in OVERLAY) else 0,
            0 if base in (target, tail) else 1,
            0 if f'/{target}/' in path or f'/{tail}/' in path else 1,
            0 if '/entit' in path else 1,
            0 if base.startswith(target) or base.startswith(tail) else 1,
            len(base),
            0 if path in spoken else 1,
        )

    return min(pool, key=rank)


def near_texture(names, ns, source, jar=None, size=None):
    """The texture sitting beside a model file, named the same way."""
    stem = norm(re.sub(r'\.(geo\.json|class)$', '', os.path.basename(source)))
    pool = [n for n in names
            if n.startswith(f'assets/{ns}/textures/') and n.endswith('.png')]
    hits = [p for p in pool
            if norm(os.path.basename(p)[:-4]) == stem
            or stem.startswith(norm(os.path.basename(p)[:-4]))]
    hits.sort(key=lambda p: (0 if (jar and size and png_size(jar, p) == tuple(size)) else 1,
                             0 if '/entit' in p else 1, len(p)))
    return hits[0] if hits else None


def any_texture(jar, names, ns, size, entity='', source=''):  # noqa: D401
    """Last resort: the sheet of the right size that looks least like a layer."""
    if not size:
        return None
    fits = [n for n in names
            if n.startswith(f'assets/{ns}/textures/') and n.endswith('.png')
            and png_size(jar, n) == tuple(size)]
    stem = norm(re.sub(r'\.(geo\.json|class)$', '', os.path.basename(source)))
    target = norm(entity)

    def rank(path):
        base = norm(os.path.basename(path)[:-4])
        shared = max((len(os.path.commonprefix([base, other]))
                      for other in (target, stem) if other), default=0)
        return (0 if '/entit' in path else 1,
                1 if any(word in path.lower() for word in OVERLAY) else 0,
                0 if f'/{entity}/' in path else 1,
                -shared, len(path))

    fits.sort(key=rank)
    return fits[0] if fits else None


# ── the geckolib route ──────────────────────────────────────────────────────

# How a geo file's rotations are read. Blockbench writes them measured its own
# way; a loader may turn any of the three round again, and which a mod meant
# cannot be read off the file - both are legal bedrock. So it is a per-mob
# switch, set where the usual reading comes out wrong.
SPINS = {
    None: (1, -1, -1),
    'alt': (-1, -1, 1),
    # geckolib's own reading: it turns x and y round, and then the portal's
    # axes turn y and z back. Rigs built lying down and stood up by their root
    # bone need this; taken any other way they end up on their side or inside out.
    'geo': (-1, 1, -1),
    'flat': (1, 1, 1),
}


def geo_bones(model, mirror=False, spin=None, cubespin=None, order=None):
    """A geo file's bone tree in the portal's axes: y down, front to the front."""
    geometry = model['minecraft:geometry'][0]
    description = geometry.get('description', {})
    bones = []
    # Some models turn their cubes the other way about. Which way a mod means
    # cannot be read off the file - both are legal bedrock - so it is a per-mob
    # switch, set where the usual reading comes out as a heap of loose boxes.
    sign = SPINS.get(spin, SPINS[None])
    # A cube turned on the spot is not read the same way round as the bone that
    # holds it: geckolib builds the two rotations from different corners of its
    # own maths, and rigs whose shape comes from cube rotations come apart if
    # the bone's reading is used for both.
    cubesign = SPINS[cubespin] if cubespin else sign

    for bone in geometry.get('bones', []):
        pivot = bone.get('pivot') or [0, 0, 0]
        turn = bone.get('rotation') or [0, 0, 0]
        cubes = []
        for cube in bone.get('cubes') or []:
            if not cube.get('size') or not cube.get('origin'):
                continue
            size = [float(v) for v in cube['size']]
            origin = [float(v) for v in cube['origin']]
            grow = float(cube.get('inflate', 0) or 0)
            middle = [origin[i] + size[i] / 2 for i in range(3)]
            faces = geolib.cube_faces(cube)
            if not faces:
                continue
            if mirror and cube.get('mirror'):
                # only where a pin asks: some mods set the flag and do not mean it
                faces = em.mirrored(faces)

            # A geckolib cube may be turned on the spot, which is most of how
            # these models get their shape: dropping it leaves a pile of boxes
            # all square to each other and nothing that looks like the mob.
            tilt = cube.get('rotation')
            spun = {}
            if tilt and any(tilt):
                anchor = [float(v) for v in (cube.get('pivot') or middle)]
                spun = {
                    **({'o': order} if order else {}),
                    'r': [round(cubesign[0] * tilt[0], 3),
                          round(cubesign[1] * tilt[1], 3),
                          round(cubesign[2] * tilt[2], 3)],
                    'p': [round(anchor[0] - pivot[0], 3),
                          round(-(anchor[1] - pivot[1]), 3),
                          round(-(anchor[2] - pivot[2]), 3)],
                }

            cubes.append({
                # blockbench measures y upward and the game's front is its -z:
                # both flip, which is a half turn and keeps the model's hands on
                'c': [round(middle[0] - pivot[0], 3),
                      round(-(middle[1] - pivot[1]), 3),
                      round(-(middle[2] - pivot[2]), 3)],
                's': [round(size[0] + 2 * grow, 3),
                      round(size[1] + 2 * grow, 3),
                      round(size[2] + 2 * grow, 3)],
                'f': faces,
                **spun,
            })
        parent = bone.get('parent')
        anchor = pivot
        bones.append({
            'name': bone['name'],
            'parent': parent,
            'pivot': [round(anchor[0], 3), round(-anchor[1], 3), round(-anchor[2], 3)],
            'rot': [round(sign[i] * turn[i] * math.pi / 180, 4) for i in range(3)],
            'cubes': cubes,
        })

    # a child's pivot is written in world terms, so take the parent's back off
    at = {b['name']: b['pivot'] for b in bones}
    for bone in bones:
        parent = bone['parent']
        if parent and parent in at:
            bone['pivot'] = [round(bone['pivot'][i] - at[parent][i], 3)
                             for i in range(3)]
    return bones, description


def geo_route(jar, names, ns, entity, family, fix=None):
    """Draw from a .geo.json, found by asking the mob's classes which one."""
    fix = fix or {}
    target = norm(entity)
    pool = [n for n in names
            if n.endswith('.geo.json') and n.startswith(f'assets/{ns}/')]

    named = []
    # the mob's own classes first, and the props it throws or stands on last
    own = [n for n in family if not any(w in os.path.basename(n).lower()
                                        for w in EXTRA)]
    ordered = ([n for n in own if exact(n, entity)]
               + [n for n in own if not exact(n, entity)]
               + [n for n in family if n not in own])
    for entry in ordered[:8]:
        _, geos = strings_in(jar, entry)
        for path in geos:
            full = f'assets/{ns}/{path}'
            if full in pool:
                named.append(full)

    # GeckoLib often builds the path from an id rather than writing it out, so
    # look the other way round: which model file does this mob's code mention?
    if not named:
        with zipfile.ZipFile(jar) as zf:
            blobs = [zf.read(e) for e in family[:8]]
        for path in pool:
            stem = os.path.basename(path)[:-len('.geo.json')]
            token = stem.encode()
            if any(token in blob for blob in blobs):
                named.append(path)

    if named:
        # order says which class named it, but a file called after the mob
        # itself outranks that: fdbosses points at malkuth_boss_spawner first
        hits = sorted(named, key=lambda n: (
            norm(os.path.basename(n)[:-len('.geo.json')]) != target,
            named.index(n)))
    else:
        hits = [n for n in pool if target in norm(os.path.basename(n))]
        hits.sort(key=lambda n: (norm(os.path.basename(n)[:-9]) != target, len(n)))
    if not hits:
        return None

    with zipfile.ZipFile(jar) as zf:
        model = json.loads(zf.read(hits[0]))
    # a pin may say how to read the file without naming which file it is
    bones, description = geo_bones(model, fix.get('mirror'), fix.get('spin'),
                                   fix.get('cubes'), fix.get('order'))
    if not any(b['cubes'] for b in bones):
        return None
    return {
        'bones': in_order(bones),
        'tw': description.get('texture_width', 64),
        'th': description.get('texture_height', 64),
        'source': hits[0],
        'route': 'geckolib',
    }


def exact(path, entity):
    """Whether this class is named for the mob itself, not one of its props."""
    base = norm(os.path.basename(path)[:-6])
    for tail in ('entitymodel', 'model', 'renderer', 'render', 'entity'):
        if base.endswith(tail):
            base = base[:-len(tail)]
    for head in ('model', 'new'):
        if base.startswith(head) and len(base) > len(head):
            base = base[len(head):]
    return base == norm(entity)


def java_route(jar, names, ns, entity, family):
    """Read the mesh out of the bytecode, whichever model API built it.

    A boss usually ships several models: itself, its shield, its armour, the
    shell it hides in. Those props are often the bigger mesh, so the class
    named for the mob wins outright and the rest are only a fallback.
    """
    models = [n for n in family if 'model' in n.lower()] or family
    own = [n for n in models if exact(n, entity)]
    if own:
        models = own + [n for n in models if n not in own]
    found_all = []
    seen = set()
    queue = list(models[:6])
    while queue:
        entry = queue.pop(0)
        if entry in seen:
            continue
        seen.add(entry)
        try:
            text = em.disassemble(jar, entry)
        except Exception:                             # noqa: BLE001
            continue

        # Twilight Forest's Ur-Ghast is a Ghast with extras: the boxes are all
        # in the class it extends, so follow the chain when a class is empty.
        parent = em.SUPER.search(text)
        if parent:
            base = parent.group(1).replace('.', '/') + '.class'
            if base in names and len(seen) < 6:
                queue.append(base)

        found = []
        mesh = em.parse(text)
        if mesh.bones:
            found.append(('vanilla', mesh.bones, mesh.size or (64, 64)))
        bones, size = em.parse_advanced(text)
        if bones:
            found.append(('advanced', bones, size or (64, 64)))

        for route, bones, size in found:
            cubes = sum(len(b['cubes']) for b in bones)
            if not cubes:
                continue
            found_all.append({'bones': in_order(bones), 'tw': size[0],
                              'th': size[1], 'source': entry, 'route': route,
                              'cubes': cubes})

    if not found_all:
        return None
    found_all.sort(key=lambda c: (0 if exact(c['source'], entity) else 1,
                                  -c['cubes']))
    return found_all[0]


# ── build ───────────────────────────────────────────────────────────────────

def pinned(boss, jar, names, ns):
    """A hand-pinned model and texture, if this boss has one."""
    fix = OVERRIDES.get(boss)
    if not fix:
        return None, None

    model = fix.get('model')
    if model and not model.startswith('assets/') and model.endswith('.geo.json'):
        model = f'assets/{ns}/{model}'
    if model and model not in names:
        raise SyncMiss(f'pinned model {model} is not in the jar')

    texture = fix.get('texture')
    if texture and not texture.startswith('assets/'):
        texture = f'assets/{ns}/{texture}'
    if texture and texture not in names:
        raise SyncMiss(f'pinned texture {texture} is not in the jar')
    return model, texture


class SyncMiss(RuntimeError):
    """A pin that points at something the jar does not have."""


def fold(bones, incoming):
    """Merge one class's bones into what is already read.

    A subclass names bones its parent class defines - Alex's Caves hangs the
    Luxtructosaurus's plates off a chest it never declares - and referencing
    one leaves an empty stand-in. Taking the first of each name would keep the
    stand-in and throw away the real thing, so they are merged rather than
    chosen between.

    A part the subclass does build, though, replaces its parent's rather than
    joining it: the call is addOrReplaceChild and the name says so. Keeping
    both leaves the mob wearing a second copy of itself.
    """
    have = {b['name']: b for b in bones}
    for bone in incoming:
        old = have.get(bone['name'])
        if old is None:
            bones.append(bone)
            have[bone['name']] = bone
            continue
        old['cubes'] = old['cubes'] or bone['cubes']
        if not old['parent'] and bone['parent']:
            old['parent'] = bone['parent']
        if not any(old['pivot']) and any(bone['pivot']):
            old['pivot'] = bone['pivot']
        if not any(old.get('rot') or ()) and any(bone.get('rot') or ()):
            old['rot'] = bone['rot']
    return bones


def in_order(bones):
    """Bones sorted so a parent always comes before its children.

    The renderer hangs each bone off whatever it has built already, so a child
    read before its parent would be left hanging off the model root instead.
    """
    left = list(bones)
    done, out = set(), []
    while left:
        ready = [b for b in left if not b['parent'] or b['parent'] in done]
        if not ready:                      # a cycle, or a parent that is not here
            out.extend(left)
            break
        for bone in ready:
            out.append(bone)
            done.add(bone['name'])
        left = [b for b in left if b not in ready]
    return out


# The game's own model classes, which a mod extends and only adds to. The
# client jar carries no names, so each is found the way the wither is: by the
# part names its mesh builder leaves in the constant pool.
VANILLA_MODELS = {
    'HumanoidModel': ('head', 'hat', 'body', 'right_arm', 'left_arm',
                      'right_leg', 'left_leg'),
}

_bases = {}


def vanilla_base(kind):
    """Find one of the game's own model classes in the obfuscated client jar.

    Several classes carry all the part names, because the subclasses carry
    them too. The one they all extend is the base, and that is the one with
    the parts in it.
    """
    if kind in _bases:
        return _bases[kind]
    marks = [word.encode() for word in VANILLA_MODELS.get(kind, ())]
    hits = []
    if marks:
        with zipfile.ZipFile(em.JAR) as zf:
            for name in zf.namelist():
                if name.endswith('.class') and '$' not in name:
                    if all(mark in zf.read(name) for mark in marks):
                        hits.append(name)
    parents = set()
    for hit in hits:
        above = em.SUPER.search(em.disassemble(em.JAR, hit))
        if above:
            parents.add(above.group(1).replace('.', '/') + '.class')
    _bases[kind] = next((h for h in hits if h in parents), None)
    return _bases[kind]


def read_model(jar, names, ns, entity, path, mirror=False, spin=None,
               cubespin=None, order=None):
    """One named model file or class, read with whichever reader suits it."""
    if path.endswith('.geo.json'):
        with zipfile.ZipFile(jar) as zf:
            model = json.loads(zf.read(path))
        bones, description = geo_bones(model, mirror, spin, cubespin, order)
        return {'bones': in_order(bones),
                'tw': description.get('texture_width', 64),
                'th': description.get('texture_height', 64),
                'source': path, 'route': 'geckolib'}

    # A model often adds a few parts to one it extends - Twilight Forest's
    # snow queen declares none of her own - so the chain is read and merged,
    # the class's own bones first.
    route, bones, size, seen = None, [], None, set()
    entry = path
    for _ in range(4):
        if not entry or entry in seen or entry not in names:
            break
        seen.add(entry)
        text = em.disassemble(jar, entry)

        got = None
        mesh = em.parse(text)
        if any(b['cubes'] for b in mesh.bones):
            got = ('vanilla', mesh.bones, mesh.size)
        more, other = em.parse_advanced(text)
        if any(b['cubes'] for b in more) and (
                got is None or sum(len(b['cubes']) for b in more) >
                sum(len(b['cubes']) for b in got[1])):
            got = ('advanced', more, other)

        if got:
            route = route or got[0]
            size = size or got[2]
            bones = fold(bones, got[1])

        parent = em.SUPER.search(text)
        entry = (parent.group(1).replace('.', '/') + '.class') if parent else None

    # and the chain may run out of the mod and into one of the game's own: a
    # model that extends HumanoidModel writes down only what it changes, and
    # taken alone is a knight with no head on it
    if entry and entry not in names:
        base = vanilla_base(os.path.basename(entry)[:-len('.class')])
        if base:
            mesh = em.parse(em.disassemble(em.JAR, base))
            if any(b['cubes'] for b in mesh.bones):
                route = route or 'vanilla'
                bones = fold(bones, mesh.bones)

    if not bones:
        return None
    # a model that leaves its sheet size to the game says nothing about it, and
    # the classic biped sheet is not the size of the modern one
    guessed = size is None
    size = size or (64, 64)
    return {'bones': in_order(bones), 'tw': size[0], 'th': size[1],
            'guessed': guessed,
            'source': path, 'route': route or 'vanilla'}


def veiled(data, strength):
    """Lift a barrier's alpha so it still reads on a card.

    A shell like the Shelterer's is drawn at a twelfth of full alpha: enough to
    tint a lit world, nothing at all against the black a card sits on. Scaling
    the whole sheet so its strongest pixel lands at `strength` keeps the shape
    and the falloff and only changes how much of it survives the background.
    """
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(data)).convert('RGBA')
    alpha = img.getchannel('A')
    top = max(alpha.getdata()) or 255
    lift = min(255.0 * strength / top, 255.0 / top)
    img.putalpha(alpha.point(lambda v: min(255, int(v * lift))))
    out = io.BytesIO()
    img.save(out, 'PNG')
    return out.getvalue()


def train_bones(found, jar, names, ns, entity, spec):
    """Hang a line of body segments off a mob that is really a chain of them.

    A serpent boss is not one entity: it is a head, and behind it a train of
    part entities the game spaces out along its length, each drawn from a model
    of its own. Read whole, a card shows a head and nothing else. This reads the
    segment model once, lays copies of it down the mob's own axis, and gives the
    last one the tail. The copies keep their own sheet, named as a second skin.
    """
    step = spec.get('step', 48)
    seg = read_model(jar, names, ns, entity, spec['model'],
                     spec.get('mirror'), spec.get('spin'))
    if not seg:
        return found

    body, tail = set(spec.get('body', ())), set(spec.get('tail', ()))

    def undrawn(bones, cut):
        """the named bones and everything hanging off them, by name"""
        gone = set(cut)
        for bone in bones:
            if bone['parent'] in gone:
                gone.add(bone['name'])
        return gone

    grown = list(found['bones'])
    for i in range(spec.get('count', 4)):
        last = i == spec.get('count', 4) - 1
        gone = undrawn(seg['bones'], body if last else tail)
        # the mob's own front is its +z, so the train runs the other way. The
        # stem stands where the head's own root does, which is why it hangs off
        # nothing rather than off the head: a segment carries the same root
        # offset the head does, and hanging one off the other counts it twice.
        stem = f'segment{i}'
        grown.append({'name': stem, 'parent': None,
                      'pivot': [0, 0, -(spec.get('gap', step) + i * step)],
                      'rot': [0, 0, 0], 'cubes': [], 'skin': 1})
        for bone in seg['bones']:
            place = dict(bone)
            place['name'] = f'{stem}_{bone["name"]}'
            place['parent'] = (f'{stem}_{bone["parent"]}' if bone['parent']
                               else stem)
            place['cubes'] = [] if bone['name'] in gone else bone['cubes']
            place['skin'] = 1
            grown.append(place)

    return {**found, 'bones': grown,
            'segment': {'tw': seg['tw'], 'th': seg['th'],
                        'source': seg['source']}}


def graft_bones(found, jar, names, ns, entity, spec):
    """Hang a second model off one of this mob's own bones.

    A mob is not always one model. The Mutant Skeleton carries a crossbow
    that is a model of its own with a sheet of its own, drawn by a layer that
    walks down the arm and draws it at the hand; read alone the skeleton
    stands there empty-handed. This reads that second model, poses it, and
    parents it where the layer leaves it. It keeps its own sheet, named as a
    second skin the same way a serpent's segments are.
    """
    held = read_model(jar, names, ns, entity, spec['model'],
                      spec.get('mirror'), spec.get('spin'))
    if not held:
        return found

    for name, turn in (spec.get('rest') or {}).items():
        for bone in held['bones']:
            if bone['name'] == name:
                bone['rot'] = [round(-turn[0], 4), round(-turn[1], 4),
                               round(turn[2], 4)]

    tag = spec.get('prefix', 'held')
    at = spec.get('at') or (0, 0, 0)
    grown = list(found['bones'])
    for bone in held['bones']:
        place = dict(bone)
        place['name'] = f'{tag}_{bone["name"]}'
        if bone['parent']:
            place['parent'] = f'{tag}_{bone["parent"]}'
        else:
            # the layer draws it at the end of a bone, not at its root
            place['parent'] = spec['parent']
            place['pivot'] = [round(place['pivot'][i] + at[i], 3)
                              for i in range(3)]
        place['skin'] = 1
        grown.append(place)

    return {**found, 'bones': grown,
            'segment': {'tw': held['tw'], 'th': held['th'],
                        'source': held['source']}}


def build(boss, jars, listing, write=True):
    ns, entity = boss.split(':')
    if ns == 'minecraft':
        # the game's own mobs come out of the client jar, not a mod
        spec = em.MOBS.get(entity)
        if not spec:
            return {'id': boss, 'ok': False,
                    'why': 'vanilla builds this one by hand'}
        if write:
            em.build(entity, spec)
        return {'id': boss, 'key': entity, 'route': 'client', 'ok': True,
                'name': spec['name'], 'mod': 'minecraft',
                'bones': 0, 'cubes': 0, 'source': spec['marker']}

    jar = jars.get(ns)
    if not jar:
        return {'id': boss, 'route': None, 'ok': False, 'why': 'no jar'}
    names = listing[jar]
    family = kin(names, ns, entity)
    if not family:
        return {'id': boss, 'route': None, 'ok': False, 'why': 'no class of that name'}

    fix = OVERRIDES.get(boss, {})
    try:
        pin_model, pin_texture = pinned(boss, jar, names, ns)
    except SyncMiss as exc:
        return {'id': boss, 'route': None, 'ok': False, 'why': str(exc)}

    found = None
    if pin_model:
        found = read_model(jar, names, ns, entity, pin_model,
                           fix.get('mirror'), fix.get('spin'),
                           fix.get('cubes'), fix.get('order'))
    if not found:
        found = (geo_route(jar, names, ns, entity, family, fix)
                 or java_route(jar, names, ns, entity, family))
    if not found:
        return {'id': boss, 'route': None, 'ok': False, 'why': 'no model found'}

    # A rig can hold the same mob several times over: one build per phase, the
    # skeleton that is under the armour, spare weapons the animation hands it,
    # all standing in the rest pose at once. Naming the parts of the one it
    # wears empties the rest and leaves the tree they hang from alone.
    if fix.get('keep'):
        worn = set(fix['keep'])
        for bone in found['bones']:
            if bone['name'] not in worn:
                bone['cubes'] = []
    # A prop the fight draws for one attack is easier named than kept around:
    # dropping a bone takes everything hanging off it too.
    if fix.get('drop'):
        gone = set(fix['drop'])
        for bone in found['bones']:
            if bone['parent'] in gone:
                gone.add(bone['name'])
            if bone['name'] in gone:
                bone['cubes'] = []
    # and a bone the mob does need can still carry a box it does not: a slash
    # the fight draws, a prop parked on a shoulder. Those go one at a time.
    for name, index in fix.get('hide') or ():
        for bone in found['bones']:
            if bone['name'] == name and index < len(bone['cubes']):
                bone['cubes'].pop(index)

    # The class that names a texture matters as much as the name: a renderer
    # names the mob's skin, a layer class names the coat over it.
    plain, extra = [], []
    for entry in family[:10]:
        pngs, _ = strings_in(jar, entry)
        if not pngs:
            continue
        low = os.path.basename(entry).lower()
        (extra if any(word in low for word in EXTRA) else plain).extend(pngs)
    named = plain + extra
    sheet = (found['tw'], found['th'])
    texture = (pin_texture
               or pick_texture(jar, names, ns, entity, named, sheet)
               or near_texture(names, ns, found['source'], jar, sheet)
               or any_texture(jar, names, ns, sheet, entity, found['source']))
    if not texture:
        return {'id': boss, 'route': found['route'], 'ok': False,
                'why': 'no texture', 'source': found['source']}

    # A part built in a loop leaves the reader nothing to follow: no names, no
    # measurements, just a counter and a call. What that loop makes is written
    # down here instead, worked out from the code once. The sixth, optional
    # element mirrors the box, for a part on a rig's other side drawn from the
    # same corner of the sheet. A box of None is a bare pivot - a joint the
    # loop parents its own next part to rather than draws anything of its own.
    for part in fix.get('parts') or ():
        name, parent, pivot, box, uv = part[:5]
        mirror = part[5] if len(part) > 5 else False
        cubes = []
        if box is not None:
            x, y, z, w, h, d = box
            faces = em.box_uv(uv[0], uv[1], w, h, d)
            cubes.append({
                'c': [round(x + w / 2, 3), round(y + h / 2, 3),
                      round(-(z + d / 2), 3)],
                's': [w, h, d],
                'f': em.mirrored(faces) if mirror else faces,
            })
        found['bones'].append({
            'name': name, 'parent': parent, 'rot': [0, 0, 0],
            'pivot': [pivot[0], pivot[1], -pivot[2]],
            'cubes': cubes,
        })

    # The pose a mob is actually seen in.
    #
    # createBodyLayer builds the mesh, and for a good many mobs what it builds
    # is not the creature: it is a rack of parts all square to each other,
    # which setupAnim then bends into an animal every single frame before the
    # first one is ever drawn. The Mutant Enderman's arms hang flat at its
    # sides there, its legs run straight down, and read as built it is a
    # black post. So the rest pose those methods assign is written down here
    # and baked in, in the game's own axes - x and y turn round on the way
    # into the portal's, the same way a PartPose's own rotation does.
    for name, turn in (fix.get('rest') or {}).items():
        for bone in found['bones']:
            if bone['name'] == name:
                bone['rot'] = [round(-turn[0], 4), round(-turn[1], 4),
                               round(turn[2], 4)]

    # The same thing said as a lean rather than a pose.
    #
    # Where a vanilla model assigns its idle angles outright, mutantmore's
    # rigs add theirs: every frame an idle animation sways each bone about a
    # fixed offset, and that offset - not the mesh - is the stance the mob is
    # seen in. Degrees, in the game's axes, added to whatever the bone was
    # built with rather than put in its place.
    for name, turn in (fix.get('lean') or {}).items():
        for bone in found['bones']:
            if bone['name'] == name:
                held = bone.get('rot') or [0, 0, 0]
                bone['rot'] = [round(held[0] - turn[0] * math.pi / 180, 4),
                               round(held[1] - turn[1] * math.pi / 180, 4),
                               round(held[2] + turn[2] * math.pi / 180, 4)]

    # A part the reader did find, but hung off the wrong thing: a loop built
    # bone the reader has no name for stands between it and its real parent,
    # so it lands on the root instead. Said here rather than guessed at.
    if fix.get('reparent'):
        for bone in found['bones']:
            if bone['name'] in fix['reparent']:
                bone['parent'] = fix['reparent'][bone['name']]

    # the renderer hangs each bone off whatever it has built already, so
    # parts and a reparent both have to leave every parent still ahead of
    # its children
    if fix.get('parts') or fix.get('reparent'):
        found['bones'] = in_order(found['bones'])

    # where the model said nothing, the sheet it is pinned to is the answer
    if found.get('guessed') and pin_texture:
        found['tw'], found['th'] = png_size(jar, pin_texture)

    if fix.get('train'):
        found = train_bones(found, jar, names, ns, entity, fix['train'])
    # and a mob may simply be holding something the renderer draws from a
    # model of its own
    if fix.get('graft'):
        found = graft_bones(found, jar, names, ns, entity, fix['graft'])
        found['bones'] = in_order(found['bones'])

    # A mob may wear one sheet over part of itself and another over the rest:
    # the Shelterer's inner head is drawn from its own skin and the shell it
    # sits in from a second, which is why the shell's corner of the first is
    # blank. Naming the bones is all it takes; they read the second instead.
    for name in (fix.get('skin') or {}).get('bones', ()):
        for bone in found['bones']:
            if bone['name'] == name:
                bone['skin'] = 1
    # The second sheet need not be measured the way the first is. A layer may
    # build the part it draws from a mesh of its own declared against a
    # smaller sheet, and the file shipped for it can still be a finer copy:
    # what matters is the size the boxes were laid out against, not the pixels.
    if (fix.get('skin') or {}).get('size'):
        wide, tall = fix['skin']['size']
        found['segment'] = {'tw': wide, 'th': tall}

    key = f'{ns}__{entity}'
    if write:
        os.makedirs(OUT, exist_ok=True)
        under = fix.get('ghost')
        if under and not under.startswith('assets/'):
            under = f'assets/{ns}/{under}'
        worn = fix.get('coat')
        if worn and not worn.startswith('assets/'):
            worn = f'assets/{ns}/{worn}'
        second = (fix.get('train') or fix.get('skin')
                  or fix.get('graft') or {}).get('texture')
        if second and not second.startswith('assets/'):
            second = f'assets/{ns}/{second}'
        with zipfile.ZipFile(jar) as zf:
            with open(os.path.join(OUT, f'{key}.png'), 'wb') as fh:
                fh.write(zf.read(texture))
            if under:
                with open(os.path.join(OUT, f'{key}_ghost.png'), 'wb') as fh:
                    fh.write(zf.read(under))
            if worn:
                with open(os.path.join(OUT, f'{key}_coat.png'), 'wb') as fh:
                    fh.write(zf.read(worn))
            if second:
                raw = zf.read(second)
                veil = (fix.get('skin') or {}).get('veil')
                with open(os.path.join(OUT, f'{key}_skin.png'), 'wb') as fh:
                    fh.write(veiled(raw, veil) if veil else raw)
        model = {
            'id': boss, 'name': pretty(entity), 'mod': ns,
            **({'zoom': fix['zoom']} if fix.get('zoom') else {}),
            **({'pose': fix['pose']} if fix.get('pose') else {}),
            **({'focus': fix['focus']} if fix.get('focus') else {}),
            **({'ghost': f'{key}_ghost.png'} if fix.get('ghost') else {}),
            **({'coat': f'{key}_coat.png'} if fix.get('coat') else {}),
            # a bone may name a skin of its own; the mob's own is always first
            **({'skins': [
                {'texture': f'{key}.png',
                 'tw': found['tw'], 'th': found['th']},
                {'texture': f'{key}_skin.png',
                 'tw': (found.get('segment') or found)['tw'],
                 'th': (found.get('segment') or found)['th'],
                 **({'veil': True}
                    if (fix.get('skin') or {}).get('veil') else {})},
            ]} if second else {}),
            'tw': found['tw'], 'th': found['th'], 'texture': f'{key}.png',
            'bones': found['bones'], 'source': found['source'],
            'sheet': texture,
            # a sheet that is not the size the model was drawn for reads every
            # face off the wrong part of it: worth knowing, not worth dropping
            'fits': png_size(jar, texture) == (found['tw'], found['th']),
        }
        with open(os.path.join(OUT, f'{key}.model.json'), 'w') as fh:
            json.dump(model, fh, separators=(',', ':'))

    return {'id': boss, 'key': key, 'route': found['route'], 'ok': True,
            'name': pretty(entity), 'mod': ns,
            'cubes': sum(len(b['cubes']) for b in found['bones']),
            'bones': len(found['bones']), 'source': found['source'],
            'texture': texture}


def main():
    write = '--list' not in sys.argv
    bosses = read_tag(TAG)
    # pinning one boss at a time means rebuilding one, not all sixty
    only = [a for a in sys.argv[1:] if not a.startswith('--')]
    if only:
        bosses = [b for b in bosses if any(o in b for o in only)]
    jars, listing = index_jars(MODS)

    done, failed = [], []
    for boss in bosses:
        try:
            result = build(boss, jars, listing, write)
        except Exception as exc:                      # noqa: BLE001
            result = {'id': boss, 'ok': False, 'why': f'{type(exc).__name__}: {exc}'}
        (done if result.get('ok') else failed).append(result)
        if result.get('ok') and result.get('route') != 'vanilla-jar':
            print(f'  {boss:<44} {result["route"]:<9} '
                  f'{result["bones"]:>3} bones {result["cubes"]:>4} cubes')
        elif not result.get('ok'):
            print(f'  {boss:<44} -- {result.get("why")}')

    if write and not only:
        index = [{'key': r['key'], 'id': r['id'], 'name': r['name'],
                  'mod': r['mod'], 'model': f'{r["key"]}.model.json'}
                 for r in done]
        index.sort(key=lambda b: (b['mod'] != 'minecraft', b['mod'], b['name']))
        with open(os.path.join(OUT, 'index.json'), 'w') as fh:
            json.dump(index, fh, indent=1)
        print(f'index    {len(index)} bosses')

    print(f'\n{len(done)} built, {len(failed)} skipped')
    for miss in failed:
        print(f'  missing: {miss["id"]} - {miss.get("why")}')
    return done, failed


if __name__ == '__main__':
    main()
