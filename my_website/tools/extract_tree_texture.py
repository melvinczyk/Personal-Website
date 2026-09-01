"""Pull the block textures the world panel's background scenery is built out
of - the overworld tree and grass, and the Twilight Forest and Aether scenery
the forecast card rotates through beside it - straight off the game's own
jars.

Run from my_website/:
    python tools/extract_tree_texture.py ["<path to a mods folder>"]

These are ordinary block textures, not the additively-blended sky textures
extract_world_icons.py deals with - no unblacking needed, just a crop out of
the jar and onto disk.

Twilight Forest adds no grass block or dirt texture of its own - like
vanilla, it colours the same grayscale textures from a biome colormap at
render time. Rather than invent a colour, this reads the real one out of the
mod's own biome json: Spooky Forest's, data/twilightforest/worldgen/biome/
spooky_forest.json, grass_color 12865827 / foliage_color 16745729 - a real
burnt orange-red rather than a green filtered sideways or a purple that
happens to look "magic". The trunks are real distinct textures already and
need no tinting at all - dark_log, canopy_log and mangrove_log are three
different trees in the mod's own files, not one recoloured three times.
"""
import io
import os
import sys
import zipfile

from PIL import Image

HERE    = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'icons')

VANILLA_JAR = os.path.expanduser(
    '~/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')
MODS = [os.path.expanduser(p) for p in (
    '~/curseforge/minecraft/Instances/Groid Pack OG/mods',
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG/mods',
)]

VANILLA_TEXTURES = {
    'tree_log.png':      'assets/minecraft/textures/block/oak_log.png',
    'tree_leaves.png':   'assets/minecraft/textures/block/oak_leaves.png',
    'grass_top.png':     'assets/minecraft/textures/block/grass_block_top.png',
    'grass_side.png':    'assets/minecraft/textures/block/grass_block_side.png',
    'grass_blade.png':   'assets/minecraft/textures/block/grass.png',
    'dirt.png':          'assets/minecraft/textures/block/dirt.png',
    'flower_poppy.png':     'assets/minecraft/textures/block/poppy.png',
    'flower_dandelion.png': 'assets/minecraft/textures/block/dandelion.png',
    # grayscale, alpha-masked to just the fringe rows - composited over dirt
    # to build a grass side face in any tint, the way the game itself does it
    '_grass_overlay.png': 'assets/minecraft/textures/block/grass_block_side_overlay.png',
}

# Three real Twilight Forest trees, not one texture reused three times - the
# main one is Canopy, the mod's own giant hollow tree, which is the "huge
# tree" the reference screenshots are actually showing.
TWILIGHT_LOGS = {
    'twilight_log_canopy.png':   'assets/twilightforest/textures/block/canopy_log.png',
    'twilight_log_dark.png':     'assets/twilightforest/textures/block/dark_log.png',
    'twilight_log_mangrove.png': 'assets/twilightforest/textures/block/mangrove_log.png',
}

# The Aether's own grass and the holystone underneath it, plus the Golden
# Oak - one of the Aether's own trees, and gold before anything here tints
# it, which is the same colour the rest of this board already uses for the
# Aether. All ship with real colour baked in, unlike vanilla's grass, so none
# of it needs tinting.
AETHER_TEXTURES = {
    'aether_grass_top.png':   'assets/aether/textures/block/natural/aether_grass_block_top.png',
    'aether_grass_side.png':  'assets/aether/textures/block/natural/aether_grass_block_side.png',
    'holystone.png':          'assets/aether/textures/block/natural/holystone.png',
    'aether_tree_log.png':    'assets/aether/textures/block/natural/golden_oak_log.png',
    'aether_tree_leaves.png': 'assets/aether/textures/block/natural/golden_oak_leaves.png',
}

# Leaves, the grass block's top face and the grass plant sprite all ship
# grayscale and are tinted at render time from the biome's colormaps; this is
# the game's own fallback colour for the overworld, for when no colormap is
# loaded. Twilight Forest's own two below are Spooky Forest's real numbers.
FOLIAGE_TINT      = (72, 181, 24)
GRASS_TINT        = (127, 178, 56)
TWILIGHT_GRASS    = (196, 81, 35)     # spooky_forest.json grass_color 12865827
TWILIGHT_FOLIAGE  = (255, 133, 1)     # spooky_forest.json foliage_color 16745729


def tint(image, colour):
    """A grayscale texture, multiplied by the colour the game paints it."""
    image = image.convert('RGBA')
    a = image.split()[3]
    gray = image.convert('L')
    tinted = Image.merge('RGB', tuple(
        gray.point(lambda v, c=c: round(v / 255 * c)) for c in colour))
    tinted.putalpha(a)
    return tinted


def composite(base, overlay):
    """The overlay's tinted fringe, laid over the base - a grass side face."""
    out = base.convert('RGBA').copy()
    out.alpha_composite(overlay.convert('RGBA'))
    return out


def mod_jar(folders, prefix):
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.lower().startswith(prefix) and name.endswith('.jar'):
                return os.path.join(folder, name)
    return None


def read(zf, entry):
    return Image.open(io.BytesIO(zf.read(entry))).convert('RGBA')


def save(name, image):
    image.save(os.path.join(OUT_DIR, name))
    print('wrote', name, image.size)


def main():
    folders = ([f for f in sys.argv[1:] if os.path.isdir(f)] or MODS)
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.exists(VANILLA_JAR):
        print(f'no vanilla jar at {VANILLA_JAR}')
        return
    with zipfile.ZipFile(VANILLA_JAR) as zf:
        images = {name: read(zf, entry) for name, entry in VANILLA_TEXTURES.items()}

    overlay = images.pop('_grass_overlay.png')
    dirt = images['dirt.png']

    save('grass_top.png', tint(images['grass_top.png'], GRASS_TINT))
    save('grass_side.png', composite(dirt, tint(overlay, GRASS_TINT)))
    save('grass_blade.png', tint(images['grass_blade.png'], GRASS_TINT))
    save('tree_leaves.png', tint(images['tree_leaves.png'], FOLIAGE_TINT))
    for name in ('tree_log.png', 'dirt.png', 'flower_poppy.png', 'flower_dandelion.png'):
        save(name, images[name])

    # Twilight Forest: the same overlay-over-dirt trick, in Spooky Forest's
    # own colour, plus its own three trees. images[] still holds the raw,
    # untinted reads from above - tint() returns a new image rather than
    # mutating them, so they are reused here rather than re-read from the jar.
    save('twilight_grass_top.png', tint(images['grass_top.png'], TWILIGHT_GRASS))
    save('twilight_grass_side.png', composite(dirt, tint(overlay, TWILIGHT_GRASS)))
    save('twilight_grass_blade.png', tint(images['grass_blade.png'], TWILIGHT_GRASS))
    save('twilight_leaves.png', tint(images['tree_leaves.png'], TWILIGHT_FOLIAGE))

    twilight_jar = mod_jar(folders, 'twilightforest')
    if twilight_jar and os.path.exists(twilight_jar):
        with zipfile.ZipFile(twilight_jar) as zf:
            for name, entry in TWILIGHT_LOGS.items():
                save(name, read(zf, entry))
    else:
        print('no Twilight Forest jar found, skipping its logs')

    aether_jar = mod_jar(folders, 'aether-')
    if aether_jar and os.path.exists(aether_jar):
        with zipfile.ZipFile(aether_jar) as zf:
            for name, entry in AETHER_TEXTURES.items():
                save(name, read(zf, entry))
    else:
        print('no Aether jar found, skipping its scenery')


if __name__ == '__main__':
    main()
