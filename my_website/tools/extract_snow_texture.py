"""Pull the one texture winter's ground needs: a grass block already capped
with snow, straight off the vanilla jar.

Run from my_website/:
    python tools/extract_snow_texture.py

A separate small script rather than folded into extract_tree_texture.py,
which already has its hands full building the overworld/Twilight
Forest/Aether scenery - this is the one asset winter alone needs, and it
ships with real colour baked in already, so there is no tinting step at all.
"""
import io
import os
import zipfile

from PIL import Image

HERE    = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'icons')

VANILLA_JAR = os.path.expanduser(
    '~/curseforge/minecraft/Install/versions/1.20.1/1.20.1.jar')

TEXTURE = 'assets/minecraft/textures/block/grass_block_snow.png'
OUT_NAME = 'grass_snow_side.png'


def main():
    if not os.path.exists(VANILLA_JAR):
        print(f'no vanilla jar at {VANILLA_JAR}')
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    with zipfile.ZipFile(VANILLA_JAR) as zf:
        image = Image.open(io.BytesIO(zf.read(TEXTURE))).convert('RGBA')
    image.save(os.path.join(OUT_DIR, OUT_NAME))
    print('wrote', OUT_NAME, image.size)


if __name__ == '__main__':
    main()
