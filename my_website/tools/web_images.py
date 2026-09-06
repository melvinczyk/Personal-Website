"""Make web-sized copies of the season screenshots.

Run from my_website/:
    python tools/web_images.py [season1 season2 ...] [--force]

The seasons folder is 1.3 GB of raw Minecraft screenshots, some of them
thirteen megabytes each, and the portal was putting the originals straight
into an <img> and a CSS background. One season's page came to fifteen
megabytes decoded, nearly all of it one screenshot behind the header.

So two derivatives per shot, both WebP, written beside the originals in a
_web folder:

  thumb  480px wide, for the masonry grid, where a tile is never more than a
         few hundred pixels across and the original was being scaled down to
         it by the browser after downloading all of it.
  view   1920px wide, for the hero behind the header and for the lightbox.

The originals are left exactly where they are. Nothing here deletes anything:
they are the archive, and a derivative that is wrong should be rebuildable
from them rather than being all that is left.
"""

import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), 'static', 'minecraft')
OUT = '_web'

# (folder, longest edge, quality). WebP at 82 is visually clean on screenshots
# and about a twentieth of the PNG.
SIZES = (('thumb', 480, 80), ('view', 1920, 82))
KINDS = ('.png', '.jpg', '.jpeg', '.webp')


def seasons():
    # season1, season2 ... and not "seasons", which is EclipticSeasons' own
    # art and has nothing to do with a season of the server
    return sorted(d for d in os.listdir(ROOT)
                  if d[:6] == 'season' and d[6:].isdigit()
                  and os.path.isdir(os.path.join(ROOT, d)))


def build(season, force=False):
    folder = os.path.join(ROOT, season)
    made = skipped = 0
    saved = 0
    # Every thumbnail's size, written out beside them. The gallery needs it
    # before the image arrives: the tiles are lazy-loaded and the grid is a
    # column layout, so without a declared size every tile collapses to a
    # couple of pixels - and once the whole column has collapsed the browser
    # never decides a lazy image is near the viewport, so none of them ever
    # load. A deadlock that looks exactly like a broken gallery.
    sizes = {}
    for name in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in KINDS or stem.startswith('logo'):
            continue
        source = os.path.join(folder, name)
        if not os.path.isfile(source):
            continue
        was = os.path.getsize(source)
        for kind, edge, quality in SIZES:
            out_dir = os.path.join(folder, OUT, kind)
            os.makedirs(out_dir, exist_ok=True)
            target = os.path.join(out_dir, f'{stem}.webp')
            # a derivative older than its source is a stale derivative
            if (not force and os.path.exists(target)
                    and os.path.getmtime(target) >= os.path.getmtime(source)):
                skipped += 1
                continue
            try:
                with Image.open(source) as art:
                    art = art.convert('RGB')
                    art.thumbnail((edge, edge), Image.LANCZOS)
                    art.save(target, 'WEBP', quality=quality, method=4)
                    if kind == 'thumb':
                        sizes[stem] = list(art.size)
            except Exception as exc:                  # noqa: BLE001
                print(f'  {name}: {type(exc).__name__} {exc}')
                continue
            made += 1
            if kind == 'view':
                saved += was - os.path.getsize(target)

    # a skipped file still has to be in the table, so anything already built
    # is measured off the file rather than left out
    web = os.path.join(folder, OUT)
    if os.path.isdir(os.path.join(web, 'thumb')):
        for thumb in sorted(os.listdir(os.path.join(web, 'thumb'))):
            stem = os.path.splitext(thumb)[0]
            if stem in sizes:
                continue
            try:
                with Image.open(os.path.join(web, 'thumb', thumb)) as art:
                    sizes[stem] = list(art.size)
            except Exception:                         # noqa: BLE001
                pass
        with open(os.path.join(web, 'sizes.json'), 'w') as fh:
            json.dump(sizes, fh, separators=(',', ':'))
    return made, skipped, saved


def main(which, force=False):
    total = 0
    for season in which or seasons():
        made, skipped, saved = build(season, force)
        total += saved
        print(f'{season}: {made} written, {skipped} already current, '
              f'{saved / 1048576:.0f} MB lighter at view size')
    print(f'{total / 1048576:.0f} MB saved across every season')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    main(args, '--force' in sys.argv)
