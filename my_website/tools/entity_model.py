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
    # Elder Guardian is drawn with the plain Guardian's own model class -
    # the renderer just scales it up - so "tail0" (its numbered tail
    # segments) is enough on its own to land on it.
    'elder_guardian': {
        'tier':    0,
        'order':   3,
        'marker':  'tail0',
        'reject':  None,
        'texture': 'textures/entity/guardian_elder.png',
        'name':    'Elder Guardian',
        'id':      'minecraft:elder_guardian',
    },
    # "mouth" and "horn" are each shared with several other mobs' models (a
    # wolf, a llama, a goat...) and no single reject clears all of them, so
    # this one is pinned to its resolved class - fcs.class in this jar -
    # rather than searched for by marker.
    'ravager': {
        'tier':    0,
        'order':   4,
        'marker':  'mouth',
        'class':   'fcs.class',
        'reject':  None,
        'texture': 'textures/entity/illager/ravager.png',
        'name':    'Ravager',
        'id':      'minecraft:ravager',
    },
    # IllagerModel: the shared body every illager (vindicator, pillager,
    # illusioner, evoker) is built from, distinguished only by texture. Its
    # own marker string, "hat_rim", is shared with the plain villager's
    # model too - the villager's own copy has no "nose" or "arms" bone,
    # which IllagerModel does, but pinning the resolved class is simpler
    # than teaching find_classes a second marker to require.
    'evoker': {
        'tier':    0,
        'order':   5,
        'marker':  'hat_rim',
        'class':   'fdq.class',
        'reject':  None,
        'texture': 'textures/entity/illager/evoker.png',
        'name':    'Evoker',
        'id':      'minecraft:evoker',
        # the vindicator and pillager wear this, the evoker never does - its
        # own renderer just skips the part
        'drop':    ('hat',),
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
CLASSNAME = re.compile(r'^\w[\w .<>,?]*\bclass ([\w.$]+)', re.M)
# The owner is optional: a model that calls its own helper to pose a bone -
# setRotationAngle(box, x, y, z), the usual Blockbench export - is written by
# javap with no class in front of the name, and reading only qualified calls
# drops every rotation such a model sets.
#
# A mod's own class file keeps CubeDeformation's real, dotted name - Forge
# ships mod code built against Mojang's own mappings - but the vanilla client
# jar is obfuscated, and there the same class is a bare two-to-four-letter
# alias with no path in front of it at all ("fei", here). The two patterns
# can never collide - a mod's owner always carries a package path - so either
# one is safe to accept as the same class.
DEFORM = re.compile(r'CubeDeformation$|^[a-z]{2,4}$')
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


def read_float_arrays(text):
    """The static float[] fields a class's own <clinit> fills in, keyed by
    field name. Elder Guardian's 12 spikes are laid out by six of these -
    rotation and position multipliers indexed by spike number - baked in at
    class-load time rather than addBox'd by name, so the loop that poses
    them needs the arrays themselves, not just the numbers parse() sees."""
    arrays = {}
    cur, nums = None, []
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        op, rest = m.group(1), m.group(2)
        if op == 'newarray' and 'float' in rest:
            cur, nums = [], []
            continue
        if cur is None:
            continue
        if op in PUSH_INT:
            nums.append(PUSH_INT[op])
            continue
        if op in ('bipush', 'sipush'):
            nums.append(int(rest.split()[0]))
            continue
        if op.startswith('ldc'):
            num = LDC_NUM.search(rest)
            if num:
                nums.append(float(num.group(1)))
            continue
        if op == 'fastore':
            if len(nums) >= 2 and isinstance(nums[-2], int) and isinstance(nums[-1], float):
                idx, val = nums[-2], nums[-1]
                while len(cur) <= idx:
                    cur.append(0.0)
                cur[idx] = val
            nums = []
            continue
        if op == 'putstatic':
            f = FIELD.search(rest)
            if f and cur:
                arrays[f.group(1)] = cur
            cur, nums = None, []
            continue
    return arrays


# fbm.class's own <clinit>: the 2x9x2 spike every spike in the pose loop
# below reuses, from texOffs(0, 0).addBox(-1, -4.5, -1, 2, 9, 2) - the one
# addBox call in `b()` between the head bone and the loop, read once by hand
# since the loop's own name and pose never touch a literal parse() can see.
GUARDIAN_SPIKE_CUBE = [{
    'c': [0.0, 0.0, 0.0], 's': [2.0, 9.0, 2.0], 'f': box_uv(0, 0, 2.0, 9.0, 2.0),
}]


def parse_guardian_spikes(text, bones):
    """Elder Guardian is drawn with the plain Guardian's own model class.
    Its 12 spikes are hung off a shared cube builder in a for-loop, posed
    from six static float[12] arrays baked into the class's own <clinit> -
    each spike's name arrives as a string concat (not a literal) and its
    pose as a run of local-variable loads (not a constant push), so parse()
    walks straight past all twelve without adding anything. This rebuilds
    them from the arrays and the loop's own arithmetic instead."""
    arrays = read_float_arrays(text)
    need = ('a', 'b', 'f', 'g', 'h', 'i')
    if not all(k in arrays and len(arrays[k]) >= 12 for k in need):
        return bones
    rot_x, rot_y, rot_z = arrays['a'], arrays['b'], arrays['f']
    pos_x, pos_y, pos_z = arrays['g'], arrays['h'], arrays['i']
    spikes = []
    for idx in range(12):
        # a(i, 0, 0) = 1 + cos(i)*0.01 - a near-1 per-spike wobble on the
        # spike's own reach, baked in the same way the vanilla model is
        wobble = 1.0 + math.cos(idx) * 0.01
        x = pos_x[idx] * wobble
        y = 16.0 + pos_y[idx] * wobble
        z = pos_z[idx] * wobble
        spikes.append({
            'name': f'spike{idx}', 'parent': 'head',
            'pivot': [round(x, 3), round(y, 3), round(-z, 3)],
            'rot': [round(-rot_x[idx] * math.pi, 4),
                   round(-rot_y[idx] * math.pi, 4),
                   round(rot_z[idx] * math.pi, 4)],
            'cubes': GUARDIAN_SPIKE_CUBE,
        })
    return bones + spikes


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
    def add_box(self, nums, mirror=None):
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
        # a call's own mirror argument (addBox(..., true)) overrides the
        # builder's standing mirror() state - it is how a model flips just
        # one box of a set drawn off the same texOffs, a left/right pair
        # sharing one patch of sheet without the builder itself ever turning
        flip = self.mirror if mirror is None else mirror
        self.cubes.append({
            'c': [round(x + w / 2, 3), round(y + h / 2, 3), round(-(z + d / 2), 3)],
            's': [round(w, 3), round(h, 3), round(d, 3)],
            'f': mirrored(faces) if flip else faces,
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
        if op == 'invokevirtual' and floats >= 6:
            # a trailing Z is addBox(..., mirror): a per-call flip, the
            # boolean pushed last and sitting on top of the six floats. Left
            # in the stack it reads as a seventh number, and mesh.stack[-6:]
            # picks up that boolean in place of the box's own x and shifts
            # every other argument down a slot - a corrupt box, not a missing
            # one, which is what made it hard to spot.
            mirror_z = args.endswith('Z)')
            need = 7 if mirror_z else 6
            if len(mesh.stack) >= need:
                call_mirror = bool(mesh.stack.pop()) if mirror_z else None
                mesh.add_box(mesh.stack[-6:], mirror=call_mirror)
                mesh.stack.clear()
                if args.startswith('(Ljava/lang/String;') and mesh.strings:
                    mesh.strings.pop()
                continue

        if op == 'invokestatic' and floats in (3, 6) and args.count('L') == 0:
            nums = mesh.stack[-floats:] if len(mesh.stack) >= floats else [0] * floats
            if floats == 3:
                # PartPose ("feg" in this build) has two static three-float
                # methods sharing the one descriptor - offset(x, y, z) and
                # rotation(xRot, yRot, zRot) - and only the method's own name
                # tells them apart: offset is "a" everywhere, including its
                # six-float offsetAndRotation overload below, so any other
                # name on the same class is the rotation-only one. A hat
                # brim turned flat with no offset of its own is built this
                # way; read as offset() its turn lands in the pivot instead
                # and the bone never rotates at all.
                owner = (d.group(1) or '').rsplit('/', 1)[-1]
                if owner == 'feg' and d.group(2) != 'a':
                    mesh.pose = ([0, 0, 0], [-nums[0], -nums[1], nums[2]])
                else:
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
    # Citadel's own pose helpers - swing(), walk(), flap(), bob() - each take
    # six floats too, so a setupAnim() full of them can out-score the
    # constructor that actually builds the boxes. The constructor is never in
    # doubt, though: javap names it after the class, so blocks are narrowed to
    # that one first and only widened back to "whichever scores highest" if
    # nothing matches it.
    cls = CLASSNAME.search(text)
    simple = re.split(r'[.$]', cls.group(1))[-1] if cls else None
    ctor = re.compile(rf'\b{re.escape(simple)}\(') if simple else None
    pool = [b for b in blocks if ctor and ctor.search(b[0])] or blocks
    body = max(pool, key=score) if pool else []
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
        elif ('setRotationAngle' in method or 'setRotateAngle' in method) and args.count('F') == 3:
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


# The Ender Dragon's own createBodyLayer is not built the way every other
# mob's is: instead of CubeListBuilder.addBox(x, y, z, w, h, d) - a pair of
# ints then six floats, which is what parse() above looks for - it calls the
# older named-box overload, addBox(String, x, y, z, w, h, d, u, v): three
# floats then five ints, with a throwaway label per box ("upperlip", "scale",
# "nostril"...) that names nothing about the skeleton. parse()'s scorer never
# counts these calls, so the dragon's real 525-line body-layer method scores
# 0 and loses to a shorter, unrelated one. Rather than teach the shared
# scorer a second box shape - and risk every one of the sixty-odd mobs that
# already read correctly through it - this walks that one method on its own.
#
# The dragon's skeleton is also flat: every one of its 20 parts is added
# straight to the root PartDefinition (the bytecode reuses the same local
# variable - aload_1 - as the receiver each time), never to one another. So
# there is no parent chain to recover, only a pivot per part, which is either
# PartPose.ZERO (left at [0, 0, 0]) or PartPose.offset(x, y, z) - a static
# call taking the three floats pushed just before it.
DRAGON_NAME_BOX = re.compile(r'\(Ljava/lang/String;FFFIIIII\)')


def parse_dragon(text):
    """Read fot.class's `public static fek a()` - EnderDragonModel's own
    createBodyLayer - by hand, using the calling convention above."""
    methods, cur = [], []
    for line in text.splitlines():
        if re.match(r'^  \S.*\(.*\)', line) and not line.startswith('    '):
            if cur:
                methods.append(cur)
            cur = []
        cur.append(line)
    if cur:
        methods.append(cur)
    body = next((b for b in methods if 'public static fek a();' in b[0]), None)
    if body is None:
        return None

    parts, cur_part, stack, mirror = [], None, [], False
    # local variable slot -> the name of the part whose PartDefinition lives
    # there. Slot 1 holds the root (astore_1, from meshdefinition.getRoot());
    # every other slot is filled by astore-ing what a part's own fen.a(...)
    # call returns - a PartDefinition of its own, which is exactly what a
    # child reads back with aload before building itself. jaw is added to
    # aload_3 - head's own slot, not the root's - which is what makes it a
    # child of head rather than a sibling standing next to it.
    slot_owner = {1: None}
    held_slot = 1
    last_part = None      # the part just finalized, until its astore (if any)

    def flush():
        nonlocal last_part
        if cur_part and cur_part['cubes']:
            parts.append(cur_part)
        last_part = cur_part

    for raw in body:
        m = LINE.match(raw)
        if not m:
            continue
        op, rest = m.group(1), m.group(2)

        if op.startswith('aload'):
            slot = op.split('_')[-1] if '_' in op else rest.strip()
            if slot.isdigit():
                held_slot = int(slot)
            continue
        if op.startswith('astore'):
            slot = op.split('_')[-1] if '_' in op else rest.strip()
            if slot.isdigit() and last_part:
                slot_owner[int(slot)] = last_part['name']
            continue

        if op in PUSH_INT:
            stack.append(PUSH_INT[op])
            continue
        if op in ('bipush', 'sipush'):
            stack.append(int(rest.split()[0]))
            continue
        if op.startswith('ldc'):
            num = LDC_NUM.search(rest)
            if num:
                stack.append(float(num.group(1)))
                continue
            s = LDC_STR.search(rest)
            if s:
                stack.append(('STR', s.group(1).strip()))
            continue

        if op == 'invokestatic':
            d = DESC.search(rest)
            if not d:
                stack.clear()
                continue
            name, args = d.group(2), d.group(3)
            if name == 'c' and args == '()':
                # CubeListBuilder.create() - the string just under it on the
                # stack, pushed before this call, is the part it belongs to;
                # whichever slot was most recently aload'd is its parent
                flush()
                part_name = next((v[1] for v in reversed(stack)
                                  if isinstance(v, tuple) and v[0] == 'STR'), None)
                cur_part = {'name': part_name, 'parent': slot_owner.get(held_slot),
                           'cubes': [], 'pivot': [0.0, 0.0, 0.0]}
                mirror = False
            elif args == '(FFF)':
                # PartPose.offset(x, y, z) - already relative to the parent
                # this part was just built against, the same as every other
                # vanilla mob's own pivot; no world-space math to undo here
                floats = [v for v in stack if isinstance(v, float)]
                if len(floats) >= 3 and cur_part:
                    x, y, z = floats[-3:]
                    cur_part['pivot'] = [round(x, 3), round(y, 3), round(-z, 3)]
            stack.clear()
            continue

        if op == 'getstatic':      # PartPose.ZERO - pivot stays [0, 0, 0]
            stack.clear()
            continue

        if op == 'invokevirtual':
            d = DESC.search(rest)
            if not d:
                stack.clear()
                continue
            owner, args = d.group(1), d.group(3)
            if DRAGON_NAME_BOX.match(args):
                floats = [v for v in stack if isinstance(v, float)]
                ints = [v for v in stack if isinstance(v, int)]
                if cur_part and len(floats) >= 3 and len(ints) >= 5:
                    x, y, z = floats[-3:]
                    w, h, d_, u, v = ints[-5:]
                    faces = box_uv(u, v, w, h, d_)
                    cur_part['cubes'].append({
                        'c': [round(x + w / 2, 3), round(y + h / 2, 3),
                             round(-(z + d_ / 2), 3)],
                        's': [round(w, 3), round(h, 3), round(d_, 3)],
                        'f': mirrored(faces) if mirror else faces,
                    })
            elif args == '()' and (owner or '').endswith('fej'):
                mirror = not mirror       # the builder's own mirror toggle
            elif args == '(Ljava/lang/String;Lfej;Lfeg;)':
                flush()
                cur_part = None
            stack.clear()
            continue

    flush()
    return [{'name': p['name'], 'parent': p['parent'], 'pivot': p['pivot'],
             'rot': [0, 0, 0], 'cubes': p['cubes']} for p in parts]


def dragon_extend(bones):
    """The Ender Dragon has no jointed neck or tail in its own model - "neck"
    is one small 10-unit cube sitting at the origin, and "body" is the only
    tail geometry there is, one long box. The game draws both by re-rendering
    those same two pieces several times over along a curve computed at
    runtime from the dragon's actual recent flight path - there is no fixed
    shape in the class file for a card to read, only whatever the dragon
    happened to be doing the moment it was drawn. Read as-is, the result is a
    head sitting inside the body's own silhouette with nothing behind it.

    This lays real copies of the same two pieces out in a straight line
    instead: not what any particular flight looks like, but recognizably a
    dragon rather than a stub. The neck repeats itself forward from the
    body's own front edge until the head - unmoved, still its own shape -
    picks up where the last copy ends; the tail repeats the body's own
    largest box backward from its rear edge, a little smaller each time,
    since a straight run of the same size would just read as a longer body.
    """
    by_name = {b['name']: b for b in bones}
    neck, body, head = by_name['neck'], by_name['body'], by_name['head']

    # the spine's own height, and the body box's front and back edges, read
    # off its cubes rather than assumed, so this keeps working if the box
    # the game ships there ever changes
    spine_y = body['pivot'][1] + body['cubes'][0]['c'][1]
    front = body['pivot'][2] + max(c['c'][2] + c['s'][2] / 2 for c in body['cubes'])
    back = body['pivot'][2] + min(c['c'][2] - c['s'][2] / 2 for c in body['cubes'])
    step = (max(c['c'][2] + c['s'][2] / 2 for c in neck['cubes'])
            - min(c['c'][2] - c['s'][2] / 2 for c in neck['cubes']))
    neck_count = 3

    extra = []
    for i in range(1, neck_count):
        z = front + step * (i + 0.5)
        extra.append({'name': f'neck{i + 1}', 'parent': None,
                      'pivot': [neck['pivot'][0], spine_y, round(z, 3)],
                      'rot': [0, 0, 0], 'cubes': neck['cubes']})

    # body's own main box is already 64 deep; four more that size, even
    # tapered, would run the tail out to twice the dragon's own length. A
    # shorter, fixed-depth repeat narrowing toward a point reads as a tail
    # tapering off rather than the body just running on and on.
    main = max(body['cubes'], key=lambda c: c['s'][0] * c['s'][1] * c['s'][2])
    tail_count, tail_depth = 4, 14.0
    cursor = back
    for i in range(tail_count):
        frac = 1 - (i + 1) / (tail_count + 1)
        size = [round(main['s'][0] * frac, 3), round(main['s'][1] * frac, 3), tail_depth]
        cursor -= tail_depth
        extra.append({'name': f'tail{i + 1}', 'parent': None,
                      'pivot': [0, spine_y, round(cursor + tail_depth / 2, 3)],
                      'rot': [0, 0, 0],
                      'cubes': [{'c': [0, 0, 0], 's': size, 'f': main['f']}]})

    # Every leg's own pivot sits barely past the body box's side, so only
    # about half its own width is actually inside that box - the rest reads
    # as open air between leg and body from the card's fixed 3/4 angle, even
    # though a straight-on view would show them touching. Pulling each one a
    # few units further in fixes that regardless of viewing angle.
    NUDGE = 3.0
    LEGS = ('left_front_leg', 'right_front_leg', 'left_hind_leg', 'right_hind_leg')

    out = []
    for b in bones:
        if b['name'] == 'neck':
            b = {**b, 'pivot': [neck['pivot'][0], spine_y, round(front + step * 0.5, 3)]}
        elif b['name'] == 'head':
            b = {**b, 'pivot': [head['pivot'][0], spine_y,
                                round(front + step * neck_count, 3)]}
        elif b['name'] in LEGS:
            x = b['pivot'][0]
            x += NUDGE if x < 0 else -NUDGE
            b = {**b, 'pivot': [round(x, 3), b['pivot'][1], b['pivot'][2]]}
        out.append(b)
    out += extra
    return out


def build_dragon():
    text = disassemble(JAR, 'fot.class')
    bones = dragon_extend(parse_dragon(text))
    if not bones:
        raise SystemExit('ender_dragon: createBodyLayer did not parse')
    os.makedirs(OUT, exist_ok=True)
    with zipfile.ZipFile(JAR) as zf:
        png = zf.read('assets/minecraft/textures/entity/enderdragon/dragon.png')
    with open(os.path.join(OUT, 'ender_dragon.png'), 'wb') as fh:
        fh.write(png)
    model = {
        'id': 'minecraft:ender_dragon', 'name': 'Ender Dragon', 'class': 'fot.class',
        # a 248-unit wingspan next to a head barely a tenth that wide means the
        # auto-fit's whole-model framing is spent almost entirely on empty air
        # between the wingtips - the same trade spiritcaller and azazel make,
        # focus on the head and lean on zoom rather than show it all small.
        # "neck" is now the first of three segments dragon_extend lays down
        # ahead of the body, not the head end of that chain - head is.
        'focus': 'head', 'zoom': 3.0,
        'tw': 256, 'th': 256, 'texture': 'ender_dragon.png', 'bones': bones,
    }
    with open(os.path.join(OUT, 'ender_dragon.model.json'), 'w') as fh:
        json.dump(model, fh, separators=(',', ':'))
    cubes = sum(len(b['cubes']) for b in bones)
    print(f'ender_dragon fot.class {len(bones):>2} bones {cubes:>3} cubes  256x256')
    return model


def build(key, spec):
    # A single marker string is usually enough to land on one class, or on a
    # handful where the right one reads first. Ravager's "mouth"/"horn"
    # strings are each shared with several other mobs' models (a wolf, a
    # llama, a goat...), and no single reject clears all of them at once -
    # so its spec names the resolved class directly rather than searching.
    candidates = [spec['class']] if spec.get('class') else find_classes(
        JAR, spec['marker'], spec.get('reject'))
    if not candidates:
        raise SystemExit(f'{key}: no class holds "{spec["marker"]}"')

    entry, mesh, text = None, None, None
    for name in candidates:
        text = disassemble(JAR, name)
        read = parse(text)
        if read.bones and sum(len(b['cubes']) for b in read.bones):
            entry, mesh = name, read
            break
    if mesh is None:
        raise SystemExit(f'{key}: no mesh in {", ".join(candidates)}')
    bones = mesh.bones
    if key == 'elder_guardian':
        bones = parse_guardian_spikes(text, bones)
    if spec.get('drop'):
        # IllagerModel is shared by every illager - vindicator, pillager,
        # evoker, illusioner - and the hat is the one part not all of them
        # wear: the renderer itself skips it per mob rather than the model
        # leaving it out, which this bytecode reader has no way to see.
        # Emptying a bone's cubes is enough; nothing here builds a mesh for
        # one with none.
        gone = set(spec['drop'])
        for bone in bones:
            if bone['parent'] in gone:
                gone.add(bone['name'])
            if bone['name'] in gone:
                bone['cubes'] = []

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
