"""
Loads and indexes all song2vec data once at process start.
Keeps everything in memory so search/render requests are fast.
"""

import csv
import json
import colorsys
import io
import math
import os
import threading

import numpy as np
from PIL import Image
from sklearn.decomposition import PCA

_lock   = threading.Lock()
_loaded = False

# Public globals filled by _load()
SONGS      = {}   # spotify_id → {name, artist, genres: set, tags: [(tag, pop)]}
SONG_INDEX = []   # list of (lower_name, lower_artist, spotify_id) for search

genres_list  = []
tags_list    = []
G_norm       = None
T_norm       = None
genre2idx    = {}
tag2idx      = {}
pca_g_color  = None
pca_t_color  = None
pca_g_layout = None
pca_t_layout = None

COLOR_OVERRIDES = {
    "metal":(120,10,10),"death metal":(80,10,20),"black metal":(25,15,35),
    "thrash metal":(140,20,20),"doom metal":(50,20,40),"grindcore":(110,10,30),
    "hardcore":(160,20,20),"punk":(180,20,40),"grunge":(90,60,30),"emo":(70,30,60),
    "goth":(40,20,60),"industrial":(60,60,70),"darkwave":(50,30,80),
    "rap":(50,50,60),"hip hop":(70,60,90),"trap":(80,30,100),
    "folk":(140,180,70),"country":(200,140,60),"acoustic":(200,170,110),
    "blues":(40,80,180),"pop":(255,100,180),"dance pop":(255,80,200),
    "edm":(50,220,220),"house":(120,60,230),"tropical house":(255,200,80),
    "reggaeton":(255,80,60),"classical":(220,220,250),"ambient":(80,140,200),
    "chillout":(120,200,220),"jazz":(180,130,50),"soul":(180,80,40),
    "funk":(220,140,50),"r&b":(150,40,110),"rock":(180,60,60),
    "classic rock":(200,90,50),"shoegaze":(140,120,200),
    "melancholic":(60,80,140),"dark":(25,20,40),"happy":(255,220,80),
    "sad":(70,90,150),"chill":(120,200,220),"aggressive":(200,30,30),
    "energetic":(255,120,40),"romantic":(220,100,150),"atmospheric":(120,140,180),
    "upbeat":(255,180,80),"heavy":(50,40,50),"nostalgic":(180,140,100),
    "dreamy":(180,180,240),"epic":(80,50,130),
}

DATA_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                         'Desktop', 'CS_CLASS', 'CS665sp26', 'Musical-Blob', 'data')
DATA_ROOT = os.path.normpath(os.path.expanduser(
    '~/Desktop/CS_CLASS/CS665sp26/Musical-Blob/data'))


def _read_csv(path):
    rows = []
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f, delimiter=';')
        raw_header = next(reader)[0]
        headers = [h.strip().strip('"') for h in raw_header.split(',')]
        for row in reader:
            if len(row) == len(headers):
                rows.append(dict(zip(headers, [p.strip().strip('"') for p in row])))
    return rows


def _load():
    global _loaded, SONGS, SONG_INDEX
    global genres_list, tags_list, G_norm, T_norm, genre2idx, tag2idx
    global pca_g_color, pca_t_color, pca_g_layout, pca_t_layout

    with _lock:
        if _loaded:
            return

        # ── Songs ──────────────────────────────────────────────────────
        for row in _read_csv(os.path.join(DATA_ROOT, 'csv', 'songs.csv')):
            sid = row['spotify_id']
            if sid not in SONGS:
                SONGS[sid] = {'name': row['name'], 'artist': row['artist'],
                              'genres': set(), 'tags': []}
            SONGS[sid]['genres'].add(row['genre_name'])

        # ── Tags ───────────────────────────────────────────────────────
        for row in _read_csv(os.path.join(DATA_ROOT, 'csv', 'tags.csv')):
            sid = row['song_spotify_id']
            if sid in SONGS:
                SONGS[sid]['tags'].append((row['tag'], int(row['popularity'] or 0)))

        # Deduplicate + sort tags by popularity desc
        for sid in SONGS:
            seen = set()
            deduped = []
            for tag, pop in sorted(SONGS[sid]['tags'], key=lambda x: -x[1]):
                if tag not in seen:
                    seen.add(tag)
                    deduped.append((tag, pop))
            SONGS[sid]['tags'] = deduped[:12]   # keep top 12

        # ── Search index ────────────────────────────────────────────────
        SONG_INDEX = [
            (s['name'].lower(), s['artist'].lower(), sid)
            for sid, s in SONGS.items()
        ]

        # ── Embeddings + PCA ────────────────────────────────────────────
        with open(os.path.join(DATA_ROOT, 'embeddings', 'genre_embeddings.json')) as f:
            genre_raw = json.load(f)
        with open(os.path.join(DATA_ROOT, 'embeddings', 'tag_embeddings.json')) as f:
            tag_raw = json.load(f)

        genres_list = list(genre_raw.keys())
        tags_list   = list(tag_raw.keys())
        genre2idx   = {g: i for i, g in enumerate(genres_list)}
        tag2idx     = {t: i for i, t in enumerate(tags_list)}

        G = np.array(list(genre_raw.values()), dtype=np.float32)
        T = np.array(list(tag_raw.values()),   dtype=np.float32)
        G_norm = G / (np.linalg.norm(G, axis=1, keepdims=True) + 1e-9)
        T_norm = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)

        pca_g_color  = PCA(n_components=3).fit(G_norm)
        pca_t_color  = PCA(n_components=3).fit(T_norm)
        pca_g_layout = PCA(n_components=2).fit(G_norm)
        pca_t_layout = PCA(n_components=2).fit(T_norm)

        _loaded = True


# ── Colour helpers ─────────────────────────────────────────────────────────────

def _vec_to_rgb(vec, pca, temp=3.0, hue_offset=0.15):
    p = np.tanh(pca.transform(vec.reshape(1, -1))[0] * temp)
    h = (math.atan2(float(p[1]), float(p[0])) / (2 * math.pi) + 0.5 + hue_offset) % 1.0
    s = float(np.clip(math.sqrt(float(p[0])**2 + float(p[1])**2) * 0.5 + 0.5, 0.5, 1.0))
    v = float(np.clip((float(p[2]) + 1) / 2, 0.2, 1.0))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (r * 255, g * 255, b * 255)


def _vec_to_xy(vec, pca, padding):
    p   = pca.transform(vec.reshape(1, -1))[0]
    p_t = np.tanh(p * 0.6)
    x   = float((p_t[0] + 1) / 2 * (1 - 2 * padding) + padding)
    y   = float((p_t[1] + 1) / 2 * (1 - 2 * padding) + padding)
    return x, y


def get_genre_color(name):
    n = name.lower()
    if n in COLOR_OVERRIDES:
        return tuple(float(c) for c in COLOR_OVERRIDES[n])
    if n in genre2idx:
        return _vec_to_rgb(G_norm[genre2idx[n]], pca_g_color)
    return None


def get_tag_color(name):
    n = name.lower()
    if n in COLOR_OVERRIDES:
        return tuple(float(c) for c in COLOR_OVERRIDES[n])
    if n in tag2idx:
        return _vec_to_rgb(T_norm[tag2idx[n]], pca_t_color)
    return None


# ── Core render (exact match to visualization.ipynb render_blob) ───────────────

def render_blob(song_genres, song_tags, size=400):
    """
    song_genres: list of genre name strings
    song_tags:   list of (tag_name, popularity) tuples — top 8 used
    Returns: PIL Image (RGB)
    """
    _load()

    # Mirror synthesize(): top_g=5, top_t=8 by similarity to the song's mean vec
    # Since we have the actual genres/tags directly, use them as-is with equal weight.
    syn_genres = [(g, 1.0) for g in song_genres if g in genre2idx][:5]
    syn_tags   = [(t, 1.0) for t, _ in song_tags  if t in tag2idx ][:8]

    canvas = np.zeros((size, size, 3), dtype=np.float32)
    y_grid, x_grid = np.mgrid[0:size, 0:size]

    n_g, n_t   = len(syn_genres), len(syn_tags)
    genre_base = size * (0.20 + 0.10 / max(n_g, 1))
    tag_base   = size * (0.12 + 0.06 / max(n_t, 1))

    g_max = max((s for _, s in syn_genres), default=0) or 1.0
    for name, sim in syn_genres:
        color = get_genre_color(name)
        if color is None:
            continue
        color = np.array(color, dtype=np.float32)
        x, y   = _vec_to_xy(G_norm[genre2idx[name]], pca_g_layout, padding=0.22)
        x, y   = x * size, y * size
        weight = max(sim / g_max, 0.3)
        dist   = np.sqrt((x_grid - x) ** 2 + (y_grid - y) ** 2)
        mask   = np.clip(1 - dist / (genre_base * weight), 0, 1) ** 2
        canvas += color[None, None, :] * mask[..., None] * 0.04 * weight

    t_max = max((s for _, s in syn_tags), default=0) or 1.0
    for name, sim in syn_tags:
        color = get_tag_color(name)
        if color is None:
            continue
        color = np.array(color, dtype=np.float32)
        x, y   = _vec_to_xy(T_norm[tag2idx[name]], pca_t_layout, padding=0.15)
        x, y   = x * size, y * size
        weight = max(sim / t_max, 0.3)
        dist   = np.sqrt((x_grid - x) ** 2 + (y_grid - y) ** 2)
        mask   = np.clip(1 - dist / (tag_base * weight), 0, 1) ** 2
        canvas += color[None, None, :] * mask[..., None] * 0.04 * weight

    canvas = np.clip(canvas, 0, 1)
    mx = canvas.max(-1); mn = canvas.min(-1)
    L  = (mx + mn) / 2
    scale  = np.where(L > 0, np.minimum(L, 0.78) / (L + 1e-9), 1.0)
    canvas = canvas * scale[..., None]
    canvas = np.power(canvas, 0.85)
    canvas = (np.clip(canvas, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(canvas, 'RGB')
