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
GETFIELD = re.compile(r'^\s*\d+:\s+getfield\s+#\d+\s+// Field ([\w/$]+)\.([\w$]+):([IF])')
PUTFIELD = re.compile(r'^\s*\d+:\s+putfield\s+#\d+\s+// Field ([\w$]+):([IF])')
TYPE_REF = re.compile(r'getstatic\s+#\d+\s+// Field net/minecraft/world/item/ArmorItem\$Type\.(\w+):')
LAMBDA   = re.compile(r'^\s+\S.*\s(lambda\$[\w$]+)\(')
DYNAMIC  = re.compile(r'invokedynamic\s+#\d+,\s+\d+\s+// InvokeDynamic #(\d+):')
BOOT     = re.compile(r'^\s{2}(\d+): #\d+ REF_')
TARGET   = re.compile(r'^\s+#\d+ REF_invokeStatic [\w/$]+\.(lambda\$[\w$]+):')


_listings = {}


def disassemble(jar, entry, verbose=False):
    """javap is slow and the same class comes up repeatedly, so keep it."""
    key = (jar, entry, verbose)
    if key not in _listings:
        with tempfile.TemporaryDirectory() as work:
            with zipfile.ZipFile(jar) as zf:
                path = zf.extract(entry, work)
            _listings[key] = subprocess.run(
                ['javap', '-v' if verbose else '-c', '-p', path],
                capture_output=True, text=True, check=True).stdout
    return _listings[key]


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


SLOT_IN_NAME = (('helmet', 'head'), ('head', 'head'), ('chest', 'chest'),
                ('body', 'chest'), ('legs', 'legs'), ('legging', 'legs'),
                ('feet', 'feet'), ('boot', 'feet'))


def defaults(jar, entry):
    """{field: value} for the numbers a class sets up in its constructor.

    Only a field set straight from a constant counts: the same class usually
    carries setters that write the field from an argument, and those would
    otherwise read as whatever number happened to come last.
    """
    found, last = {}, None
    for line in disassemble(jar, entry).splitlines():
        value = number(line)
        if value is not None:
            last = float(value)
            continue
        m = FLOAT.match(line)
        if m:
            last = float(m.group(1) or m.group(2))
            continue
        m = PUTFIELD.match(line)
        if m:
            if last is not None:
                found[m.group(1)] = last
            last = None
            continue
        last = None
    return found


def by_config(jar, lines, have):
    """Protection and toughness read out of another class's settings.

    A mod that lets its armor be tuned holds the numbers in a config object
    and reads them by field, so the field's name is what says which slot it
    is for and the class it belongs to is what says what it was set to.
    """
    protection, tough, seen = {}, 0.0, {}
    for line in lines:
        m = GETFIELD.match(line)
        if not m:
            continue
        owner, field, kind = m.group(1) + '.class', m.group(2), m.group(3)
        if owner not in have:
            continue
        if owner not in seen:
            seen[owner] = defaults(jar, owner)
        if field not in seen[owner]:
            continue
        plain = field.lower()
        if kind == 'F' and 'toughness' in plain:
            tough = seen[owner][field]
        elif kind == 'I' and 'def' in plain:
            for word, slot in SLOT_IN_NAME:
                if word in plain:
                    protection[slot] = int(seen[owner][field])
                    break
    return protection, tough


ARRAY_PUT = re.compile(r'^\s*\d+:\s+putstatic\s+#\d+\s+// Field ([\w$]+):\[I')
ARRAY_GET = re.compile(r'getstatic\s+#\d+\s+// Field ([\w$]+):\[I')


def arrays(listing):
    """{field: protection by slot} for int arrays set up in a static block."""
    found, window = {}, []
    for line in clinit(listing):
        m = ARRAY_PUT.match(line)
        if m:
            values = by_index(window)
            if values:
                found[m.group(1)] = values
            window = []
            continue
        window.append(line)
    return found


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
    """A material written as its own class: read its two methods."""
    listing = disassemble(jar, entry)
    parts = methods(listing)
    protection = {}
    for name in DEFENSE:
        if name not in parts:
            continue
        protection = by_index(parts[name]) or by_type(parts[name])
        if not protection:
            # the method may only index an array the class set up earlier
            held = next((ARRAY_GET.search(line) for line in parts[name]
                         if ARRAY_GET.search(line)), None)
            if held:
                protection = arrays(listing).get(held.group(1), {})
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
    if len(protection) == 4:
        values = floats(window)
        return protection, (values[0] if values else 0.0)

    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
    protection, tough = by_config(jar, window, have)
    return (protection, tough) if len(protection) == 4 else None


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

    # the class that registers the item is worth looking at before the rest
    entries.sort(key=lambda e: (0 if re.search(r'(item|regist|init)', e, re.I)
                                else 1, len(e)))
    hits = []
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
            if not (made or field):
                continue
            # a name can be registered more than once in a mod, so prefer the
            # one that is plainly an armor piece and the one registered under
            # the item's own name rather than the name of its set
            armor = any('ArmorItem' in inner or 'ArmorMaterial' in inner
                        for inner in window)
            rank = (0 if armor else 1, names.index(m.group(1)))
            if rank == (0, 0):
                return made, field
            hits.append((*rank, made, field))

    hits.sort(key=lambda hit: hit[:2])
    return (hits[0][2], hits[0][3]) if hits else (None, None)


def stats(jar, item_id):
    """(protection by slot, toughness) for one item, or None."""
    made, field = registration(jar, item_id)
    if field:
        # the constant may name a whole material class rather than one built
        # in place, in which case the values are in its methods as usual
        found = from_field(jar, *field) or from_inner(jar, field[0])
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
