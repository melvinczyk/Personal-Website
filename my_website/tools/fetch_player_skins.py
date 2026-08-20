"""Resolve every player UUID found in the season folders to a name and skin.

Run from my_website/:  python tools/fetch_player_skins.py [--force]

Skins are downloaded once and served from static/, so the portal never has to
call Mojang at request time (and never hits the browser's CORS wall). Re-run it
when new .dat files land or someone changes their skin.
"""

import base64
import json
import os
import sys
import urllib.request

HERE      = os.path.dirname(os.path.abspath(__file__))
STATIC    = os.path.join(os.path.dirname(HERE), 'static', 'minecraft')
SKIN_DIR  = os.path.join(STATIC, 'skins')
INDEX     = os.path.join(SKIN_DIR, 'players.json')
PROFILE   = 'https://sessionserver.mojang.com/session/minecraft/profile/{}'
UA        = {'User-Agent': 'nicholasburczyk.com minecraft-portal/1.0'}


def get(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def find_uuids():
    found = {}
    for season in sorted(os.listdir(STATIC)):
        stats = os.path.join(STATIC, season, 'stats')
        if not os.path.isdir(stats):
            continue
        for name in sorted(os.listdir(stats)):
            if name.endswith('.dat'):
                found.setdefault(os.path.splitext(name)[0], []).append(season)
    return found


def resolve(uuid):
    """Mojang wants the dashless form; textures arrive base64 inside a property."""
    profile = json.loads(get(PROFILE.format(uuid.replace('-', ''))))
    textures = {}
    for prop in profile.get('properties', []):
        if prop.get('name') == 'textures':
            textures = json.loads(base64.b64decode(prop['value']))['textures']
    skin = textures.get('SKIN', {})
    return {
        'name':  profile.get('name', uuid[:8]),
        'url':   skin.get('url'),
        # Mojang only sends metadata.model for slim arms; classic is the default
        'slim':  skin.get('metadata', {}).get('model') == 'slim',
    }


def main():
    force = '--force' in sys.argv
    os.makedirs(SKIN_DIR, exist_ok=True)
    index = {}
    if os.path.exists(INDEX):
        index = json.load(open(INDEX))

    uuids = find_uuids()
    if not uuids:
        print('no .dat files found under static/minecraft/*/stats/')
        return

    for uuid, seasons in uuids.items():
        if uuid in index and not force:
            # the profile is cached, but a player can turn up in a new season
            index[uuid]['seasons'] = seasons
            print(f'{uuid}  {index[uuid]["name"]:<18} cached   {", ".join(seasons)}')
            continue
        try:
            info = resolve(uuid)
        except Exception as exc:
            print(f'{uuid}  FAILED: {exc}')
            continue

        skin_file = f'{uuid}.png'
        if info['url']:
            with open(os.path.join(SKIN_DIR, skin_file), 'wb') as fh:
                fh.write(get(info['url']))
        else:
            skin_file = None

        index[uuid] = {
            'name':    info['name'],
            'slim':    info['slim'],
            'skin':    skin_file,
            'seasons': seasons,
        }
        arms = 'slim' if info['slim'] else 'classic'
        print(f'{uuid}  {info["name"]:<18} {arms:<8} {", ".join(seasons)}')

    with open(INDEX, 'w') as fh:
        json.dump(index, fh, indent=2, sort_keys=True)
    print(f'\nwrote {INDEX} ({len(index)} players)')


if __name__ == '__main__':
    main()
