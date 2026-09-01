"""Build the legendary fish board out of Starcatcher's own data.

Run from my_website/:
    python tools/fish.py ["<path to a mods folder>"]

Starcatcher keeps its fish as a datapack registry rather than in code: one
JSON per fish under data/<namespace>/starcatcher/fish/, carrying the rarity,
the item the catch hands you, and the mod that has to be present for the fish
to exist at all. The website wants the legendary slice of that as a board -
every one of them with a place from the start, the way the boss roster works,
so the gap where a catch has not happened yet is the point of the line.

Three things are pulled out of the jars:

  * which fish are legendary, and of those, which ones this pack can actually
    produce - a fish gated on a mod that is not installed is not a fish
    anybody here can catch, and putting it on the board would be an empty
    slot nobody could ever fill
  * the icon the game draws for each, found by walking the item's model chain
    the same way tools/extract_item_icons.py does
  * starcatcher:unknown_fish, the mod's own silhouette, which is what a fish
    nobody has landed yet is shown as

Everything lands in static/minecraft/fish/ with an index.json beside it, the
same shape the boss and miniboss folders use.
"""

import io
import json
import os
import sys
import zipfile

from PIL import Image

import extract_item_icons as icons

HERE   = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), 'static', 'minecraft')
OUT    = os.path.join(STATIC, 'fish')
INDEX  = os.path.join(OUT, 'index.json')

# The instance lives in a different place on each machine this is run from -
# bosses.py hard-codes one of them - so both are tried and the argument wins
# over either.
MODS = [os.path.expanduser(p) for p in (
    '~/curseforge/minecraft/Instances/Groid Pack OG/mods',
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG/mods',
)]

# The rung of Starcatcher's own ladder this board is about. Widen it and both
# the board and the tracker's export follow - fish_tracker.js has a matching
# FISH_RARITIES of its own, and the two want to agree.
WANTED = ('legendary',)

# What the mod draws for a fish nobody has landed. It is a real item texture
# rather than a GUI sprite, so it comes out of the same walk as the rest.
UNKNOWN = 'starcatcher:unknown_fish'

# unusualfishmod hands out three of its legendaries as a spawn egg for the
# live creature rather than a fish item or a bucket - the catch actually
# spawns the thing in front of you. A spawn egg has no texture of its own to
# walk to: it is vanilla's template_spawn_egg model, tinted from two colours
# baked into the entity's own Java class rather than sitting in any resource
# this script can read. Rather than leave three legendary slots blank, this
# builds the same egg the game would, coloured from the one place those
# colours are visible without decompiling anything: the entity's own skin.
VANILLA_JAR = os.path.expanduser(
    '~/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')
SPAWN_EGG_BASE    = 'assets/minecraft/textures/item/spawn_egg.png'
SPAWN_EGG_OVERLAY = 'assets/minecraft/textures/item/spawn_egg_overlay.png'
SPAWN_EGG_SKINS = {
    'unusualfishmod:celestial_fish_spawn_egg':
        'assets/unusualfishmod/textures/entity/celestial_fish.png',
    'unusualfishmod:gnasher_spawn_egg':
        'assets/unusualfishmod/textures/entity/gnasher.png',
    'unusualfishmod:prawn_spawn_egg':
        'assets/unusualfishmod/textures/entity/prawn.png',
}


def fish_files(paths):
    """Every fish definition in every jar: registry id -> (jar, entry).

    The id is the path, not the file: data/<ns>/starcatcher/fish/<rest>.json
    is <ns>:<rest>, which is how the trophies come out as trophy_trophy_gold
    rather than six things all called trophy.
    """
    out = {}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:                            # noqa: BLE001
            continue
        with zf:
            for entry in zf.namelist():
                parts = entry.split('/')
                if (len(parts) < 5 or parts[0] != 'data'
                        or parts[2] != 'starcatcher' or parts[3] != 'fish'
                        or not entry.endswith('.json')):
                    continue
                out[f'{parts[1]}:{"/".join(parts[4:])[:-5]}'] = (path, entry)
    return out


def installed(paths):
    """Which mod ids are actually in the folder, read off each jar's own id.

    A fish carries forge:mod_loaded conditions naming the mod that adds it.
    Matching those against the jars present is the difference between a board
    of what can be caught here and a board of what Starcatcher supports.
    """
    found = {'minecraft', 'forge', 'starcatcher'}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:                            # noqa: BLE001
            continue
        with zf:
            for name in ('META-INF/mods.toml', 'META-INF/neoforge.mods.toml'):
                if name not in zf.namelist():
                    continue
                for line in zf.read(name).decode('utf-8', 'replace').splitlines():
                    # TOML comments run to the end of the line and are not
                    # always stripped out of a mod's own template before it
                    # ships - unusualfishmod's modId line still carries its
                    # "#mandatory" straight off the example file, and left in
                    # it reads as part of the id
                    line = line.split('#', 1)[0].strip()
                    if line.startswith('modId'):
                        found.add(line.split('=')[1].strip().strip('"\' '))
    return found


def gates(spec):
    """The mods a fish needs before it exists at all."""
    return [c.get('modid') for c in spec.get('forge:conditions') or []
            if c.get('type') == 'forge:mod_loaded' and c.get('modid')]


def names(paths):
    """item id -> the name the game shows for it, out of every en_us.json."""
    out = {}
    for path in paths:
        try:
            zf = zipfile.ZipFile(path)
        except Exception:                            # noqa: BLE001
            continue
        with zf:
            for entry in zf.namelist():
                if not entry.endswith('/lang/en_us.json'):
                    continue
                try:
                    lang = json.loads(zf.read(entry).decode('utf-8-sig'))
                except Exception:                    # noqa: BLE001
                    continue
                for key, value in lang.items():
                    if key.startswith('item.') and key.count('.') == 2:
                        _, ns, name = key.split('.')
                        out.setdefault(f'{ns}:{name}', value)
    return out


def pretty(item_id):
    """'starcatcher:lush_pike' -> 'Lush Pike', when no lang file says better."""
    return ' '.join(word.capitalize()
                    for word in item_id.split(':')[-1].split('/')[-1].split('_'))


def fish_name(item_id, label):
    """The catch's own name, minus "Spawn Egg" for the three that hand out one.

    The board is a board of creatures, not of items - "Celestial Fish" reads
    as a catch the way "Celestial Fish Spawn Egg" reads as an inventory slot.
    """
    name = label.get(item_id) or pretty(item_id)
    return name[:-len(' Spawn Egg')] if name.endswith(' Spawn Egg') else name


def save_icon(ref, filename, px=64):
    """One item texture, squared off and written at a size a tile can use."""
    with zipfile.ZipFile(ref[0]) as zf:
        raw = zf.read(ref[1])
    icon = Image.open(io.BytesIO(raw)).convert('RGBA')
    # an animated texture is its frames stacked; the first one is the icon
    if icon.height > icon.width:
        icon = icon.crop((0, 0, icon.width, icon.width))
    if icon.width != px:
        icon = icon.resize((px, px), Image.NEAREST)
    icon.save(os.path.join(OUT, filename), optimize=True)
    return filename


def dominant_colours(image, n=2):
    """The n most common opaque colours in an image, most common first.

    Good enough to stand in for a spawn egg's own base/highlight colours
    without reading the two constants out of the entity's class file: an
    egg's base colour is usually most of the creature's own skin, and the
    next colour that is not just a shade of the first is usually the marking
    that would have been the highlight.
    """
    small = image.convert('RGBA').resize((32, 32))
    counts = {}
    for r, g, b, a in small.getdata():
        if a < 128:
            continue
        # a mob skin is a UV-unwrapped atlas, and most of the canvas around
        # the actual islands is blank white padding - left in, it outweighs
        # every real colour on the creature and every egg comes out white
        if r > 235 and g > 235 and b > 235:
            continue
        counts[(r, g, b)] = counts.get((r, g, b), 0) + 1
    ranked = sorted(counts, key=counts.get, reverse=True)
    picked = []
    for colour in ranked:
        # skip anything close to a colour already picked, or the palette
        # comes back as five shades of the same body colour
        if any(sum(abs(a - b) for a, b in zip(colour, kept)) < 90 for kept in picked):
            continue
        picked.append(colour)
        if len(picked) == n:
            break
    while len(picked) < n:
        picked.append(picked[-1] if picked else (150, 150, 150))
    return picked


def tint_layer(image, colour):
    """A grayscale mask, multiplied by a flat colour - see extract_tree_texture.py."""
    image = image.convert('RGBA')
    alpha = image.getchannel('A')
    gray = image.convert('L')
    tinted = Image.merge('RGB', tuple(
        gray.point(lambda v, c=c: round(v / 255 * c)) for c in colour))
    tinted.putalpha(alpha)
    return tinted


def save_spawn_egg_icon(paths, skin_entry, filename, px=64):
    """A spawn egg icon built the way the game builds one, coloured from the
    creature's own skin rather than from the class file that really holds it.

    Returns the filename, or None if either the entity skin or the vanilla
    spawn egg textures could not be found.
    """
    skin_ref = None
    for path in paths:
        try:
            with zipfile.ZipFile(path) as zf:
                if skin_entry in zf.namelist():
                    skin_ref = (path, skin_entry)
                    break
        except Exception:                            # noqa: BLE001
            continue
    if not skin_ref or not os.path.exists(VANILLA_JAR):
        return None

    with zipfile.ZipFile(skin_ref[0]) as zf:
        skin = Image.open(io.BytesIO(zf.read(skin_ref[1])))
    base_colour, spot_colour = dominant_colours(skin, 2)

    with zipfile.ZipFile(VANILLA_JAR) as zf:
        base = tint_layer(Image.open(io.BytesIO(zf.read(SPAWN_EGG_BASE))), base_colour)
        overlay = tint_layer(Image.open(io.BytesIO(zf.read(SPAWN_EGG_OVERLAY))), spot_colour)
    egg = Image.alpha_composite(base, overlay)
    egg = egg.resize((px, px), Image.NEAREST)
    egg.save(os.path.join(OUT, filename), optimize=True)
    return filename


def main():
    folders = ([f for f in sys.argv[1:] if os.path.isdir(f)]
               or [f for f in MODS if os.path.isdir(f)][:1])
    if not folders:
        print('no mods folder found - pass one:\n  ' + '\n  '.join(MODS))
        return

    paths = icons.jars(folders)
    models, textures = icons.index_assets(paths)
    have = installed(paths)
    label = names(paths)
    os.makedirs(OUT, exist_ok=True)

    board, skipped, iconless = [], [], []
    for fish_id, ref in sorted(fish_files(paths).items()):
        try:
            with zipfile.ZipFile(ref[0]) as zf:
                spec = json.loads(zf.read(ref[1]).decode('utf-8-sig'))
        except Exception:                            # noqa: BLE001
            continue
        if (spec.get('rarity') or '').lower() not in WANTED:
            continue
        # the trophies are legendary and are not fish: they are the reward
        # for a tournament, and the guide does not list them either
        if not spec.get('has_guide_entry'):
            skipped.append((fish_id, 'no guide entry'))
            continue
        missing = [mod for mod in gates(spec) if mod not in have]
        if missing:
            skipped.append((fish_id, 'needs ' + ', '.join(missing)))
            continue

        item = (spec.get('catch_info') or {}).get('item') or fish_id
        key = fish_id.replace(':', '__').replace('/', '_')

        icon_file = None
        if item in SPAWN_EGG_SKINS:
            # checked ahead of the generic walk on purpose: every spawn egg's
            # model chain resolves to vanilla's own plain, untinted
            # item/spawn_egg texture (that IS the real "layer0" of
            # item/template_spawn_egg), which is a valid find as far as
            # texture_of is concerned but is the wrong icon for every egg -
            # it carries no colour at all
            icon_file = save_spawn_egg_icon(paths, SPAWN_EGG_SKINS[item], f'{key}.png')
        else:
            found = icons.texture_of(item, models)
            art = textures.get(icons.split(found)) if found else None
            if art:
                icon_file = save_icon(art, f'{key}.png')
        if not icon_file:
            iconless.append(fish_id)
            continue

        size = spec.get('size_and_weight') or {}
        board.append({
            'key':    key,
            'id':     fish_id,
            'item':   item,
            'name':   fish_name(item, label),
            'mod':    fish_id.split(':')[0],
            'rarity': (spec.get('rarity') or '').upper(),
            'icon':   icon_file,
            # what an average one of these weighs in at, so a locked tile has
            # something to say about the fish beyond its name
            'size':   round(float(size.get('average_size_cm') or 0)),
            'weight': round(float(size.get('average_weight_grams') or 0)),
            # the chance the mod rolls it against, which is as close to a
            # difficulty as its own data gets
            'chance': spec.get('base_chance'),
        })

    unknown = icons.texture_of(UNKNOWN, models)
    art = textures.get(icons.split(unknown)) if unknown else None
    if art:
        save_icon(art, 'unknown.png')

    board.sort(key=lambda f: (f['mod'] != 'starcatcher', f['name']))
    with open(INDEX, 'w') as fh:
        json.dump(board, fh, indent=1)

    print(f'wrote {INDEX}')
    for fish in board:
        print(f'  {fish["id"]:<44} {fish["name"]:<28} {fish["icon"]}')
    print(f'\n{len(board)} catchable, {len(skipped)} left off:')
    for fish_id, why in skipped:
        print(f'  {fish_id:<44} {why}')
    if iconless:
        print(f'\nno flat icon for {len(iconless)}: {", ".join(iconless)}')


if __name__ == '__main__':
    main()
