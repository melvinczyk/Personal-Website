import os
from datetime import datetime
from django.shortcuts import render
from django.conf import settings

# Edit season descriptions here
SEASON_DESCRIPTIONS = {
    1: "Groid Pack season 1 - The First Modpack",
    2: "Groid Pack season 2 - Spells and Dragons",
    3: "Groid Pack season 3 PART 1 - Guns and Factories",
    4: "Groid Pack Seven Seas - Pirates PvP",
}

# Screenshot used as the backdrop behind each disc on the gallery screen.
# Picked for legibility; falls back to a mid-list screenshot if missing.
SEASON_HEROES = {
    1: "2023-09-06_23.01.52.png",
    2: "2024-09-03_22.17.13.png",
    3: "2025-03-29_00.52.26.png",
    4: "2026-01-29_23.46.27.png",
}

SEASON_NAMES = {
    2: "SEASON 2 - Spells and Dragons",
    3: "SEASON 3 (PART 1)",
    4: "SEVEN SEAS",
}

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.webm', '.mov'}


def parse_screenshot_date(filename):
    name = os.path.splitext(filename)[0]
    try:
        return datetime.strptime(name, "%Y-%m-%d_%H.%M.%S")
    except ValueError:
        return datetime.min


def gallery(request):
    minecraft_root = os.path.join(settings.STATICFILES_DIRS[0], 'minecraft')

    seasons = []

    if not os.path.isdir(minecraft_root):
        return render(request, 'gallery.html', {'seasons': seasons})

    season_dirs = sorted(
        [d for d in os.listdir(minecraft_root)
         if d.startswith('season') and os.path.isdir(os.path.join(minecraft_root, d))],
        key=lambda d: int(''.join(filter(str.isdigit, d)) or '0')
    )

    for season_dir in season_dirs:
        digits = ''.join(filter(str.isdigit, season_dir))
        if not digits:
            continue
        season_num  = int(digits)
        season_path = os.path.join(minecraft_root, season_dir)
        url_prefix  = f'/static/minecraft/{season_dir}'

        logo_file = next(
            (f for f in ('logo.gif', 'logo.png', 'logo.jpg', 'logo.webp')
             if os.path.isfile(os.path.join(season_path, f))),
            None
        )
        has_logo  = logo_file is not None
        screenshots = []
        videos      = []

        for filename in os.listdir(season_path):
            if filename in ('logo.png',):
                continue
            ext = os.path.splitext(filename)[1].lower()
            url = f'{url_prefix}/{filename}'

            if ext in IMAGE_EXTS:
                screenshots.append({
                    'filename': filename,
                    'url':      url,
                    'label':    filename,
                    'date':     parse_screenshot_date(filename),
                })
            elif ext in VIDEO_EXTS:
                videos.append({
                    'filename': filename,
                    'url':      url,
                    'label':    filename,
                })

        screenshots.sort(key=lambda x: x['date'])

        hero_name = SEASON_HEROES.get(season_num)
        hero = next((x['url'] for x in screenshots if x['filename'] == hero_name), None)
        if hero is None and screenshots:
            hero = screenshots[len(screenshots) // 2]['url']

        seasons.append({
            'number':           season_num,
            'name':             SEASON_NAMES.get(season_num, f'SEASON {season_num}'),
            'description':      SEASON_DESCRIPTIONS.get(season_num, f'Season {season_num}.'),
            'has_logo':         has_logo,
            'logo_file':        logo_file,
            'screenshots':      screenshots,
            'videos':           videos,
            'hero':             hero,
            'screenshot_count': len(screenshots),
            'video_count':      len(videos),
        })

    return render(request, 'gallery.html', {'seasons': seasons})