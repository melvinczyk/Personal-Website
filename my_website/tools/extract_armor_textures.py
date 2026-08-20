"""Pull the armor textures every rostered player is wearing out of the mod jars.

Run from my_website/:
    python tools/extract_armor_textures.py "<path to the instance's mods folder>" [more folders...]

Minecraft renders worn armor as two flat overlays on the player model:
layer 1 carries the helmet, chestplate and boots, layer 2 the leggings. Both
live at assets/<mod>/textures/models/armor/<material>_layer_N.png, so an item
id like epicpaladins:moonlight_boots resolves by stripping the slot off the
end. Anything a mod draws with its own 3D model has no such texture and is
reported as unmatched rather than guessed at.
"""

import json
import os
import re
import struct
import sys
import zipfile

import io
import tempfile

from PIL import Image

import geo as geo_model
import javamodel
import mcreator

HERE    = os.path.dirname(os.path.abspath(__file__))
STATIC  = os.path.join(os.path.dirname(HERE), 'static', 'minecraft')
OUT_DIR = os.path.join(STATIC, 'armor')
INDEX   = os.path.join(OUT_DIR, 'armor.json')

VANILLA_JAR = os.path.expanduser(
    '~/Documents/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')

ARMOR_PATH = re.compile(r'^assets/([^/]+)/textures/models/armor/(.+)_layer_([12])\.png$')
# some mods skip the _layer_N convention and ship "<material>.png" plus
# "<material>_legs.png" in the same folder
ARMOR_ALT  = re.compile(r'^assets/([^/]+)/textures/models/armor/([^/]+?)(_legs)?\.png$')

# the piece of the item name that says which slot it goes in
SLOT_WORDS = ('helmet', 'chestplate', 'chest', 'leggings', 'legs', 'boots',
              'feet', 'cap', 'tunic', 'pants', 'shoes', 'skull', 'head', 'hat',
              'mask', 'crown', 'plate', 'greaves', 'shirt')
ARMOR_SLOTS = {103: 'head', 102: 'chest', 101: 'legs', 100: 'feet'}

GEO_PATH = re.compile(r'^assets/([^/]+)/geo/(?:.*/)?([^/]+)\.geo\.json$')
GEO_TEX  = re.compile(r'^assets/([^/]+)/textures/(?:armor|models/armor|entity/armor)/(?:.*/)?([^/]+)\.png$')
ITEM_TEX = re.compile(r'^assets/([^/]+)/textures/item/(?:.*/)?([^/]+)\.png$')
CLASS    = re.compile(r'^([\w/$]*?)([\w$]*[Mm]odel[\w$]*)\.class$')

# which word in a class name says it is the piece for a given slot
SLOT_WORDS_IN_CLASS = {
    'head':  ('helmet', 'helm', 'head', 'hat', 'mask', 'crown'),
    'chest': ('chestplate', 'chest', 'armor', 'body', 'tunic'),
    'legs':  ('leggings', 'legging', 'legs', 'pants', 'greaves'),
    'feet':  ('boots', 'boot', 'feet', 'shoes'),
}

def png_size(data):
    return struct.unpack('>II', data[16:24])


def jars(folders):
    found = []
    if os.path.exists(VANILLA_JAR):
        found.append(VANILLA_JAR)
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            if name.endswith('.jar'):
                found.append(os.path.join(folder, name))
    return found


def build_index(paths):
    """(namespace, material) -> {layer: (jar, entry)}"""
    index = {}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:
            continue
        with zf:
            for entry in zf.namelist():
                m = ARMOR_PATH.match(entry)
                if m:
                    ns, material, layer = m.group(1), m.group(2), int(m.group(3))
                    # overlays are the dye mask for leather, not a set of their own
                    if material.endswith('_overlay'):
                        continue
                    index.setdefault((ns, material), {})[layer] = (path, entry)
                    continue
                m = ARMOR_ALT.match(entry)
                if m and '_layer_' not in m.group(2):
                    ns, material, layer = m.group(1), m.group(2), 2 if m.group(3) else 1
                    index.setdefault((ns, material), {})[layer] = (path, entry)
    return index


def candidates(item_id):
    ns, _, path = item_id.partition(':')
    if not path:
        ns, path = 'minecraft', ns
    parts = path.split('_')
    names = []
    while parts and parts[-1] in SLOT_WORDS:
        parts.pop()
        names.append('_'.join(parts))
    names.append(path)
    out = []
    for name in names:
        for variant in (name, name[:-6] if name.endswith('_armor') else None,
                        name[6:] if name.startswith('armor_') else None):
            if variant and variant not in out:
                out.append(variant)
    return ns, out


def resolve(item_id, index):
    ns, names = candidates(item_id)
    for name in names:                       # the mod's own namespace wins
        if (ns, name) in index:
            return (ns, name)
    for name in names:
        for key in index:
            if key[1] == name:
                return key
    return None


def build_geo_index(paths):
    """(namespace, stem) -> (jar, entry) for models, their textures, and the
    item folder, which is where one mod keeps an armor sheet."""
    models, textures, items, classes = {}, {}, {}, {}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:
            continue
        with zf:
            for entry in zf.namelist():
                m = GEO_PATH.match(entry)
                if m:
                    models[(m.group(1), m.group(2))] = (path, entry)
                m = GEO_TEX.match(entry)
                if m and '_layer_' not in m.group(2):
                    textures[(m.group(1), m.group(2))] = (path, entry)
                m = ITEM_TEX.match(entry)
                if m:
                    items[(m.group(1), m.group(2))] = (path, entry)
                m = CLASS.match(entry)
                if m:
                    classes[(namespace_of(path, entry), m.group(2))] = (path, entry)
    return models, textures, items, classes


_jar_namespace = {}


def namespace_of(jar, entry):
    """A class file says nothing about the mod id, so ask the jar's assets.

    A jar may carry more than one mod, in which case the class's own package
    is what tells them apart: net/mcreator/minepiece/... is minepiece's.
    """
    if jar not in _jar_namespace:
        with zipfile.ZipFile(jar) as zf:
            found = {name.split('/')[1] for name in zf.namelist()
                     if name.startswith('assets/') and name.count('/') > 1}
        found.discard('minecraft')
        _jar_namespace[jar] = sorted(found)
    found = _jar_namespace[jar]
    if len(found) == 1:
        return found[0]
    parts = set(entry.split('/'))
    for ns in found:
        if ns in parts:
            return ns
    return None


def pick(index, ns, names, suffixes):
    """The first entry in `ns` whose stem is one of `names` plus a suffix."""
    for name in names:
        for suffix in suffixes:
            if (ns, name + suffix) in index:
                return (ns, name + suffix), index[(ns, name + suffix)]
    for name in names:                       # otherwise the stem has to contain it
        hits = [k for k in index if k[0] == ns and name in k[1]]
        if len(hits) == 1:
            return hits[0], index[hits[0]]
    return None, None


GEO_SUFFIXES = ('_armor', '', '_armor_model', '_set')
TEX_SUFFIXES = ('_armor_textures', '_armor', '', '_textures', '_layer_1')


def resolve_geo(item_id, models, textures):
    ns, names = candidates(item_id)
    model_key, model_ref = pick(models, ns, names, GEO_SUFFIXES)
    if not model_ref:
        return None
    _, tex_ref = pick(textures, ns, names, TEX_SUFFIXES)
    if not tex_ref:
        return None
    return model_key, model_ref, tex_ref


def convert_geo(model_ref, tex_ref):
    """Read the model and its sheet, dropping every face the sheet draws as
    nothing: armor sets carry a lot of cubes that are never seen."""
    with zipfile.ZipFile(model_ref[0]) as zf:
        model = json.loads(zf.read(model_ref[1]))
    with zipfile.ZipFile(tex_ref[0]) as zf:
        raw = zf.read(tex_ref[1])

    image = Image.open(io.BytesIO(raw)).convert('RGBA')
    alpha = image.getchannel('A')
    declared = model['minecraft:geometry'][0]['description']
    scale = image.width / declared.get('texture_width', image.width)

    def visible(u, v, w, h):
        box = (int(u * scale), int(v * scale),
               max(int((u + w) * scale), int(u * scale) + 1),
               max(int((v + h) * scale), int(v * scale) + 1))
        box = (max(0, box[0]), max(0, box[1]),
               min(image.width, box[2]), min(image.height, box[3]))
        if box[2] <= box[0] or box[3] <= box[1]:
            return False
        return alpha.crop(box).getextrema()[1] >= 128

    return geo_model.convert(model, visible), raw


def worn_items():
    """Every armor item id worn in any season, with the seasons it turns up in."""
    sys.path.insert(0, os.path.dirname(HERE))
    from minecraft import nbt

    items = {}
    for season in sorted(os.listdir(STATIC)):
        stats = os.path.join(STATIC, season, 'stats')
        if not os.path.isdir(stats):
            continue
        for name in sorted(os.listdir(stats)):
            if not name.endswith('.dat'):
                continue
            try:
                data = nbt.load(os.path.join(stats, name))
            except Exception:
                continue
            for entry in data.get('Inventory', []):
                if entry.get('Slot') in ARMOR_SLOTS and entry.get('id'):
                    items.setdefault(entry['id'], set()).add(season)
    return items


def build_item_sheet(item_id, items, out, written):
    """Last resort: a mod that codes its armor model in Java still has to give
    it a texture, and some keep an ordinary 64x32 sheet in with the icons. The
    shape of the file is the tell, since icons are 16 or 32 square."""
    ns, names = candidates(item_id)
    _, ref = pick(items, ns, names, ('', '_layer_1', '_armor'))
    if not ref:
        return False
    with zipfile.ZipFile(ref[0]) as zf:
        data = zf.read(ref[1])
    w, h = png_size(data)
    if w != 64 or h not in (32, 64):
        return False

    filename = f'{ns}__{os.path.splitext(os.path.basename(ref[1]))[0]}_layer_1.png'
    if filename not in written:
        with open(os.path.join(OUT_DIR, filename), 'wb') as fh:
            fh.write(data)
        written.add(filename)
    out[item_id] = {'l1': {'file': filename, 'w': w, 'h': h}}
    print(f'{item_id:<48} {ns}:{ref[1].rsplit("/", 1)[-1]} (sheet filed with the icons)')
    return True


# mcreator writes the armor texture into the item class as a plain string, and
# the constant pool keeps it as readable utf-8
PNG_REF = re.compile(rb'([a-z0-9_.-]{2,}):(textures/[\w/.-]+\.png)')


def java_textures(jar, names):
    """Every texture named by a class belonging to this set."""
    found = []
    wanted = [n.replace('_', '') for n in names]
    with zipfile.ZipFile(jar) as zf:
        entries = set(zf.namelist())
        for entry in entries:
            if not entry.endswith('.class'):
                continue
            base = entry.rsplit('/', 1)[-1].lower().replace('_', '')
            if not any(n in base for n in wanted):
                continue
            for m in PNG_REF.finditer(zf.read(entry)):
                asset = f'assets/{m.group(1).decode()}/{m.group(2).decode()}'
                if asset in entries and asset not in found:
                    found.append(asset)
    return found


def best_texture(jar, assets, slot, size):
    """The one whose shape matches the model, then whose name matches the slot."""
    best, best_score = None, -99
    with zipfile.ZipFile(jar) as zf:
        for asset in assets:
            data = zf.read(asset)
            score = 3 if png_size(data) == size else 0
            name = asset.rsplit('/', 1)[-1].lower()
            for other, words in SLOT_WORDS_IN_CLASS.items():
                if any(w in name for w in words):
                    score += 2 if other == slot else -2
            if score > best_score:
                best, best_score = (jar, asset), score
    return best


def build_java(item_id, class_index, textures, items, out, written):
    """A model the mod wrote in Java: read it back out of the bytecode."""
    ns, names = candidates(item_id)
    slot = slot_for(item_id)
    if not slot:
        return False

    wanted = [n.replace('_', '') for n in names]
    hits = []
    for (namespace, cls), ref in class_index.items():
        if namespace != ns:
            continue
        plain = cls.lower()
        matched = next((n for n in wanted if n in plain), None)
        if not matched:
            continue
        # a set ships one class per piece, but its own name runs through all of
        # them, so take that out before asking which piece a class is for:
        # otherwise the "armor" in ChestHolyArmorModel reads as a chest piece
        # and so does the one in FeetHolyArmorModel
        rest = plain.replace(matched, '')
        mine = any(w in rest for w in SLOT_WORDS_IN_CLASS[slot])
        other = any(w in rest for name, group in SLOT_WORDS_IN_CLASS.items()
                    if name != slot for w in group)
        if other and not mine:
            continue
        hits.append((0 if mine else 1, len(cls), cls, ref))
    if not hits:
        return False
    hits.sort()

    _, _, cls, ref = hits[0]
    with tempfile.TemporaryDirectory() as work:
        with zipfile.ZipFile(ref[0]) as zf:
            path = zf.extract(ref[1], work)
        try:
            # the item says which slot it is worn in; the model's own part
            # names may not, since a boot is often just a leg with a boot on it
            model = javamodel.read(path, None, slot)
        except Exception as exc:
            print(f'{item_id:<48} bytecode failed: {exc}')
            return False
    if slot not in model['slots']:
        return False

    # the model says what shape of sheet it expects to be painted with
    tex_ref = best_texture(ref[0], java_textures(ref[0], names), slot,
                           (model['tw'], model['th']))
    if not tex_ref:
        _, tex_ref = pick(textures, ns, names, TEX_SUFFIXES)
    if not tex_ref:
        _, tex_ref = pick(items, ns, names, ('', '_layer_1', '_armor'))
    if not tex_ref:
        return False

    with zipfile.ZipFile(tex_ref[0]) as zf:
        raw = zf.read(tex_ref[1])
    texture = f'{ns}__{cls}.png'
    filename = f'{ns}__{cls}_{slot}.model.json'
    # a java model may be drawn against a sheet of any size
    model['tw'], model['th'] = png_size(raw)
    if filename not in written:
        model['texture'] = texture
        with open(os.path.join(OUT_DIR, texture), 'wb') as fh:
            fh.write(raw)
        with open(os.path.join(OUT_DIR, filename), 'w') as fh:
            json.dump(model, fh, separators=(',', ':'), sort_keys=True)
        written.add(filename)

    cubes = sum(len(v) for v in model['slots'][slot].values())
    out[item_id] = {'geo': {'file': filename, 'slot': slot}}
    print(f'{item_id:<48} {ns}:{cls} (java model, {cubes} cubes)')
    return True


def build_mcreator(item_id, pieces, out, written):
    """A set built with MCreator: the item class says outright which model and
    which sheet the piece is drawn with, so nothing has to be guessed."""
    slot = slot_for(item_id)
    if not slot:
        return False
    ns, names = candidates(item_id)
    found = mcreator.piece(pieces, ns, names, slot)
    if not found:
        return False

    if found['kind'] == 'geo':
        stem = os.path.basename(found['model'][1]).replace('.geo.json', '')
        return write_geo(item_id, ns, stem, found['model'], found['texture'],
                         slot, out, written, 'mcreator model')

    sheet_ref, model_ref = found['texture'], found.get('model')
    bound = found.get('bound')

    with zipfile.ZipFile(sheet_ref[0]) as zf:
        raw = zf.read(sheet_ref[1])
    stem = os.path.splitext(os.path.basename(sheet_ref[1]))[0]
    stem = re.sub(r'_layer_[12]$', '', stem)   # the name says the layer already
    w, h = png_size(raw)

    if not model_ref:
        # left to the vanilla model, so the sheet is an ordinary flat overlay
        layer = 2 if slot == 'legs' else 1
        filename = f'{ns}__{stem}_layer_{layer}.png'
        if filename not in written:
            with open(os.path.join(OUT_DIR, filename), 'wb') as fh:
                fh.write(raw)
            written.add(filename)
        out[item_id] = {f'l{layer}': {'file': filename, 'w': w, 'h': h}}
        print(f'{item_id:<48} {ns}:{stem} (mcreator, vanilla model)')
        return True

    cls = os.path.splitext(os.path.basename(model_ref[1]))[0]
    with tempfile.TemporaryDirectory() as work:
        with zipfile.ZipFile(model_ref[0]) as zf:
            path = zf.extract(model_ref[1], work)
        try:
            model = javamodel.read(path, bound, slot)
        except Exception as exc:
            print(f'{item_id:<48} bytecode failed: {exc}')
            return False
    if slot not in model['slots']:
        return False
    model['tw'], model['th'] = w, h

    # a set may draw several pieces with one model class, each keeping only the
    # parts that piece covers, so the slot belongs in the name as well
    texture = f'{ns}__{stem}.png'
    filename = f'{ns}__{cls}_{slot}.model.json'
    if filename not in written:
        model['texture'] = texture
        with open(os.path.join(OUT_DIR, texture), 'wb') as fh:
            fh.write(raw)
        with open(os.path.join(OUT_DIR, filename), 'w') as fh:
            json.dump(model, fh, separators=(',', ':'), sort_keys=True)
        written.add(filename)

    cubes = sum(len(v) for v in model['slots'][slot].values())
    out[item_id] = {'geo': {'file': filename, 'slot': slot}}
    print(f'{item_id:<48} {ns}:{cls} (mcreator model, {cubes} cubes)')
    return True


def slot_for(item_id):
    """Which slot the item goes in, from the word its name ends with."""
    path = item_id.partition(':')[2] or item_id
    for word, slot in (('helmet', 'head'), ('skull', 'head'), ('head', 'head'),
                       ('hat', 'head'), ('cap', 'head'), ('mask', 'head'), ('crown', 'head'),
                       ('chestplate', 'chest'), ('chest', 'chest'), ('tunic', 'chest'),
                       ('shirt', 'chest'), ('plate', 'chest'),
                       ('leggings', 'legs'), ('legs', 'legs'), ('pants', 'legs'),
                       ('greaves', 'legs'),
                       ('boots', 'feet'), ('feet', 'feet'), ('shoes', 'feet')):
        if path.endswith(word):
            return slot
    return None


def build_geo(item_id, models, textures, out, written):
    found = resolve_geo(item_id, models, textures)
    if not found:
        return False
    (ns, stem), model_ref, tex_ref = found
    slot = slot_for(item_id)
    if not slot:
        return False

    return write_geo(item_id, ns, stem, model_ref, tex_ref, slot, out, written, 'model')


def write_geo(item_id, ns, stem, model_ref, tex_ref, slot, out, written, note):
    try:
        model, raw = convert_geo(model_ref, tex_ref)
    except Exception as exc:
        print(f'{item_id:<48} model failed: {exc}')
        return False
    if slot not in model['slots']:
        return False

    texture = f'{ns}__{stem}.png'
    filename = f'{ns}__{stem}.model.json'
    if filename not in written:
        model['texture'] = f'{texture}'
        with open(os.path.join(OUT_DIR, texture), 'wb') as fh:
            fh.write(raw)
        with open(os.path.join(OUT_DIR, filename), 'w') as fh:
            json.dump(model, fh, separators=(',', ':'), sort_keys=True)
        written.add(filename)

    cubes = sum(len(v) for v in model['slots'][slot].values())
    out[item_id] = {'geo': {'file': filename, 'slot': slot}}
    print(f'{item_id:<48} {ns}:{stem} ({note}, {cubes} cubes)')
    return True


def main():
    folders = [f for f in sys.argv[1:] if os.path.isdir(f)]
    if not folders:
        print(__doc__)
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    all_jars = jars(folders)
    index = build_index(all_jars)
    models, textures, item_sheets, classes = build_geo_index(all_jars)
    pieces = mcreator.index(all_jars, namespace_of)
    print(f'{len(index)} armor materials, {len(models)} models, '
          f'{len(pieces)} mcreator pieces, across {len(all_jars)} jars\n')

    out, missing, written = {}, [], set()
    for item_id, seasons in sorted(worn_items().items()):
        # a model the mod drew itself beats a flat sheet, which for those mods
        # is only the texture their own geometry is painted with
        if (build_mcreator(item_id, pieces, out, written)
                or build_geo(item_id, models, textures, out, written)
                or build_java(item_id, classes, textures, item_sheets, out, written)):
            continue

        key = resolve(item_id, index)
        if not key:
            if not build_item_sheet(item_id, item_sheets, out, written):
                missing.append((item_id, sorted(seasons)))
            continue

        ns, material = key
        record = {}
        for layer, (jar, entry) in sorted(index[key].items()):
            filename = f'{ns}__{material}_layer_{layer}.png'
            with zipfile.ZipFile(jar) as zf:
                data = zf.read(entry)
            if filename not in written:
                with open(os.path.join(OUT_DIR, filename), 'wb') as fh:
                    fh.write(data)
                written.add(filename)
            w, h = png_size(data)
            record[f'l{layer}'] = {'file': filename, 'w': w, 'h': h}
        out[item_id] = record
        print(f'{item_id:<48} {ns}:{material}')

    with open(INDEX, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True)

    print(f'\nwrote {INDEX} ({len(out)} items, {len(written)} textures)')
    if missing:
        print('\nnothing to render these with (their mods are not in the folders given):')
        for item_id, seasons in missing:
            print(f'  {item_id:<48} {", ".join(seasons)}')


if __name__ == '__main__':
    main()
