"""Pull the icons the world panel draws with out of the game's own files.

Run from my_website/:
    python tools/extract_world_icons.py ["<path to a mods folder>"]

Two sets, both lifted rather than drawn, so the board shows the same sky and
the same calendar the players see in game:

  sun / moon    vanilla's environment textures. The game draws these additively
                against the sky, so they ship with no alpha at all and a black
                surround - keyed out here, or the panel gets a black square.
  season        Serene Seasons' calendar, one face per sub-season, in the
                mod's own order: 00 is early spring and 11 is late winter.
"""

import io
import os
import sys
import zipfile

from PIL import Image

HERE    = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'icons')

VANILLA_JAR = os.path.expanduser(
    '~/Documents/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')
MODS = os.path.expanduser(
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG Server/mods')

SUN  = 'assets/minecraft/textures/environment/sun.png'
MOON = 'assets/minecraft/textures/environment/moon_phases.png'
CAL  = 'assets/sereneseasons/textures/item/calendar_%02d.png'

# the atlas is four across and two down, and the game reads a phase as
# (phase % 4, phase / 4) - full moon first, new moon at four
MOON_COLS = 4


def unblack(image):
    """Black is nothing here: the sky shows through wherever the texture is dark."""
    image = image.convert('RGB')
    out = Image.new('RGBA', image.size)
    pixels = image.load()
    keep = out.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = pixels[x, y]
            lit = max(r, g, b)
            if not lit:
                continue
            # hold the colour and let brightness be the opacity, which is what
            # additive blending was doing on the sky in the first place
            scale = 255 / lit
            keep[x, y] = (min(255, round(r * scale)), min(255, round(g * scale)),
                          min(255, round(b * scale)), lit)
    return out


def trim(image, floor=24):
    """The sun is a small disc in a wide, almost invisible halo.

    Left whole it draws as a few bright pixels lost in a 32 pixel square. Cut
    the field back to where the glow is actually visible and the disc reads at
    icon size, with enough halo left around it to still look like a sun.
    """
    solid = image.getchannel('A').point(lambda v: 255 if v >= floor else 0)
    box = solid.getbbox()
    if not box:
        return image
    left, top, right, bottom = box
    side = max(right - left, bottom - top)
    mid_x, mid_y = (left + right) / 2, (top + bottom) / 2
    return image.crop((round(mid_x - side / 2), round(mid_y - side / 2),
                       round(mid_x + side / 2), round(mid_y + side / 2)))


def read(jar, entry):
    with zipfile.ZipFile(jar) as zf:
        return Image.open(io.BytesIO(zf.read(entry)))


def seasons_jar(folder):
    for name in sorted(os.listdir(folder)):
        if name.lower().startswith('sereneseasons') and name.endswith('.jar'):
            return os.path.join(folder, name)
    return None


def main(folder):
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []

    if os.path.exists(VANILLA_JAR):
        sun = trim(unblack(read(VANILLA_JAR, SUN)))
        sun.save(os.path.join(OUT_DIR, 'sun.png'))
        written.append('sun.png')

        sheet = read(VANILLA_JAR, MOON)
        tile = sheet.width // MOON_COLS
        for phase in range(8):
            col, row = phase % MOON_COLS, phase // MOON_COLS
            face = sheet.crop((col * tile, row * tile,
                               col * tile + tile, row * tile + tile))
            unblack(face).save(os.path.join(OUT_DIR, f'moon_{phase}.png'))
            written.append(f'moon_{phase}.png')
    else:
        print(f'no vanilla jar at {VANILLA_JAR}, skipping sun and moon')

    jar = seasons_jar(folder) if os.path.isdir(folder) else None
    if jar:
        for sub in range(12):
            name = f'season_{sub:02d}.png'
            read(jar, CAL % sub).convert('RGBA').save(os.path.join(OUT_DIR, name))
            written.append(name)
    else:
        print(f'no Serene Seasons jar under {folder}, skipping the calendar')

    for name in written:
        print('wrote', name)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else MODS)
