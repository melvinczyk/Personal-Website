"""Convert a Blockbench/GeckoLib .geo.json armor model into cubes the gallery
can build out of CSS boxes.

Mods that draw their own armor ship a Bedrock-format model instead of the two
flat sheets vanilla uses. The format is a bone tree of axis-aligned cubes, which
is exactly what the player model already is, so the work is coordinate
conversion plus dropping everything that would render as nothing.

Coordinates: Blockbench measures from the feet with +y up and the model facing
-z. The gallery measures from the middle of the figure with +y down and the
model facing +z, so y' = 16 - y and z' = -z, which is a half turn about x.
"""

import json
import math

# Where each biped bone attaches on the gallery's model, in its own units.
ATTACH = {
    'head': (0, -12, 0),
    'body': (0, -2, 0),
    'armR': (-6, -2, 0),
    'armL': (6, -2, 0),
    'legR': (-2, 10, 0),
    'legL': (2, 10, 0),
}

# The biped bone a set's own bones hang off, however the mod spells it.
PARENTS = [
    ('head', 'head'),
    ('body', 'body'), ('torso', 'body'), ('chest', 'body'),
    ('leftarm', 'armL'), ('rightarm', 'armR'),
    ('leftleg', 'legL'), ('rightleg', 'legR'),
    ('leftboot', 'legL'), ('rightboot', 'legR'),
    ('leftfoot', 'legL'), ('rightfoot', 'legR'),
    ('leftshoe', 'legL'), ('rightshoe', 'legR'),
]

FACE_NAMES = {'north': 'front', 'south': 'back', 'east': 'right',
              'west': 'left', 'up': 'top', 'down': 'bottom'}


def part_of(bone_name, parent_name):
    """Which limb a bone rides on. The parent is authoritative: at least one
    mod ships a left leg bone parented to the right leg."""
    for needle, part in PARENTS:
        if needle in (parent_name or '').lower().replace('_', ''):
            return part
    for needle, part in PARENTS:
        if needle in bone_name.lower().replace('_', ''):
            return part
    return None


def slot_of(bone_name, part):
    """Which equipment slot draws this bone."""
    if 'boot' in bone_name.lower() or 'feet' in bone_name.lower():
        return 'feet'
    if part == 'head':
        return 'head'
    if part in ('body', 'armL', 'armR'):
        return 'chest'
    return 'legs'


def box_uv(u, v, w, h, d):
    """The unwrap Blockbench uses when a cube has a single uv origin."""
    return {
        'top':    [u + d,         v,     w, d],
        'bottom': [u + d + w,     v,     w, d],
        'right':  [u,             v + d, d, h],
        'front':  [u + d,         v + d, w, h],
        'left':   [u + d + w,     v + d, d, h],
        'back':   [u + d + w + d, v + d, w, h],
    }


def cube_faces(cube):
    uv = cube.get('uv')
    size = cube['size']
    if isinstance(uv, list):
        # a cube may be any fraction of a block, but the game lays its faces
        # out on the sheet as if it were the whole number of pixels below, so
        # anything finer than a pixel is stretched rather than given its own
        w, h, d = (math.floor(v) for v in size)
        return box_uv(uv[0], uv[1], w, h, d)

    out = {}
    for key, name in FACE_NAMES.items():
        face = (uv or {}).get(key)
        if not face:
            continue
        u, v = face['uv']
        w, h = face.get('uv_size', [0, 0])
        flip = ('x' if w < 0 else '') + ('y' if h < 0 else '')
        if w < 0:
            u, w = u + w, -w
        if h < 0:
            v, h = v + h, -h
        if not w or not h:
            continue
        out[name] = [u, v, w, h] + ([flip] if flip else [])
    return out


def convert_cube(cube, attach):
    size = [float(v) for v in cube['size']]
    grow = float(cube.get('inflate', 0) or 0)
    origin = [float(v) for v in cube['origin']]

    # blockbench gives the low corner; the gallery positions boxes by centre
    cx = origin[0] + size[0] / 2
    cy = origin[1] + size[1] / 2
    cz = origin[2] + size[2] / 2

    out = {
        'c': [round(cx - attach[0], 3),
              round((16 - cy) - attach[1], 3),
              round(-cz - attach[2], 3)],
        's': [round(size[0] + 2 * grow, 3),
              round(size[1] + 2 * grow, 3),
              round(size[2] + 2 * grow, 3)],
        'u': [round(size[0], 3), round(size[1], 3), round(size[2], 3)],
        'f': cube_faces(cube),
    }

    rotation = cube.get('rotation')
    if rotation and any(rotation):
        pivot = [float(v) for v in cube.get('pivot', [cx, cy, cz])]
        # flipping y and z turns the y and z rotations around with them
        out['r'] = [round(rotation[0], 3), round(-rotation[1], 3), round(-rotation[2], 3)]
        out['p'] = [round(pivot[0] - attach[0], 3),
                    round((16 - pivot[1]) - attach[1], 3),
                    round(-pivot[2] - attach[2], 3)]
    return out


EPS = 1e-4

# For each face: the axis it faces, its direction, and the two axes it spans.
FACE_AXES = {
    'front':  (2,  1, 0, 1), 'back':   (2, -1, 0, 1),
    'left':   (0,  1, 2, 1), 'right':  (0, -1, 2, 1),
    'bottom': (1,  1, 0, 2), 'top':    (1, -1, 0, 2),
}


def bounds(cube):
    return [(cube['c'][i] - cube['s'][i] / 2, cube['c'][i] + cube['s'][i] / 2)
            for i in range(3)]


def spin(point, degrees):
    """The same z, y, x order the model is drawn with."""
    x, y, z = point
    for axis, angle in ((2, degrees[2]), (1, degrees[1]), (0, degrees[0])):
        if not angle:
            continue
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        if axis == 2:
            x, y = x * c - y * s, x * s + y * c
        elif axis == 1:
            x, z = x * c + z * s, -x * s + z * c
        else:
            y, z = y * c - z * s, y * s + z * c
    return [x, y, z]


def face_corners(cube, name):
    """The four corners of one face, wherever the cube's own rotation puts it."""
    axis, direction, span_a, span_b = FACE_AXES[name]
    half = [cube['s'][i] / 2 for i in range(3)]
    corners = []
    for a in (-1, 1):
        for b in (-1, 1):
            local = [0, 0, 0]
            local[axis] = direction * half[axis]
            local[span_a] = a * half[span_a]
            local[span_b] = b * half[span_b]
            if cube.get('r'):
                local = spin(local, cube['r'])
                pivot = cube['p']
                offset = [cube['c'][i] - pivot[i] for i in range(3)]
                offset = spin(offset, cube['r'])
                corners.append([pivot[i] + offset[i] + local[i] for i in range(3)])
            else:
                corners.append([cube['c'][i] + local[i] for i in range(3)])
    return corners


def bury(cubes):
    """Drop every face that is sealed inside another cube of the same bone.

    These sets are built by piling boxes on top of each other, so a good part
    of any of them is buried in the rest. A face whose four corners all sit
    inside another box can never be seen, whichever way the cube is turned.
    """
    solids = [bounds(c) for c in cubes if not c.get('r')]

    for cube in cubes:
        own = None if cube.get('r') else bounds(cube)
        kept = {}
        for name, rect in cube['f'].items():
            corners = face_corners(cube, name)
            buried = False
            for other in solids:
                if other is own:
                    continue
                if all(other[i][0] + EPS < p[i] < other[i][1] - EPS
                       for p in corners for i in range(3)):
                    buried = True
                    break
            if not buried:
                kept[name] = rect
        cube['f'] = kept

    return [c for c in cubes if c['f']]


def convert(model, keep_face=None):
    """geo json -> {slot: {part: [cube, ...]}}.

    keep_face(u, v, w, h) may say a face is entirely transparent, in which case
    it is dropped along with any cube left with nothing to draw.
    """
    geometry = model['minecraft:geometry'][0]
    description = geometry['description']
    parents = {b['name']: b.get('parent') for b in geometry['bones']}

    slots = {}
    for bone in geometry['bones']:
        cubes = bone.get('cubes') or []
        if not cubes:
            continue
        part = part_of(bone['name'], parents.get(bone['name']))
        if not part:
            continue
        slot = slot_of(bone['name'], part)

        kept = []
        for cube in cubes:
            if not cube.get('size') or not cube.get('origin'):
                continue
            converted = convert_cube(cube, ATTACH[part])
            if keep_face:
                converted['f'] = {name: rect for name, rect in converted['f'].items()
                                  if keep_face(*rect[:4])}
            if converted['f']:
                kept.append(converted)

        if kept:
            slots.setdefault(slot, {}).setdefault(part, []).extend(kept)

    for parts in slots.values():
        for part, cubes in parts.items():
            parts[part] = bury(cubes)

    return {
        'tw': description.get('texture_width', 64),
        'th': description.get('texture_height', 64),
        'slots': slots,
    }
