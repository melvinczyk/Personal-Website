import os
from datetime import datetime
from django.shortcuts import render
from django.conf import settings

# Edit season descriptions here
SEASON_DESCRIPTIONS = {
    1: "Groid Pack season 1 - the first modpack",
    2: "Groid Pack season 2 - spells and dragons ",
    3: "Groid Pack season 3 PART 1 - guns and machinery",
    4: "Groid Pack Seven Seas - pirates PvP",
}

SEASON_NAMES = {
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

        seasons.append({
            'number':           season_num,
            'name':             SEASON_NAMES.get(season_num, f'SEASON {season_num}'),
            'description':      SEASON_DESCRIPTIONS.get(season_num, f'Season {season_num}.'),
            'has_logo':         has_logo,
            'logo_file':        logo_file,
            'screenshots':      screenshots,
            'videos':           videos,
            'screenshot_count': len(screenshots),
            'video_count':      len(videos),
        })

    return render(request, 'gallery.html', {'seasons': seasons})