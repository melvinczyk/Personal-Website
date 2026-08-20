"""Read an armor set out of a mod built with MCreator.

MCreator writes one item class per piece, named for the registry id, and hangs
an anonymous inner class off it that hands the renderer a HumanoidModel:

    DarkMetalArmorItem$Chestplate        the piece, holding its texture path
    DarkMetalArmorItem$Chestplate$1      builds the model it is drawn with

The inner class is what pairs the mod's own parts with the vanilla ones, a
line at a time: it pushes "left_arm" and then reads Modeldarkbib.LeftArm. That
pairing is the only thing that says which limb a part rides on, so guessing
from the class name (which is how the rest of the extractor has to work) picks
the wrong model whenever a mod ships more than one set of similar geometry.
"""

import os
import re
import subprocess
import tempfile
import zipfile

# the inner class MCreator names each piece with
SLOT_CLASS = {'head': 'Helmet', 'chest': 'Chestplate', 'legs': 'Leggings', 'feet': 'Boots'}

# vanilla's part names, as the limbs the portal knows
LIMBS = {'head': 'head', 'hat': 'head', 'body': 'body',
         'left_arm': 'armL', 'right_arm': 'armR',
         'left_leg': 'legL', 'right_leg': 'legR'}

PIECE = re.compile(r'^(?:.*/)?([\w$]+)Item\$(Helmet|Chestplate|Leggings|Boots)(\$1)?\.class$')
ITEMS = re.compile(r'^(?:.*/)?\w*ModItems\.class$')
WHOLE = re.compile(r'^(?:.*/)?([\w]+)Item\.class$')
PNG   = re.compile(rb'([a-z0-9_-][a-z0-9_.-]*):(textures/[\w/.-]+\.png)')

STRING   = re.compile(r'^\s*\d+:\s+ldc\w*\s+#\d+\s+// String (.*)$')
GETFIELD = re.compile(r'^\s*\d+:\s+getfield\s+#\d+\s+// Field ([\w/$]+)\.([\w$]+):')


class Sets:
    """Every armor piece the MCreator mods ship, by (namespace, set, slot).

    The jar each namespace came from is kept alongside, because a piece whose
    class is not named after its registry id can only be found by reading the
    mod's item list, and that is worth doing only when the name lookup fails.
    """

    def __init__(self):
        self.pieces = {}
        self.whole = {}          # (namespace, set) -> an item covering all four
        self.jars = {}
        self.lists = {}          # namespace -> registry name: class name
        self.names = {}          # namespace -> its item list, read on demand

    def __len__(self):
        return len(self.pieces)


def index(paths, namespace_of):
    found = Sets()
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:
            continue
        with zf:
            for entry in zf.namelist():
                if ITEMS.match(entry):
                    found.lists.setdefault(namespace_of(path, entry), entry)
                    continue
                m = PIECE.match(entry)
                if not m:
                    m = WHOLE.match(entry)
                    if m:
                        ns = namespace_of(path, entry)
                        if ns:
                            found.whole[(ns, m.group(1).lower())] = (path, entry)
                            found.jars[ns] = path
                    continue
                ns = namespace_of(path, entry)
                if not ns:
                    continue
                key = (ns, m.group(1).lower(), m.group(2))
                which = 'model' if m.group(3) else 'item'
                found.pieces.setdefault(key, {})[which] = (path, entry)
                found.jars[ns] = path
    return found


def texture(ref):
    """The sheet the piece names, as an entry in its own jar."""
    with zipfile.ZipFile(ref[0]) as zf:
        entries = set(zf.namelist())
        for m in PNG.finditer(zf.read(ref[1])):
            asset = f'assets/{m.group(1).decode()}/{m.group(2).decode()}'
            if asset in entries:
                return (ref[0], asset)
    return None


def disassemble(jar, entry, verbose=False):
    with tempfile.TemporaryDirectory() as work:
        with zipfile.ZipFile(jar) as zf:
            path = zf.extract(entry, work)
        return subprocess.run(['javap', '-v' if verbose else '-c', '-p', path],
                              capture_output=True, text=True, check=True).stdout


def model_of(ref):
    """(the model class the piece draws itself with, {its part: limb}).

    The bytecode pushes the vanilla part's name, builds the mod's model and
    then reads the part off it, so the last name pushed before a field read
    is the one that field answers to.
    """
    listing = disassemble(*ref)
    pending, holder, bound = None, None, {}
    for line in listing.splitlines():
        m = STRING.match(line)
        if m:
            pending = m.group(1).strip()
            continue
        m = GETFIELD.match(line)
        if not m:
            continue
        owner, field = m.group(1), m.group(2)
        if '/client/model/' not in owner or owner.startswith('net/minecraft/'):
            continue
        if pending in LIMBS:
            bound[field] = LIMBS[pending]
            holder = owner
    return (holder, bound) if holder and bound else (None, {})


def model_class(jar, owner):
    entry = owner + '.class'
    with zipfile.ZipFile(jar) as zf:
        return (jar, entry) if entry in zf.namelist() else None


LAMBDA  = re.compile(r'^\s+\S.*\s(lambda\$[\w$]+)\(\);$')
NEW     = re.compile(r'^\s*\d+:\s+new\s+#\d+\s+// class ([\w/$]+)$')
BOOT    = re.compile(r'^\s{2}(\d+): #\d+ REF_')
TARGET  = re.compile(r'^\s+#\d+ REF_invokeStatic [\w/$]+\.(lambda\$[\w$]+):')
NAME    = re.compile(r'^\s*\d+:\s+ldc\w*\s+#\d+\s+// String ([a-z0-9_]+)$')
DYNAMIC = re.compile(r'^\s*\d+:\s+invokedynamic\s+#\d+,\s+\d+\s+// InvokeDynamic #(\d+):')


def item_list(jar, entry):
    """{registry id: class name} from the list a mod registers its items with.

    MCreator names an item's class after whatever the author first called it,
    which is not always what the item ended up registered as: one mod's
    lucky_hat is a LuckyAmuletItem. The registry call is where the two meet,
    and it reaches the class through a lambda, so the bootstrap table has to
    be walked to get from the name to the constructor.
    """
    listing = disassemble(jar, entry, verbose=True)
    built, boots, out = {}, {}, {}

    lambda_name, index_at = None, None
    for line in listing.splitlines():
        m = LAMBDA.match(line)
        if m:
            lambda_name = m.group(1)
            continue
        m = NEW.match(line)
        if m and lambda_name and lambda_name not in built:
            built[lambda_name] = m.group(1).rsplit('/', 1)[-1]
            continue
        m = BOOT.match(line)
        if m:
            index_at = int(m.group(1))
            continue
        m = TARGET.match(line)
        if m and index_at is not None:
            boots[index_at] = m.group(1)
            index_at = None

    pending = None
    for line in listing.splitlines():
        m = NAME.match(line)
        if m:
            pending = m.group(1)
            continue
        m = DYNAMIC.match(line)
        if m and pending:
            made = built.get(boots.get(int(m.group(1))))
            if made:
                out[pending] = made
            pending = None
    return out


CLASS_REF = re.compile(r'// class ([\w/$]+)')
STRING_AT = re.compile(r'^\s*\d+:\s+ldc\w*\s+#\d+\s+// String (.*)$')


def referenced(jar, entries, ends):
    """The classes these ones name that live in the same jar and end in `ends`."""
    out = []
    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
    for entry in entries:
        for m in CLASS_REF.finditer(disassemble(jar, entry)):
            name = m.group(1)
            if name.endswith(ends) and name + '.class' in have and name not in out:
                out.append(name)
    return [n + '.class' for n in out]


def resources(jar, entry):
    """The geo model and sheet a GeckoLib model names, as jar entries.

    Both are built as ResourceLocation(namespace, path), so the namespace is
    whichever bare word was pushed last before the path.
    """
    found, namespace = {}, None
    with zipfile.ZipFile(jar) as zf:
        have = set(zf.namelist())
    for line in disassemble(jar, entry).splitlines():
        m = STRING_AT.match(line)
        if not m:
            continue
        text = m.group(1).strip()
        if '/' not in text:
            namespace = text
            continue
        if not namespace:
            continue
        asset = f'assets/{namespace}/{text}'
        if asset not in have:
            continue
        if text.endswith('.geo.json'):
            found.setdefault('model', (jar, asset))
        elif text.endswith('.png'):
            found.setdefault('texture', (jar, asset))
    return found if 'model' in found and 'texture' in found else {}


def drawn_with(jar, entry):
    """Follow an armor item to the geo model it is drawn with.

    A set that keeps one class for all four slots hands the game a renderer
    instead, which holds the model, which holds the model file and its sheet.
    """
    stem = entry[:-len('.class')]
    with zipfile.ZipFile(jar) as zf:
        family = [entry] + [n for n in zf.namelist() if n.startswith(stem + '$')]
    for renderer in referenced(jar, family, 'Renderer'):
        for model in referenced(jar, [renderer], 'Model'):
            found = resources(jar, model)
            if found:
                return found
    return {}


def piece(sets, ns, names, slot):
    """What one piece of a set is drawn with, or None if this mod is not one.

    'sheet' is a piece left to the vanilla model, drawn as a flat overlay;
    'java' is one the mod builds out of Minecraft's own boxes; 'geo' is one it
    ships as a Blockbench model.
    """
    ref = None
    for name in names:
        ref = sets.pieces.get((ns, name.replace('_', ''), SLOT_CLASS[slot]))
        if ref:
            break
    if not ref:                          # the class is not named after the item
        if ns not in sets.names:
            entry, jar = sets.lists.get(ns), sets.jars.get(ns)
            sets.names[ns] = item_list(jar, entry) if entry and jar else {}
        for name in names:
            made = sets.names[ns].get(name)
            if made:
                base = made.partition('$')[0].lower().removesuffix('item')
                ref = sets.pieces.get((ns, base, SLOT_CLASS[slot]))
                if not ref and (ns, base) in sets.whole:
                    return geo_set(sets.whole[(ns, base)])
                break
    if not ref:
        for name in names:
            if (ns, name.replace('_', '')) in sets.whole:
                return geo_set(sets.whole[(ns, name.replace('_', ''))])
    if not ref or 'item' not in ref:
        return None

    sheet = texture(ref['item'])
    if not sheet:
        return None
    if 'model' not in ref:
        return {'kind': 'sheet', 'texture': sheet}

    owner, bound = model_of(ref['model'])
    if not owner:
        return {'kind': 'sheet', 'texture': sheet}
    return {'kind': 'java', 'texture': sheet, 'bound': bound,
            'model': model_class(ref['model'][0], owner)}


def geo_set(item_ref):
    found = drawn_with(*item_ref)
    return {'kind': 'geo', **found} if found else None
