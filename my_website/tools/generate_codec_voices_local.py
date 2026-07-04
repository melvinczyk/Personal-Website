#!/usr/bin/env python3
"""Generate the Colonel's codec voice lines locally with Qwen3-TTS (no quota, no token).

Requires: pip install qwen-tts soundfile  (plus torch; on Intel macs pin
numpy==1.26.4 / scipy==1.13.1 / numba==0.60.0 so torch 2.2.2 stays happy).
The 1.7B Base model (~3.4GB) is downloaded to the HF cache on first run.

Line texts and the Campbell reference are shared with generate_codec_voices.py.
Skips lines whose .m4a already exists, so it can be re-run after edits
(delete the stale .m4a of any line you changed first).
"""
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_codec_voices import DEST, LINES, REF_AUDIO, REF_TEXT  # noqa: E402

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def main():
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel

    DEST.mkdir(parents=True, exist_ok=True)
    todo = {k: v for k, v in LINES.items() if not (DEST / f"{k}.m4a").exists()}
    print(f"{len(todo)}/{len(LINES)} lines to generate", flush=True)
    if not todo:
        return 0

    t = time.time()
    model = Qwen3TTSModel.from_pretrained(MODEL, device_map="cpu", dtype=torch.float32)
    print(f"model loaded in {time.time()-t:.0f}s", flush=True)

    # reusable prompt: encode the reference once instead of per line
    prompt = model.create_voice_clone_prompt(ref_audio=str(REF_AUDIO), ref_text=REF_TEXT)

    done = 0
    for key, text in todo.items():
        t = time.time()
        wavs, sr = model.generate_voice_clone(
            text=text, language="English", voice_clone_prompt=prompt,
        )
        tmp = DEST / f"{key}.tmp.wav"
        sf.write(str(tmp), wavs[0], sr)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "49152",
                        str(tmp), str(DEST / f"{key}.m4a")], check=True, capture_output=True)
        tmp.unlink()
        done += 1
        print(f"[{done}/{len(todo)}] {key} ({time.time()-t:.0f}s)", flush=True)
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
