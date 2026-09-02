"""Pull EclipticSeasons' own art and colour tables out of the mod jar.

Run from my_website/:
    python tools/extract_season_textures.py ["<path to a mods folder>"]

The pack's seasons are EclipticSeasons: twenty-four solar terms, two to a
sub-season, twelve sub-seasons to a year. The board draws all of that, so it
should draw it in the mod's own art rather than in shapes invented here:

  * the twenty-four solar term icons, cut out of the mod's own
    font/seasons_icons.png atlas - six columns by four rows, one row per
    season, in the same order the mod lists them;
  * the particles it actually spawns in each season - blossom and butterflies
    in spring, fireflies in summer, falling leaves and geese in autumn, and
    the snow and rain overlays it draws over the world;
  * the ground cover its own grass_block season definition swaps in - flowers
    through spring, four-leaf clovers through summer, snow over winter.

It also prints the mod's per-solar-term grass and leaf tints, read straight
out of TemperateSolarTermColors' bytecode rather than guessed at, so the
scenery on the board greens up and browns off on the same schedule the world
itself does. See the SOLAR_TINTS table this writes into the icons folder.
"""
import io
import json
import os
import struct
import sys
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'seasons')

MODS = [os.path.expanduser(p) for p in (
    '~/curseforge/minecraft/Instances/Groid Pack OG/mods',
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG/mods',
)]

A = 'assets/eclipticseasons/textures/'

# One row of the atlas per season, six terms across - the same i/j the mod's
# own season_phase jsons carry, so index = j * 6 + i is the solar term ordinal
ICON_ATLAS = A + 'font/seasons_icons.png'
ICON_COLS, ICON_ROWS = 6, 4

# What the mod spawns in the air, season by season. Named here the way the
# board uses them rather than the way the mod files them.
PARTICLES = {
    'blossom':   [A + f'particle/flying_bloom/bloom_{i}.png' for i in range(8)],
    'butterfly': [A + f'particle/butterfly{i}.png' for i in (1, 2, 3)],
    'firefly':   [A + 'particle/firefly.png', A + 'particle/firefly2.png'],
    'leaf':      [A + f'particle/fallen_leaves/leaf_{i}.png' for i in range(16)],
    'goose':     [A + 'particle/wild_goose.png'] +
                 [A + f'particle/wild_goose{i}.png' for i in (2, 3, 4, 5)],
}

# The weather the mod draws over the world, and the cover it lays on the
# ground - flowers in spring, clovers in summer, snow over winter.
SINGLES = {
    'rain_thin.png':    A + 'environment/thin_rain.png',
    'rain_middle.png':  A + 'environment/middle_rain.png',
    'snow_thin.png':    A + 'environment/thin_snow.png',
    'snow_middle.png':  A + 'environment/middle_snow.png',
    'snow_grass.png':   A + 'block/snowy_grass.png',
    'snow_overlay.png': A + 'block/snow_overlay.png',
    'snow_leaves.png':  A + 'block/snow_overlay_leaves.png',
}
SINGLES.update({f'flower_{i}.png': A + f'block/flower_{i}.png'
                for i in range(1, 7)})
SINGLES.update({f'clover_{i}.png':
                A + f'block/fourleaf_clover/fourleaf_clover_{i}.png'
                for i in range(7)})

# TemperateSolarTermColors' own enum, in ordinal order - the class this reads
# the tints out of. Kept here so a rename in the mod fails loudly rather than
# writing a table of the wrong colours.
COLOR_CLASS = ('com/teamtea/eclipticseasons/api/constant/solar/color/'
               'base/TemperateSolarTermColors.class')

# vanilla's plains grass and foliage, the colour the world already is before
# a solar term tints it - the mod mixes its own tint over this
BASE_GRASS   = 0x91BD59
BASE_FOLIAGE = 0x77AB2F

TERMS = (
    'beginning_of_spring', 'rain_water', 'insects_awakening',
    'spring_equinox', 'fresh_green', 'grain_rain',
    'beginning_of_summer', 'lesser_fullness', 'grain_in_ear',
    'summer_solstice', 'lesser_heat', 'greater_heat',
    'beginning_of_autumn', 'end_of_heat', 'white_dew',
    'autumnal_equinox', 'cold_dew', 'first_frost',
    'beginning_of_winter', 'light_snow', 'heavy_snow',
    'winter_solstice', 'lesser_cold', 'greater_cold',
)

# ── the mod's own colour maths ──────────────────────────────────────────────
# ColorHelper.simplyMixColor(c1, f1, c2, f2) is a straight per-channel
# weighted sum, not a normalised blend - c1 * f1 + c2 * f2, clamped by the
# byte it lands in. Reproduced rather than approximated so the table below is
# the same one the game is drawing with.


def mix(c1, f1, c2, f2):
    out = 0
    for shift in (16, 8, 0):
        v = int((c1 >> shift & 0xFF) * f1 + (c2 >> shift & 0xFF) * f2)
        out |= max(0, min(255, v)) << shift
    return out


# ── just enough of a class file to read an enum's constructor arguments ─────
_OPLEN = {op: 0 for op in range(256)}
_OPLEN.update({
    0x10: 1, 0x11: 2, 0x12: 1, 0x13: 2, 0x14: 2, 0x15: 1, 0x16: 1, 0x17: 1,
    0x18: 1, 0x19: 1, 0x36: 1, 0x37: 1, 0x38: 1, 0x39: 1, 0x3a: 1, 0x84: 2,
    0x99: 2, 0x9a: 2, 0x9b: 2, 0x9c: 2, 0x9d: 2, 0x9e: 2, 0x9f: 2, 0xa0: 2,
    0xa1: 2, 0xa2: 2, 0xa3: 2, 0xa4: 2, 0xa5: 2, 0xa6: 2, 0xa7: 2, 0xa8: 2,
    0xa9: 1, 0xb2: 2, 0xb3: 2, 0xb4: 2, 0xb5: 2, 0xb6: 2, 0xb7: 2, 0xb8: 2,
    0xb9: 4, 0xba: 4, 0xbb: 2, 0xbc: 1, 0xbd: 2, 0xc0: 2, 0xc1: 2, 0xc5: 3,
    0xc6: 2, 0xc7: 2, 0xc8: 4, 0xc9: 4,
})


def _pool(data):
    off, count, pool, i = 10, struct.unpack_from('>H', data, 8)[0], {}, 1
    while i < count:
        tag = data[off]; off += 1
        if tag == 1:
            ln = struct.unpack_from('>H', data, off)[0]; off += 2
            pool[i] = ('utf8', data[off:off + ln].decode('utf-8', 'replace'))
            off += ln
        elif tag == 3:
            pool[i] = ('int', struct.unpack_from('>i', data, off)[0]); off += 4
        elif tag == 4:
            pool[i] = ('float', struct.unpack_from('>f', data, off)[0]); off += 4
        elif tag in (5, 6):
            pool[i] = ('wide', None); off += 8; i += 1
        elif tag in (7, 8, 16, 19, 20):
            pool[i] = ('ref', struct.unpack_from('>H', data, off)[0]); off += 2
        elif tag == 15:
            pool[i] = ('mh', None); off += 3
        else:
            pool[i] = ('ref2', struct.unpack_from('>HH', data, off)); off += 4
        i += 1
    return pool, off


def _clinit(data, pool, off):
    """The static initialiser's bytecode - where an enum's constants are built."""
    off += 6                                  # access, this, super
    off += 2 + 2 * struct.unpack_from('>H', data, off)[0]   # interfaces
    for section in range(2):                  # fields, then methods
        n = struct.unpack_from('>H', data, off)[0]; off += 2
        for _ in range(n):
            off += 2
            name = pool[struct.unpack_from('>H', data, off)[0]][1]; off += 2
            off += 2
            na = struct.unpack_from('>H', data, off)[0]; off += 2
            for _ in range(na):
                an = pool[struct.unpack_from('>H', data, off)[0]][1]; off += 2
                ln = struct.unpack_from('>I', data, off)[0]; off += 4
                if section == 1 and name == '<clinit>' and an == 'Code':
                    clen = struct.unpack_from('>I', data, off + 4)[0]
                    return data[off + 8: off + 8 + clen]
                off += ln
    return None


def solar_tints(zf):
    """The mod's own grass and leaf tint per solar term, in ordinal order."""
    data = zf.read(COLOR_CLASS)
    pool, off = _pool(data)
    code = _clinit(data, pool, off)
    if not code:
        return []

    def words(index, depth=0):
        """Every utf8 a pool entry reaches - a methodref's class, name, type."""
        kind, value = pool.get(index, (None, None))
        if depth > 4:
            return []
        if kind == 'utf8':
            return [value]
        if kind == 'ref':
            return words(value, depth + 1)
        if kind == 'ref2':
            return words(value[0], depth + 1) + words(value[1], depth + 1)
        return []

    entries, stack = [], []
    i = 0
    while i < len(code):
        op = code[i]
        if op == 0xbb:                       # new - a fresh enum constant
            if stack:
                entries.append(stack)
            stack = []
        elif op == 0x12:
            stack.append(pool[code[i + 1]])
        elif op in (0x13, 0x14):
            stack.append(pool[struct.unpack_from('>H', code, i + 1)[0]])
        elif op == 0x10:
            stack.append(('int', struct.unpack_from('>b', code, i + 1)[0]))
        elif op == 0x11:
            stack.append(('int', struct.unpack_from('>h', code, i + 1)[0]))
        elif 0x02 <= op <= 0x08:
            stack.append(('int', op - 0x03))
        elif 0x0b <= op <= 0x0d:
            stack.append(('float', float(op - 0x0b)))
        elif op == 0xb8:                     # invokestatic
            call = struct.unpack_from('>H', code, i + 1)[0]
            # only the colour blend folds into a value here; the enum's own
            # $values()/values() calls at the end take no constants and would
            # eat the last entry's arguments off the stack if they were folded
            if 'simplyMixColor' in words(call) and len(stack) >= 4:
                args = stack[-4:]
                del stack[-4:]
                stack.append(('int', mix(args[0][1], args[1][1],
                                         args[2][1], args[3][1])))
        i += 1 + _OPLEN[op]
    if stack:
        entries.append(stack)

    out = []
    for row in entries[:len(TERMS)]:
        # (name, ordinal, grass, grassMix[, leaf, leafMix]) - the string name
        # and int ordinal come first and are dropped here
        nums = [v for kind, v in row if kind in ('int', 'float')]
        nums = nums[1:]                      # drop the ordinal
        if len(nums) < 2:
            continue
        grass, gmix = int(nums[0]), float(nums[1])
        leaf, lmix = (int(nums[2]), float(nums[3])) if len(nums) >= 4 \
            else (grass, gmix)
        out.append({
            'grass': f'#{mix(BASE_GRASS, 1 - gmix, grass, gmix):06x}',
            'leaf':  f'#{mix(BASE_FOLIAGE, 1 - lmix, leaf, lmix):06x}',
            'grass_mix': round(gmix, 3),
            'leaf_mix': round(lmix, 3),
        })
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
    folders = [f for f in sys.argv[1:] if os.path.isdir(f)] or MODS
    jar = (sys.argv[1] if sys.argv[1:] and sys.argv[1].endswith('.jar')
           else mod_jar(folders, 'eclipticseasons'))
    if not jar or not os.path.exists(jar):
        print('no EclipticSeasons jar found')
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    print('reading', os.path.basename(jar))

    with zipfile.ZipFile(jar) as zf:
        # the twenty-four solar term icons, one tile each
        atlas = read(zf, ICON_ATLAS)
        tw, th = atlas.width // ICON_COLS, atlas.height // ICON_ROWS
        for j in range(ICON_ROWS):
            for i in range(ICON_COLS):
                tile = atlas.crop((i * tw, j * th, (i + 1) * tw, (j + 1) * th))
                save(f'solar_{j * ICON_COLS + i:02d}.png', tile)

        for kind, entries in PARTICLES.items():
            for n, entry in enumerate(entries):
                try:
                    save(f'{kind}_{n}.png', read(zf, entry))
                except KeyError:
                    print('missing', entry)

        for name, entry in SINGLES.items():
            try:
                save(name, read(zf, entry))
            except KeyError:
                print('missing', entry)

        tints = solar_tints(zf)

    if tints:
        table = {TERMS[i]: t for i, t in enumerate(tints)}
        path = os.path.join(OUT_DIR, 'tints.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(table, fh, indent=1)
        print('wrote tints.json')
        for term, t in table.items():
            print(f'  {term:22} grass {t["grass"]}  leaf {t["leaf"]}')
    else:
        print('could not read the solar term colour table')


if __name__ == '__main__':
    main()
