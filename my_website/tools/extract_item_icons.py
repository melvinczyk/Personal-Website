"""Pull an icon for every item any player is carrying out of the mod jars.

Run from my_website/:
    python tools/extract_item_icons.py "<path to a mods folder>" [more folders...]

An item's icon is not a file named after the item: the item names a model, the
model may be built on another model, and somewhere up that chain is the texture
the game actually draws. Flat items give it as layer0; a block's item gives the
faces of the block instead, any of which will do for a 16 pixel tile.

Items a mod draws with a real 3D model have no icon at all. Those are reported
and the gallery falls back to a lettered tile.
"""

import io
import json
import os
import sys
import zipfile

from PIL import Image

HERE   = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), 'static', 'minecraft')
OUT_DIR = os.path.join(STATIC, 'items')
INDEX   = os.path.join(OUT_DIR, 'items.json')

VANILLA_JAR = os.path.expanduser(
    '~/Documents/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')

# in the order the game itself would reach for them
FACES = ('layer0', 'all', 'texture', 'side', 'north', 'front', 'end', 'particle',
         'top', 'cross', 'fan', 'rail', 'wall', 'up', 'down', 'east', 'west')


def jars(folders):
    found = [VANILLA_JAR] if os.path.exists(VANILLA_JAR) else []
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            if name.endswith('.jar'):
                found.append(os.path.join(folder, name))
    return found


def index_assets(paths):
    """(namespace, path) -> (jar, entry), for item and block models and textures."""
    models, textures = {}, {}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:
            continue
        with zf:
            for entry in zf.namelist():
                parts = entry.split('/')
                if len(parts) < 4 or parts[0] != 'assets':
                    continue
                ns, kind = parts[1], parts[2]
                if kind == 'models' and entry.endswith('.json'):
                    models.setdefault((ns, '/'.join(parts[3:])[:-5]), (path, entry))
                elif kind == 'textures' and entry.endswith('.png'):
                    textures.setdefault((ns, '/'.join(parts[3:])[:-4]), (path, entry))
    return models, textures


def read_json(ref):
    with zipfile.ZipFile(ref[0]) as zf:
        return json.loads(zf.read(ref[1]).decode('utf-8-sig'))


def split(ref, fallback='minecraft'):
    ns, _, path = ref.partition(':')
    return (ns, path) if path else (fallback, ns)


def texture_of(item_id, models):
    """Walk the model chain until something names a texture."""
    ns, name = split(item_id)
    ref = models.get((ns, f'item/{name}')) or models.get((ns, f'block/{name}'))
    seen, found = set(), {}
    while ref and ref[1] not in seen:
        seen.add(ref[1])
        try:
            model = read_json(ref)
        except Exception:
            break
        for key, value in (model.get('textures') or {}).items():
            found.setdefault(key, value)
        parent = model.get('parent')
        if not parent:
            break
        ref = models.get(split(parent))

    for face in FACES:
        if face in found and not found[face].startswith('#'):
            return found[face]
    for value in found.values():
        if not value.startswith('#'):
            return value
    return None


def main():
    folders = [f for f in sys.argv[1:] if os.path.isdir(f)]
    if not folders:
        print(__doc__)
        return

    sys.path.insert(0, os.path.dirname(HERE))
    from minecraft import nbt

    carried = set()
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
            for entry in data.get('Inventory', []) + data.get('EnderItems', []):
                if entry.get('id'):
                    carried.add(entry['id'])

    os.makedirs(OUT_DIR, exist_ok=True)
    all_jars = jars(folders)
    models, textures = index_assets(all_jars)
    print(f'{len(carried)} items carried, {len(models)} models, '
          f'{len(textures)} textures, across {len(all_jars)} jars\n')

    out, missing, written = {}, [], {}
    for item_id in sorted(carried):
        found = texture_of(item_id, models)
        ref = textures.get(split(found)) if found else None
        if not ref:
            missing.append(item_id)
            continue
        key = (ref[1], os.path.basename(ref[0]))
        if key not in written:
            ns, name = split(item_id)
            filename = f'{ns}__{name.replace("/", "_")}.png'
            with zipfile.ZipFile(ref[0]) as zf:
                data = zf.read(ref[1])
            try:
                icon = Image.open(io.BytesIO(data)).convert('RGBA')
            except Exception:
                missing.append(item_id)
                continue
            # an animated texture is its frames stacked, so the first one is
            # the icon; everything else is re-encoded to shed mod metadata
            if icon.height > icon.width:
                icon = icon.crop((0, 0, icon.width, icon.width))
            if icon.width > 64:
                icon = icon.resize((64, 64), Image.NEAREST)
            icon.save(os.path.join(OUT_DIR, filename), optimize=True)
            written[key] = filename
        out[item_id] = written[key]

    with open(INDEX, 'w') as fh:
        json.dump(out, fh, indent=0, sort_keys=True)
    print(f'wrote {INDEX} ({len(out)} icons, {len(written)} files)')
    if missing:
        print(f'\nno flat icon for these {len(missing)} '
              f'(their mod draws them in 3D):')
        for item_id in missing:
            print(f'  {item_id}')


if __name__ == '__main__':
    main()
