#!/usr/bin/env python3
"""Generate the Colonel's codec voice lines on a Modal GPU (fastest path).

Usage:
    modal run tools/generate_codec_voices_modal.py

Shares line texts and the Campbell reference with generate_codec_voices.py.
Skips lines whose .m4a already exists locally; wav conversion to m4a happens
locally via afconvert. A run of all 21 lines takes a few minutes end to end.
"""
import subprocess
import sys
from pathlib import Path

import modal

app = modal.App("codec-voices")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch", "qwen-tts", "soundfile")
)


@app.function(image=image, gpu="A10G", timeout=1800)
def generate(lines: dict, split_lines: dict, ref_bytes: bytes, ref_text: str) -> dict:
    import io
    import tempfile
    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(ref_bytes)
        ref_path = f.name

    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cuda", dtype=torch.bfloat16
    )
    prompt = model.create_voice_clone_prompt(ref_audio=ref_path, ref_text=ref_text)

    def synth(text):
        wavs, sr = model.generate_voice_clone(
            text=text, language="English", voice_clone_prompt=prompt
        )
        return np.asarray(wavs[0]), sr

    out = {}
    for i, (key, text) in enumerate(lines.items(), 1):
        if key in split_lines:
            # render parts separately and stitch with silence between them
            spec = split_lines[key]
            chunks, sr = [], 24000
            for j, part in enumerate(spec["parts"]):
                wav, sr = synth(part)
                if j:
                    chunks.append(np.zeros(int(sr * spec["gap_ms"] / 1000), dtype=wav.dtype))
                chunks.append(wav)
            wav = np.concatenate(chunks)
        else:
            wav, sr = synth(text)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        out[key] = buf.getvalue()
        print(f"[{i}/{len(lines)}] {key}", flush=True)
    return out


@app.local_entrypoint()
def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generate_codec_voices import (
        DEST, LINES, REF_AUDIO, REF_TEXT, SPLIT_LINES,
        SNAKE_LINES, SNAKE_REF_AUDIO, SNAKE_REF_TEXT, SNAKE_SPLIT_LINES,
        OTACON_LINES, OTACON_REF_AUDIO, OTACON_REF_TEXT, OTACON_SPLIT_LINES,
    )

    DEST.mkdir(parents=True, exist_ok=True)
    voices = [
        ("colonel", LINES, SPLIT_LINES, REF_AUDIO, REF_TEXT),
        ("snake", SNAKE_LINES, SNAKE_SPLIT_LINES, SNAKE_REF_AUDIO, SNAKE_REF_TEXT),
        ("otacon", OTACON_LINES, OTACON_SPLIT_LINES, OTACON_REF_AUDIO, OTACON_REF_TEXT),
    ]
    for name, lines, split_lines, ref_audio, ref_text in voices:
        todo = {k: v for k, v in lines.items() if not (DEST / f"{k}.m4a").exists()}
        print(f"{name}: {len(todo)}/{len(lines)} lines to generate")
        if not todo:
            continue

        results = generate.remote(todo, split_lines, ref_audio.read_bytes(), ref_text)

        for key, wav in results.items():
            tmp = DEST / f"{key}.tmp.wav"
            tmp.write_bytes(wav)
            subprocess.run(
                ["afconvert", "-f", "m4af", "-d", "aac", "-b", "49152",
                 str(tmp), str(DEST / f"{key}.m4a")],
                check=True, capture_output=True,
            )
            tmp.unlink()
            print(f"installed {key}.m4a")
    print("ALL DONE")
