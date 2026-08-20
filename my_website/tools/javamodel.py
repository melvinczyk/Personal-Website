"""Recover an armor model that a mod wrote in Java rather than shipping as json.

Some mods build their armor with Minecraft's own model API: a tree of parts,
each a list of boxes with a texture offset. None of that survives into the
assets, but it does survive into the bytecode, where the arguments are plain
constants pushed in order. javap prints them, so the model can be read straight
back out of the class file.

The bytecode reads like this, one child part at a time:

    aload_3                       the parent part
    ldc "tuskRight1"              its name
    CubeListBuilder.create()
    bipush 40, bipush 24          texOffs(40, 24)
    ldc -1.5f ... ldc 5.0f        addBox(x, y, z, w, h, d)
    ldc -2.5f ... fconst_0        PartPose.offsetAndRotation(...)
    PartDefinition.addOrReplaceChild(...)
    astore 4                      bound, so later parts can hang off it
"""

import math
import re
import subprocess

from geo import ATTACH, box_uv, part_of, slot_of

# Mojang's names are obfuscated in a shipped jar; these are the ones that matter.
CALLS = {
    'm_171576_': 'root',            # MeshDefinition.getRoot
    'm_171597_': 'child',           # PartDefinition.getChild(name)
    'm_171599_': 'add',             # PartDefinition.addOrReplaceChild(name, cubes, pose)
    'm_171558_': 'create',          # CubeListBuilder.create
    'm_171514_': 'texoffs',         # CubeListBuilder.texOffs(u, v)
    'm_171480_': 'mirror_on',       # CubeListBuilder.mirror()
    'm_171555_': 'mirror_set',      # CubeListBuilder.mirror(boolean)
    'm_171488_': 'addbox',          # CubeListBuilder.addBox(x, y, z, w, h, d, deform)
    'm_171481_': 'addbox',          # CubeListBuilder.addBox(x, y, z, w, h, d)
    'm_171506_': 'addbox_named',    # CubeListBuilder.addBox(name, x, y, z, w, h, d)
    'm_171419_': 'offset',          # PartPose.offset(x, y, z)
    'm_171423_': 'offset_rot',      # PartPose.offsetAndRotation(x, y, z, rx, ry, rz)
    'm_171565_': 'layer',           # LayerDefinition.create(mesh, width, height)
}

PUSH = re.compile(r'^\s*\d+:\s+(ldc\w*|bipush|sipush|iconst_(\S+)|fconst_(\S+)|dconst_\S+)\s*(#?\S+)?'
                  r'(?:\s+//\s+(?:float|int|double|String)?\s*(.*))?$')
CALL = re.compile(r'^\s*\d+:\s+invoke\w+\s+#\d+\s+// Method (?:[\w/$]+\.)?"?([\w$<>]+)"?:')
STORE = re.compile(r'^\s*\d+:\s+astore(?:_(\d+)|\s+(\d+))')
LOAD  = re.compile(r'^\s*\d+:\s+aload(?:_(\d+)|\s+(\d+))')
FIELD = re.compile(r'^\s*\d+:\s+getstatic\s+#\d+\s+// Field ([\w/$]+)\.([\w$]+)')


def numbers(line):
    """The constant a push instruction puts on the stack, if it is a number."""
    m = PUSH.match(line)
    if not m:
        return None
    kind, icon, fcon, operand, comment = m.groups()
    if icon is not None:
        return -1.0 if icon == 'm1' else float(icon)
    if fcon is not None:
        return float(fcon)
    if kind in ('bipush', 'sipush'):
        return float(operand)
    if comment:                       # ldc, whose value javap prints as a comment
        text = comment.strip().rstrip('fd')
        try:
            return float(text)
        except ValueError:
            return None
    return None


def strings(line):
    m = re.match(r'^\s*\d+:\s+ldc\w*\s+#\d+\s+// String (.*)$', line)
    return m.group(1) if m else None


class Part:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.offset = (0.0, 0.0, 0.0)
        self.rotation = (0.0, 0.0, 0.0)
        self.cubes = []


def disassemble(class_path):
    return subprocess.run(['javap', '-c', '-p', class_path],
                          capture_output=True, text=True, check=True).stdout


def parse(listing):
    """Read the class back into a part tree plus the sheet size."""
    parts, slots = [], {}
    stack, words = [], []
    root = Part('#root', None)
    parts.append(root)

    holder = root          # the part the child being built hangs off
    pending = root         # the part most recently loaded onto the stack
    name = '?'
    cubes, texoff, mirror, deform = [], (0, 0), False, 0.0
    pose = None
    sheet = (64, 32)

    for line in listing.splitlines():
        value = numbers(line)
        if value is not None:
            stack.append(value)
            continue
        word = strings(line)
        if word is not None:
            words.append(word)
            continue

        m = FIELD.match(line)
        if m and m.group(2).startswith('f_171404_'):
            pose = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))     # PartPose.ZERO
            continue

        m = LOAD.match(line)
        if m:
            slot = int(m.group(1) or m.group(2))
            if slot in slots:
                pending = slots[slot]
            continue

        m = STORE.match(line)
        if m and parts:
            slots[int(m.group(1) or m.group(2))] = parts[-1]
            continue

        m = CALL.match(line)
        if not m:
            continue
        call = CALLS.get(m.group(1))

        if m.group(1) == '<init>' and 'CubeDeformation' in line:
            deform = stack.pop() if stack else 0.0
        elif call == 'root':
            parts[-1] = root
        elif call == 'child':
            part = Part(words[-1] if words else '?', pending)
            words.clear()
            parts.append(part)
        elif call == 'create':
            # the child's name is the last string pushed before its boxes, and
            # its parent the last part loaded: taking them here rather than at
            # the end keeps a stray constant from shifting everything along
            name = words[-1] if words else '?'
            holder = pending
            words.clear()
            cubes, texoff, mirror, deform = [], (0, 0), False, 0.0
        elif call == 'texoffs':
            v, u = stack.pop(), stack.pop()
            texoff = (u, v)
        elif call == 'mirror_on':
            mirror = True
        elif call == 'mirror_set':
            mirror = bool(stack.pop())
        elif call in ('addbox', 'addbox_named'):
            if call == 'addbox_named' and words:
                words.pop()
            box = [stack.pop() for _ in range(6)][::-1]
            cubes.append({'origin': box[:3], 'size': box[3:], 'grow': deform,
                          'uv': texoff, 'mirror': mirror})
            deform = 0.0
        elif call == 'offset':
            z, y, x = stack.pop(), stack.pop(), stack.pop()
            pose = ((x, y, z), (0.0, 0.0, 0.0))
        elif call == 'offset_rot':
            values = [stack.pop() for _ in range(6)][::-1]
            pose = (tuple(values[:3]), tuple(values[3:]))
        elif call == 'add':
            part = Part(name, holder)
            part.cubes = cubes
            if pose:
                part.offset, part.rotation = pose
            parts.append(part)
            cubes, pose = [], None
        elif call == 'layer':
            height, width = stack.pop(), stack.pop()
            sheet = (int(width), int(height))

    return [p for p in parts if p is not root], sheet


# --- turning the tree into the portal's cubes -----------------------------

def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rotation_matrix(rx, ry, rz):
    """Minecraft turns a part about z, then y, then x."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    return matmul(matmul(Rz, Ry), Rx)


def apply(matrix, vector):
    return [sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3)]


def euler_zyx(m):
    """Back out the z, y, x angles the portal will replay, in degrees.

    The portal rebuilds the turn as Rz then Ry then Rx, and for that product
    m[2][0] is -sin(y), m[2][1]/m[2][2] give x and m[1][0]/m[0][0] give z.
    """
    sy = max(-1.0, min(1.0, -m[2][0]))
    ry = math.asin(sy)
    if abs(sy) < 0.99999:
        rx = math.atan2(m[2][1], m[2][2])
        rz = math.atan2(m[1][0], m[0][0])
    else:
        rx = math.atan2(-m[1][2], m[1][1])
        rz = 0.0
    return [round(math.degrees(v), 3) for v in (rx, ry, rz)]


# the model's own axes put y downward from the neck and the face toward -z
def to_portal(point):
    return [point[0], point[1], -point[2]]


def convert(parts, sheet, binding=None, slot=None):
    """parts -> {slot: {body part: [cube, ...]}} in the portal's coordinates.

    `binding` names the limb each top part rides on, for a model whose own
    names say nothing (the item class is what pairs them up). `slot` forces
    the equipment slot, for the same reason.
    """
    tw, th = sheet
    placed = {}

    for part in parts:
        chain = []
        node = part
        while node is not None:
            chain.append(node)
            node = node.parent
        chain.reverse()

        limb, top = None, ''
        for node in chain:                       # the topmost part names the limb
            if limb is not None:
                continue
            found = binding.get(node.name) if binding else part_of(node.name, None)
            if found:
                limb, top = found, node.name
        if not limb or not part.cubes:
            continue

        # walk down the chain accumulating where this part ended up
        translation = [0.0, -8.0, 0.0]           # the root sits at the neck
        matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for node in chain:
            step = apply(matrix, to_portal(node.offset))
            translation = [translation[i] + step[i] for i in range(3)]
            rx, ry, rz = node.rotation
            matrix = matmul(matrix, rotation_matrix(-rx, -ry, rz))

        anchor = ATTACH[limb]
        pivot = [round(translation[i] - anchor[i], 3) for i in range(3)]
        angles = euler_zyx(matrix)

        for cube in part.cubes:
            x, y, z = cube['origin']
            w, h, d = cube['size']
            grow = cube['grow']
            centre = to_portal([x + w / 2, y + h / 2, z + d / 2])

            faces = box_uv(cube['uv'][0], cube['uv'][1], w, h, d)
            if cube['mirror']:
                faces['left'], faces['right'] = faces['right'], faces['left']
                for name in ('front', 'back', 'top', 'bottom', 'left', 'right'):
                    faces[name] = faces[name] + ['x']

            out = {
                'c': [round(pivot[i] + centre[i], 3) for i in range(3)],
                's': [round(v + 2 * grow, 3) for v in (w, h, d)],
                'u': [w, h, d],
                'f': faces,
            }
            if any(angles):
                out['r'] = angles
                out['p'] = pivot
            placed.setdefault(slot or slot_of(top, limb), {}).setdefault(limb, []).append(out)

    return {'tw': tw, 'th': th, 'slots': placed}


def read(class_path, binding=None, slot=None):
    parts, sheet = parse(disassemble(class_path))
    return convert(parts, sheet, binding, slot)
