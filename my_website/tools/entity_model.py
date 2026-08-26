"""Recover a vanilla mob's model from the client jar.

Minecraft builds its entity models in Java rather than shipping them as data:
a chain of texOffs(u, v).addBox(x, y, z, w, h, d) calls per bone. The jar is
obfuscated, so the class and method names are meaningless, but the shape of
those calls is not: a pair of ints then six floats, hung off a builder. This
walks the bytecode and reads the numbers back out, which is the only way to
draw one of these mobs and have it be the mob rather than an impression of it.

    python tools/entity_model.py wither warden
"""

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile

JAR = os.path.expanduser(
    '~/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'static', 'minecraft', 'bosses')

# Each mob: a string only its model class holds, and the textures to lift out.
MOBS = {
    'wither': {
        'tier':    3,
        'order':   1,
        'marker':  'ribcage',
        'reject':  'right_tendril',            # the warden has a ribcage too
        'texture': 'textures/entity/wither/wither.png',
        'name':    'Wither',
        'id':      'minecraft:wither',
    },
    'warden': {
        'tier':    4,
        'order':   2,
        'marker':  'right_tendril',
        'reject':  None,
        'texture': 'textures/entity/warden/warden.png',
        'name':    'Warden',
        'id':      'minecraft:warden',
    },
}

PUSH_INT = {
    'iconst_m1': -1, 'iconst_0': 0, 'iconst_1': 1, 'iconst_2': 2,
    'iconst_3': 3, 'iconst_4': 4, 'iconst_5': 5,
    'fconst_0': 0.0, 'fconst_1': 1.0, 'fconst_2': 2.0,
    'dconst_0': 0.0, 'dconst_1': 1.0,
}

LINE = re.compile(r'^\s*\d+:\s+(\S+)\s*(.*)$')
LDC_NUM = re.compile(r'//\s*(?:float|int|double|long)\s+(-?[\d.]+(?:[eE]-?\d+)?)')
LDC_STR = re.compile(r'//\s*String\s+(.*)$')
SUPER = re.compile(r'^\w[\w .<>,?]*class [\w.$]+(?:<[^>]*>)? extends ([\w.$]+)', re.M)
# The owner is optional: a model that calls its own helper to pose a bone -
# setRotationAngle(box, x, y, z), the usual Blockbench export - is written by
# javap with no class in front of the name, and reading only qualified calls
# drops every rotation such a model sets.
DEFORM = re.compile(r'CubeDeformation$')
DESC = re.compile(r'//\s*\w+\s+(?:([\w$/]+)\.)?("?[\w$<>]+"?):(\([^)]*\))([\w$/;\[]+)')


def classes(jar):
    with zipfile.ZipFile(jar) as zf:
        return [n for n in zf.namelist() if n.endswith('.class')]


def find_classes(jar, marker, reject=None):
    """Every class whose constant pool holds this string and not the other.

    A part name shows up in more than one place: the model that builds the
    mob, and whatever else names its parts. Only one of them has a mesh in it,
    so the caller tries each and keeps the one that reads.
    """
    found = []
    with zipfile.ZipFile(jar) as zf:
        for name in zf.namelist():
            if not name.endswith('.class') or '/' in name:
                continue
            blob = zf.read(name)
            if marker.encode() not in blob:
                continue
            if reject and reject.encode() in blob:
                continue
            found.append(name)
    return found


def disassemble(jar, entry):
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(jar) as zf:
            zf.extract(entry, tmp)
        out = subprocess.run(
            ['javap', '-c', '-p', '-constants', os.path.join(tmp, entry)],
            capture_output=True, text=True, timeout=120)
    return out.stdout


def box_uv(u, v, w, h, d):
    """The unwrap the game uses for a whole box, in the portal's face names."""
    w, h, d = math.floor(w), math.floor(h), math.floor(d)
    return {
        'top':    [u + d,         v,     w, d],
        'bottom': [u + d + w,     v,     w, d],
        'right':  [u,             v + d, d, h],
        'front':  [u + d,         v + d, w, h],
        'left':   [u + d + w,     v + d, d, h],
        'back':   [u + d + w + d, v + d, w, h],
    }


def mirrored(faces):
    """A cube marked mirror is drawn as its own reflection: its two sides trade
    places and every face reads its texture backwards."""
    out = {}
    for name, rect in faces.items():
        swapped = {'left': 'right', 'right': 'left'}.get(name, name)
        flip = rect[4] if len(rect) > 4 else ''
        flip = flip.replace('x', '') if 'x' in flip else flip + 'x'
        out[swapped] = list(rect[:4]) + ([flip] if flip else [])
    return out


class Mesh:
    """One pass over the bytecode of a createBodyLayer-shaped method."""

    def __init__(self):
        self.stack = []          # numbers pushed since the last call
        self.strings = []
        self.cubes = []          # cubes of the builder under construction
        self.texoff = (0, 0)
        self.mirror = False      # the builder's own mirror flag
        self.grow = None         # a CubeDeformation waiting for its box
        self.pose = None
        self.locals = {}         # local slot -> bone name
        self.parent = None       # bone the call under construction hangs off
        self.held = None         # bone named by the last aload
        self.pending = None      # bone just committed, awaiting an astore
        self.pending_at = -9     # and the instruction it was committed at
        self.bones = []
        self.size = None

    # the portal draws with y down like the game, but with the front of a box
    # toward the viewer, which is the way the game's z runs backwards
    def add_box(self, nums):
        x, y, z, w, h, d = nums[:6]
        u, v = self.texoff
        # the sheet is unwrapped for the box as it was measured; a deformation
        # only swells or shrinks the solid afterwards, and the same patch of
        # texture is stretched over whatever comes out
        faces = box_uv(u, v, w, h, d)
        gx, gy, gz = self.grow or (0.0, 0.0, 0.0)
        self.grow = None
        x, y, z = x - gx, y - gy, z - gz
        w, h, d = w + gx * 2, h + gy * 2, d + gz * 2
        self.cubes.append({
            'c': [round(x + w / 2, 3), round(y + h / 2, 3), round(-(z + d / 2), 3)],
            's': [round(w, 3), round(h, 3), round(d, 3)],
            'f': mirrored(faces) if self.mirror else faces,
        })

    def commit(self, name, at):
        self.bones.append({
            'name':   name,
            'parent': self.parent,
            'pivot':  self.pose[0] if self.pose else [0, 0, 0],
            'rot':    self.pose[1] if self.pose else [0, 0, 0],
            'cubes':  self.cubes,
        })
        # the cubes are deliberately left in place: a model may hand the same
        # builder to two bones, as the wither does with its two side heads, and
        # only the next create() means a new set
        self.pose = None
        self.pending = name
        self.pending_at = at


def parse(text, method_hint='fek'):
    """Read the mesh out of the one static method that builds it."""
    lines = text.splitlines()
    # A class holds more than one method and only one of them builds the mesh.
    # Length is a poor guide once animation code is in the file, so score each
    # method by how much of it looks like boxes being added.
    methods, cur = [], []
    for line in lines:
        if re.match(r'^  \S.*\(.*\)', line) and not line.startswith('    '):
            if cur:
                methods.append(cur)
            cur = []
        cur.append(line)
    if cur:
        methods.append(cur)

    def score(block):
        marks = 0
        for line in block:
            d = DESC.search(line)
            if not d:
                continue
            if d.group(3) == '(II)':
                marks += 1
            elif d.group(3).count('F') >= 6:
                marks += 2
        return marks

    best = max(methods, key=score) if methods else None
    if best is not None and score(best) == 0:
        best = None

    mesh = Mesh()
    body = best or lines
    step = 0
    for line in body:
        m = LINE.match(line)
        if not m:
            continue
        step += 1
        op, rest = m.group(1), m.group(2)

        if op in PUSH_INT:
            mesh.stack.append(PUSH_INT[op])
            continue
        if op in ('bipush', 'sipush'):
            mesh.stack.append(int(rest.split()[0]))
            continue
        if op.startswith('ldc'):
            num = LDC_NUM.search(rest)
            if num:
                mesh.stack.append(float(num.group(1)))
                continue
            text_ = LDC_STR.search(rest)
            if text_:
                mesh.strings.append(text_.group(1).strip())
                # whatever was loaded just before the name is what this part
                # will hang off, before the argument loads overwrite it
                mesh.parent = mesh.held
            continue
        if op.startswith('aload'):
            slot = op.split('_')[-1] if '_' in op else rest.strip()
            mesh.held = mesh.locals.get(int(slot)) if slot.isdigit() else None
            continue
        if op.startswith('astore'):
            slot = op.split('_')[-1] if '_' in op else rest.strip()
            # only the store right after the call is keeping that bone: a store
            # any later is holding a cube builder, not a part
            if mesh.pending and slot.isdigit() and step == mesh.pending_at + 1:
                mesh.locals[int(slot)] = mesh.pending
            mesh.pending = None
            continue

        # A constructor called mid-chain - addBox(..., new CubeDeformation(0))
        # is the common one - leaves its own arguments on the stack, and those
        # would be read as the tail of the box that follows.
        if op == 'invokespecial':
            d = DESC.search(rest)
            if d:
                eaten = sum(d.group(3).count(kind) for kind in 'FIDJZBS')
                # CubeDeformation is the one constructor whose arguments the
                # box that follows genuinely needs: one number swells the
                # solid on every side, three swell it per axis. It is how a
                # model puts a shell a shade wider over the part beneath -
                # a snow golem's head under its pumpkin, a hat over a head -
                # and dropping it leaves two boxes the same size fighting for
                # the same surface.
                if DEFORM.search(d.group(1) or '') and eaten in (1, 3):
                    took = mesh.stack[-eaten:] if len(mesh.stack) >= eaten else []
                    if len(took) == eaten:
                        mesh.grow = ((took * 3) if eaten == 1 else took)[:3]
                if eaten:
                    del mesh.stack[-eaten:]
            continue

        if op not in ('invokevirtual', 'invokestatic', 'getstatic'):
            continue

        d = DESC.search(rest)
        if not d:
            # A field read is not a call and consumes nothing. CubeDeformation
            # .NONE is read this way between a box's measurements and the call
            # that uses them, so clearing here loses the whole box.
            if op != 'getstatic':
                mesh.stack.clear()
            continue
        args, ret = d.group(3), d.group(4)

        if op == 'getstatic':
            # CubeDeformation.NONE reads the same shape as PartPose.ZERO - a
            # constant of its own type - and means the opposite thing
            if DEFORM.search(d.group(1) or ''):
                mesh.grow = None
            elif ret.strip('L;') == d.group(1):
                # PartPose.ZERO, the only static of its own type worth knowing
                mesh.pose = None
            continue

        if args == '()' and op == 'invokestatic':
            mesh.cubes = []                      # a fresh CubeListBuilder
            mesh.texoff = (0, 0)
            mesh.mirror = False
            mesh.grow = None
            mesh.stack.clear()
            continue

        if args == '(II)':
            if len(mesh.stack) >= 2:
                mesh.texoff = (int(mesh.stack[-2]), int(mesh.stack[-1]))
            mesh.stack.clear()
            continue

        # mirror() and mirror(flag) are the builder handing itself back with
        # nothing measured: a part built from its own reflection, which is how
        # a model draws a left wing from the right one's corner of the sheet.
        if (op == 'invokevirtual' and args in ('()', '(Z)')
                and ret.strip('L;') == d.group(1)):
            mesh.mirror = bool(mesh.stack[-1]) if args == '(Z)' and mesh.stack else True
            mesh.stack.clear()
            continue

        floats = args.count('F')
        # a cube may be named too: addBox("scale", x, y, z, w, h, d) is a box,
        # not a new part, and telling them apart is what the floats are for
        if op == 'invokevirtual' and floats >= 6 and len(mesh.stack) >= 6:
            mesh.add_box(mesh.stack[-6:])
            mesh.stack.clear()
            if args.startswith('(Ljava/lang/String;') and mesh.strings:
                mesh.strings.pop()
            continue

        if op == 'invokestatic' and floats in (3, 6) and args.count('L') == 0:
            nums = mesh.stack[-floats:] if len(mesh.stack) >= floats else [0] * floats
            if floats == 3:
                mesh.pose = ([nums[0], nums[1], -nums[2]], [0, 0, 0])
            else:
                # the portal reads z backwards, and reflecting an axis reverses
                # every rotation but the one about that axis
                mesh.pose = ([nums[0], nums[1], -nums[2]],
                             [-nums[3], -nums[4], nums[5]])
            mesh.stack.clear()
            continue

        if args.startswith('(Ljava/lang/String;') and floats == 0 and mesh.strings:
            mesh.commit(mesh.strings[-1], step)
            mesh.strings.pop()
            mesh.stack.clear()
            continue

        # LayerDefinition.create(mesh, width, height)
        if args.count('I') == 2 and len(mesh.stack) >= 2:
            mesh.size = (int(mesh.stack[-2]), int(mesh.stack[-1]))
            mesh.stack.clear()
            continue

        # A modifier chained onto one of a box's own arguments -
        # CubeDeformation.extend(n), almost always, for a hat or a robe a size
        # wider than the body it sits over - hands itself back the same way a
        # builder does, mid-call, before the box measurements it belongs to
        # have been read. Falling through to the clear below would wipe those
        # six numbers out from under the addBox still waiting for them one
        # call up, and the box that call was building never gets added at
        # all. Eat only what this call itself put on the stack instead, the
        # same as invokespecial's own extra constructor args above.
        if op == 'invokevirtual' and ret.strip('L;') == d.group(1):
            eaten = sum(args.count(kind) for kind in 'FIDJZBS')
            # extend() hands back a deformation grown by that much again
            if DEFORM.search(d.group(1) or '') and eaten == 1 and mesh.stack:
                by = mesh.stack[-1]
                held = mesh.grow or (0.0, 0.0, 0.0)
                mesh.grow = [held[0] + by, held[1] + by, held[2] + by]
            if eaten:
                del mesh.stack[-eaten:]
            continue

        mesh.stack.clear()

    return mesh


FIELD = re.compile(r'//\s*Field\s+([\w$]+):(\S+)')
# Matched anywhere in the type name, not exactly: mods wrap and subclass these
# freely. Alex's Caves hangs the Tremorzilla's whole body off a
# HideableModelBoxWithChildren, and not counting that as a bone leaves
# everything below it with no parent to sit on.
BOX_TYPES = ('ModelBox', 'ModelRenderer', 'ModelPart')


class Advanced:
    """Reader for the model API Citadel lends to Cataclysm and Alex's mods.

    Where vanilla hangs a builder off a local, this holds every bone in a field
    of the model and wires them together afterwards, so the bones are named by
    their putfield and the tree is read off the addChild calls.
    """

    def __init__(self):
        self.stack = []
        self.refs = []
        self.order = []
        self.parts = {}
        self.texoff = (0, 0)
        self.size = None
        self.ints = []

    def part(self, name):
        if name not in self.parts:
            self.parts[name] = {'name': name, 'parent': None,
                                'pivot': [0, 0, 0], 'rot': [0, 0, 0], 'cubes': []}
            self.order.append(name)
        return self.parts[name]

    def add_box(self, name, nums):
        x, y, z, w, h, d = nums[:6]
        grow = nums[6] if len(nums) > 6 else 0.0
        u, v = self.texoff
        self.part(name)['cubes'].append({
            'c': [round(x + w / 2, 3), round(y + h / 2, 3), round(-(z + d / 2), 3)],
            's': [round(w + 2 * grow, 3), round(h + 2 * grow, 3), round(d + 2 * grow, 3)],
            'f': box_uv(u, v, w, h, d),
        })


def methods_of(text):
    """javap output split into one block per method."""
    blocks, cur = [], []
    for line in text.splitlines():
        if re.match(r'^  \S.*\(.*\)', line) and not line.startswith('    '):
            if cur:
                blocks.append(cur)
            cur = []
        cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def parse_advanced(text):
    """Read the constructor, where a model of this kind is assembled.

    Only the constructor: the animation methods further down the class are
    full of setRotationAngle calls that pose the mob frame by frame, and
    reading those as part of the build leaves every bone somewhere it only
    passes through mid-swing.
    """
    def score(block):
        marks = 0
        for line in block:
            d = DESC.search(line)
            # a box is six floats hung off something, whatever it is called
            if d and d.group(3).count('F') >= 6:
                marks += 1
        return marks

    blocks = methods_of(text)
    body = max(blocks, key=score) if blocks else []
    if not body or not score(body):
        return [], None

    read = Advanced()
    # the texture size is set in the constructor too, but read the whole class
    # for it in case a parent class holds it
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        if m.group(1) in ('bipush', 'sipush') or m.group(1) in PUSH_INT:
            continue

    for line in body:
        m = LINE.match(line)
        if not m:
            continue
        op, rest = m.group(1), m.group(2)

        if op in PUSH_INT:
            read.stack.append(PUSH_INT[op])
            continue
        if op in ('bipush', 'sipush'):
            read.stack.append(int(rest.split()[0]))
            continue
        if op.startswith('ldc'):
            num = LDC_NUM.search(rest)
            if num:
                read.stack.append(float(num.group(1)))
            continue

        if op in ('getfield', 'putfield'):
            f = FIELD.search(rest)
            if not f:
                continue
            name, kind = f.group(1), f.group(2).rstrip(';').rsplit('/', 1)[-1]
            if any(box in kind for box in BOX_TYPES):
                read.part(name)
                read.refs.append(name)
            elif name in ('texWidth', 'texHeight') and read.stack:
                width, height = read.size or (64, 64)
                read.size = ((int(read.stack[-1]), height) if name == 'texWidth'
                             else (width, int(read.stack[-1])))
                read.stack.clear()
            continue

        if op != 'invokevirtual':
            continue
        d = DESC.search(rest)
        if not d:
            read.stack.clear()
            continue
        method, args = d.group(2), d.group(3)

        if 'setRotationPoint' in method or method in ('setPos', 'm_104227_'):
            if read.refs and len(read.stack) >= 3:
                x, y, z = read.stack[-3:]
                read.part(read.refs[-1])['pivot'] = [round(x, 3), round(y, 3), round(-z, 3)]
        elif 'setRotationAngle' in method and args.count('F') == 3:
            if read.refs and len(read.stack) >= 3:
                rx, ry, rz = read.stack[-3:]
                read.part(read.refs[-1])['rot'] = [round(-rx, 4), round(-ry, 4), round(rz, 4)]
        elif 'addChild' in method or method == 'm_171599_':
            # nothing is its own parent; a pair that says so means the receiver
            # was of a type not recognised as a bone
            if len(read.refs) >= 2 and read.refs[-1] != read.refs[-2]:
                read.part(read.refs[-1])['parent'] = read.refs[-2]
        elif 'setTextureOffset' in method or args == '(II)':
            if len(read.stack) >= 2:
                read.texoff = (int(read.stack[-2]), int(read.stack[-1]))
        elif 'addBox' in method and args.count('F') >= 6:
            if read.refs and len(read.stack) >= 6:
                floats = [v for v in read.stack if isinstance(v, float)]
                read.add_box(read.refs[-1], (floats or read.stack)[-args.count('F'):])
        read.stack.clear()

    bones = [read.parts[name] for name in read.order]
    # None rather than a default: a subclass that sets no sheet size must not
    # out-vote the parent it inherits its body from
    return bones, read.size


def build(key, spec):
    candidates = find_classes(JAR, spec['marker'], spec.get('reject'))
    if not candidates:
        raise SystemExit(f'{key}: no class holds "{spec["marker"]}"')

    entry, mesh = None, None
    for name in candidates:
        read = parse(disassemble(JAR, name))
        if read.bones and sum(len(b['cubes']) for b in read.bones):
            entry, mesh = name, read
            break
    if mesh is None:
        raise SystemExit(f'{key}: no mesh in {", ".join(candidates)}')
    bones = mesh.bones

    tw, th = mesh.size or (64, 64)
    os.makedirs(OUT, exist_ok=True)

    with zipfile.ZipFile(JAR) as zf:
        png = zf.read('assets/minecraft/' + spec['texture'])
    with open(os.path.join(OUT, f'{key}.png'), 'wb') as fh:
        fh.write(png)

    model = {
        'id': spec['id'], 'name': spec['name'], 'class': entry,
        'tw': tw, 'th': th, 'texture': f'{key}.png', 'bones': bones,
    }
    with open(os.path.join(OUT, f'{key}.model.json'), 'w') as fh:
        json.dump(model, fh, separators=(',', ':'))

    cubes = sum(len(b['cubes']) for b in bones)
    print(f'{key:<8} {entry:<12} {len(bones):>2} bones {cubes:>3} cubes  {tw}x{th}')
    for b in bones:
        print(f'   {b["name"]:<16} parent={str(b["parent"]):<14} '
              f'pivot={b["pivot"]} cubes={len(b["cubes"])}')
    return model


def write_index():
    """The roster of bosses we can draw, whether or not anyone has felled one."""
    index = []
    for key, spec in MOBS.items():
        if not os.path.isfile(os.path.join(OUT, f'{key}.model.json')):
            continue
        index.append({
            'key': key, 'id': spec['id'], 'name': spec['name'],
            'tier': spec['tier'], 'order': spec['order'],
            'model': f'{key}.model.json',
        })
    index.sort(key=lambda b: b['order'])
    with open(os.path.join(OUT, 'index.json'), 'w') as fh:
        json.dump(index, fh, indent=1)
    print(f'index    {len(index)} bosses')


if __name__ == '__main__':
    for key in (sys.argv[1:] or list(MOBS)):
        build(key, MOBS[key])
    write_index()
