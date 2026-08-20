"""Work out what each worn piece of armor is worth.

A player's save records their attributes but not their armor: armor points and
toughness come from what they have on, and the game works them out afresh every
time it loads them, so the numbers are nowhere in the file. The pieces are,
though, and every mod has to tell the game what its material protects for. That
is what this reads back out.

Mods write a material in one of two shapes: an anonymous class handed straight
to the ArmorItem constructor, or a shared enum whose constants are built in a
static block. Both keep the four protection values and the toughness as plain
constants, so both can be read the same way javamodel reads a model.
"""

import re
import subprocess
import tempfile
import zipfile

# EquipmentSlot.getIndex(), which is the order a material's int[] is written in
ORDER = ('feet', 'legs', 'chest', 'head')
TYPES = {'BOOTS': 'feet', 'LEGGINGS': 'legs', 'CHESTPLATE': 'chest', 'HELMET': 'head'}

# vanilla's own materials, which no jar has to be read for
VANILLA = {
    'leather':   ((1, 2, 3, 1), 0.0),
    'chainmail': ((1, 4, 5, 2), 0.0),
    'iron':      ((2, 5, 6, 2), 0.0),
    'golden':    ((1, 3, 5, 2), 0.0),
    'gold':      ((1, 3, 5, 2), 0.0),
    'diamond':   ((3, 6, 8, 3), 2.0),
    'netherite': ((3, 6, 8, 3), 3.0),
    'turtle':    ((0, 0, 0, 2), 0.0),
}

# the names Mojang's obfuscation gives ArmorMaterial's methods in 1.20.1
DEFENSE   = ('m_7366_', 'getDefenseForType')
TOUGHNESS = ('m_6651_', 'getToughness')

MATERIAL_ARG = re.compile(r'invoke\w+\s+#\d+\s+// Method ([\w/$]+)\."?<init>"?:'
                          r'\(Lnet/minecraft/world/item/ArmorMaterial;')
NEW      = re.compile(r'^\s*\d+:\s+new\s+#\d+\s+// class ([\w/$]+)$')
STATIC   = re.compile(r'^\s*\d+:\s+getstatic\s+#\d+\s+// Field ([\w/$]+)\.([\w$]+):')
PUT      = re.compile(r'^\s*\d+:\s+putstatic\s+#\d+\s+// Field ([\w$]+):')
METHOD   = re.compile(r'^  [\w$<>. ]*[\s.]([\w$<>]+)\(')
INT      = re.compile(r'^\s*\d+:\s+(?:iconst_(\d)|bipush\s+(\d+)|sipush\s+(\d+))$')
FLOAT    = re.compile(r'^\s*\d+:\s+(?:fconst_(\d)|ldc\w*\s+#\d+\s+// float ([\d.]+)f)$')
TYPE_REF = re.compile(r'getstatic\s+#\d+\s+// Field net/minecraft/world/item/ArmorItem\$Type\.(\w+):')
LAMBDA   = re.compile(r'^\s+\S.*\s(lambda\$[\w$]+)\(')
DYNAMIC  = re.compile(r'invokedynamic\s+#\d+,\s+\d+\s+// InvokeDynamic #(\d+):')
BOOT     = re.compile(r'^\s{2}(\d+): #\d+ REF_')
TARGET   = re.compile(r'^\s+#\d+ REF_invokeStatic [\w/$]+\.(lambda\$[\w$]+):')


def disassemble(jar, entry, verbose=False):
    with tempfile.TemporaryDirectory() as work:
        with zipfile.ZipFile(jar) as zf:
            path = zf.extract(entry, work)
        return subprocess.run(['javap', '-v' if verbose else '-c', '-p', path],
                              capture_output=True, text=True, check=True).stdout


def number(line):
    m = INT.match(line)
    if m:
        return int(next(g for g in m.groups() if g is not None))
    return None


def methods(listing):
    """{method name: its lines}, for whichever of them carry constants."""
    out, name = {}, None
    for line in listing.splitlines():
        m = METHOD.match(line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
        elif name:
            out[name].append(line)
    return out


def by_type(lines):
    """Protection values keyed by slot, from puts of ArmorItem.Type constants."""
    found, pending = {}, None
    for line in lines:
        m = TYPE_REF.search(line)
        if m:
            pending = TYPES.get(m.group(1))
            continue
        value = number(line)
        if value is not None and pending:
            found[pending] = value
            pending = None
    return found


def by_index(lines):
    """Protection values from a plain int[4], in EquipmentSlot order."""
    values, taking = [], False
    for line in lines:
        if 'newarray' in line and 'int' in line:
            values, taking = [], True
            continue
        if not taking:
            continue
        value = number(line)
        if value is not None:
            values.append(value)
        if len(values) >= 8:
            break
    # the array is written as index, value, index, value...
    pairs = {}
    for i in range(0, len(values) - 1, 2):
        if values[i] < 4:
            pairs[ORDER[values[i]]] = values[i + 1]
    return pairs if len(pairs) == 4 else {}


def floats(lines):
    out = []
    for line in lines:
        m = FLOAT.match(line)
        if m:
            out.append(float(m.group(1) or m.group(2)))
    return out


def material_of(jar, entry):
    """Where the item's material comes from: its own class, or a shared one."""
    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
    holder = None
    for line in disassemble(jar, entry).splitlines():
        m = NEW.match(line)
        if m and m.group(1) + '.class' in have:
            holder = ('inner', m.group(1) + '.class', None)
            continue
        m = STATIC.match(line)
        if m and m.group(1) + '.class' in have:
            holder = ('field', m.group(1) + '.class', m.group(2))
            continue
        if MATERIAL_ARG.search(line) and holder:
            return holder
    return None


def from_inner(jar, entry):
    """A material written as one anonymous class: read its two methods."""
    parts = methods(disassemble(jar, entry))
    protection = {}
    for name in DEFENSE:
        if name in parts:
            protection = by_index(parts[name]) or by_type(parts[name])
            break
    tough = 0.0
    for name in TOUGHNESS:
        if name in parts:
            values = floats(parts[name])
            tough = values[0] if values else 0.0
            break
    return (protection, tough) if protection else None


def lambdas(listing):
    """({lambda name: its lines}, {bootstrap index: lambda name})."""
    bodies, boots, name, index = {}, {}, None, None
    for line in listing.splitlines():
        m = LAMBDA.match(line)
        if m:
            name = m.group(1)
            bodies.setdefault(name, [])
            continue
        if name is not None and line.startswith('    '):
            bodies[name].append(line)
        m = BOOT.match(line)
        if m:
            index = int(m.group(1))
            continue
        m = TARGET.match(line)
        if m and index is not None:
            boots[index] = m.group(1)
            index = None
    return bodies, boots


def clinit(listing):
    lines, taking = [], False
    for line in listing.splitlines():
        if re.match(r'^\s{2}static \{\};', line):
            taking = True
            continue
        if taking:
            if re.match(r'^\s{2}\S', line):
                break
            lines.append(line)
    return lines


def from_field(jar, entry, field):
    """A material built in a static block: read the arguments it was given."""
    listing = disassemble(jar, entry, verbose=True)
    bodies, boots = lambdas(listing)

    window = []
    for line in clinit(listing):
        m = PUT.match(line)
        if m:
            if m.group(1) == field:
                break
            window = []
            continue
        m = DYNAMIC.search(line)
        if m:                                # the per-slot map is filled in a lambda
            window.extend(bodies.get(boots.get(int(m.group(1))), []))
            continue
        window.append(line)
    else:
        return None

    protection = by_type(window)
    if len(protection) != 4 and any('newarray' in line for line in window):
        protection = by_index(window)
    if len(protection) != 4:
        return None
    values = floats(window)
    return protection, (values[0] if values else 0.0)


def material(jar, entry):
    found = material_of(jar, entry)
    if not found:
        return None
    kind, holder, field = found
    return from_inner(jar, holder) if kind == 'inner' else from_field(jar, holder, field)


EXTENDS = re.compile(r'^\w[\w$. ]* class [\w$.]+ extends ([\w$.]+)')
LDC_NAME = re.compile(r'^\s*\d+:\s+ldc\w*\s+#\d+\s+// String ([a-z0-9_]+)$')


def parent(listing):
    for line in listing.splitlines():
        m = EXTENDS.match(line)
        if m:
            return m.group(1).replace('.', '/') + '.class'
    return None


SLOT_WORDS = ('helmet', 'chestplate', 'chest', 'leggings', 'legs', 'boots',
              'feet', 'head', 'cap', 'hat', 'mask', 'crown', 'shoes')


def named(item_id):
    """The names the item may be registered under: its own, and the set's."""
    path = item_id.partition(':')[2] or item_id
    names = [path]
    for word in SLOT_WORDS:
        if path.endswith('_' + word):
            names.append(path[:-len(word) - 1])
    return names


def registration(jar, item_id):
    """Where the item is registered: the class built for it, and the constant
    holding its material where the material is handed in rather than built.

    Mods write this three ways: a lambda that news up the item, a call taking
    the material alongside the name, or an item class that carries its own.
    All three put the name first, so the answer is whatever follows it.
    """
    names = named(item_id)
    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
        entries = [e for e in have if e.endswith('.class')
                   and any(n.encode() in zf.read(e) for n in names)]

    for entry in entries:
        listing = disassemble(jar, entry, verbose=True)
        bodies, boots = lambdas(listing)
        lines = listing.splitlines()
        for i, line in enumerate(lines):
            m = LDC_NAME.match(line)
            if not m or m.group(1) not in names:
                continue
            window = []
            for after in lines[i + 1:i + 24]:
                got = DYNAMIC.search(after)
                if got:
                    window.extend(bodies.get(boots.get(int(got.group(1))), []))
                else:
                    window.append(after)
            made, field = None, None
            for inner in window:
                got = NEW.match(inner)
                if got and not made and got.group(1) + '.class' in have:
                    made = got.group(1) + '.class'
                got = STATIC.match(inner)
                if got and not field and got.group(1) + '.class' in have:
                    field = (got.group(1) + '.class', got.group(2))
            if made or field:
                return made, field
    return None, None


def stats(jar, item_id):
    """(protection by slot, toughness) for one item, or None."""
    made, field = registration(jar, item_id)
    if field:
        found = from_field(jar, *field)
        if found:
            return found
    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
    entry = made
    while entry in have:                     # the material may be set a class up
        found = material(jar, entry)
        if found:
            return found
        entry = parent(disassemble(jar, entry))
    return None
