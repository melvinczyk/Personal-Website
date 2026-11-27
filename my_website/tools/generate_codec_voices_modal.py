#!/usr/bin/env python3
"""Generate the codec voice lines on a Modal GPU (fastest path).

Usage:
    modal run tools/generate_codec_voices_modal.py                  # lines with no .m4a yet
    modal run tools/generate_codec_voices_modal.py --keys sk_memprobe,ot_brief   # redo these
    modal run tools/generate_codec_voices_modal.py --audit-only     # list clips heard as shouted

Shares line texts and the character references with generate_codec_voices.py.
Wav to m4a conversion happens locally via afconvert.

Every part of a line is rendered several times and the best take is kept. A
take is marked down when:
  - it does not sound like the character: a speaker-verification model
    (ECAPA) compares it with the reference clip, which catches the whispered
    and off-timbre takes;
  - it is spoken faster (or much slower) than the character speaks in the
    reference clip;
  - it runs straight through a comma: Whisper's word timings show no pause
    where the script has one;
  - it ends while still making sound (the clone sometimes stops on the last
    phoneme rather than after it, which plays as a clipped word);
  - one stretch of it is far louder than the rest (a shouted word), or the
    whole take is much louder than the other takes of the same words;
  - Whisper, listening to it, hears something other than the script, or
    hears it shouted (it writes those with "!" or in capitals).
Picking the quietest take, as an earlier version did, chose whispers.
The kept parts are then brought to one loudness, so a split line does not
jump in volume between sentences, and every clip ends on a short fade and a
beat of silence instead of on the last sample of speech.
"""
import subprocess
import sys
from pathlib import Path

import modal

app = modal.App("codec-voices")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch", "torchaudio", "qwen-tts", "soundfile", "speechbrain")
)

TAKES = 6            # renders per part; the best is kept
TARGET_RMS = 0.10    # loudness every part is brought to (voiced frames); matches the shipped set
LEAD_MS = 60         # silence kept in front of a clip
TAIL_MS = 350        # silence after it, so playback never stops on speech
FADE_MS = 25


@app.function(image=image, gpu="A10G", timeout=3600)
def generate(lines: dict, split_lines: dict, ref_bytes: bytes, ref_text: str) -> dict:
    import difflib
    import io
    import re
    import tempfile
    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    from qwen_tts import Qwen3TTSModel
    from speechbrain.inference.speaker import EncoderClassifier
    from transformers import pipeline

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(ref_bytes)
        ref_path = f.name

    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cuda", dtype=torch.bfloat16
    )
    prompt = model.create_voice_clone_prompt(ref_audio=ref_path, ref_text=ref_text)
    asr = pipeline("automatic-speech-recognition", model="openai/whisper-small.en", device=0)
    ecapa = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                           savedir="/tmp/ecapa", run_opts={"device": "cuda"})

    def voiceprint(wav, sr):
        t = torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32))
        if sr != 16000:
            t = torchaudio.functional.resample(t, sr, 16000)
        e = ecapa.encode_batch(t[None].cuda()).squeeze().float()
        return e / e.norm()

    def syllables(text):
        return sum(max(1, len(re.findall(r"[aeiouy]+", w))) for w in re.findall(r"[a-z']+", text.lower()))

    def synth(text):
        wavs, sr = model.generate_voice_clone(
            text=text, language="English", voice_clone_prompt=prompt
        )
        return np.asarray(wavs[0], dtype=np.float32), sr

    def frames(wav, sr, ms=20):
        hop = max(1, int(sr * ms / 1000))
        n = len(wav) // hop
        return np.sqrt((wav[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12), hop

    def trim(wav, sr):
        """Cut leading and trailing silence, keeping LEAD_MS in front."""
        rms, hop = frames(wav, sr)
        on = np.where(rms > rms.max() * 0.03)[0]
        if not len(on):
            return wav
        a = max(0, on[0] * hop - int(sr * LEAD_MS / 1000))
        b = min(len(wav), (on[-1] + 1) * hop)
        return wav[a:b]

    ref_wav, ref_sr = sf.read(ref_path, dtype="float32")
    if ref_wav.ndim > 1:
        ref_wav = ref_wav.mean(axis=1)
    ref_print = voiceprint(ref_wav, ref_sr)

    def pace(wav, sr, text):
        """Syllables per second of sound, pauses left out."""
        rms, hop = frames(wav, sr)
        voiced = (rms > rms.max() * 0.1).sum() * hop / sr
        return syllables(text) / max(voiced, 0.1)

    ref_pace = pace(ref_wav, ref_sr, ref_text)
    print(f"reference pace {ref_pace:.2f} syl/s", flush=True)

    def comma_gaps(chunks, text, wav, sr):
        """The pause in the audio at each comma of the script (None when the words don't line up).

        Whisper's word boundaries run edge to edge, so the pause is measured in
        the sound itself: the longest quiet stretch near the end of the word
        that carries the comma.
        """
        words = text.split()
        heard = [c for c in chunks if norm(c["text"]).strip()]
        if len(heard) != len(words):
            return None
        rms, hop = frames(wav, sr)
        voiced = rms[rms > rms.max() * 0.1]
        hush = (np.median(voiced) if len(voiced) else rms.max()) * 0.15
        step = hop / sr
        gaps = []
        for i, w in enumerate(words[:-1]):
            t = heard[i]["timestamp"][1]
            if not w.endswith(",") or t is None:
                continue
            a, b = max(0, int((t - 0.15) / step)), min(len(rms), int((t + 0.3) / step))
            run = longest = 0
            for v in rms[a:b]:
                run = run + 1 if v < hush else 0
                longest = max(longest, run)
            gaps.append(longest * step)
        return gaps

    def norm(s):
        return re.sub(r"[^a-z ]", "", s.lower().replace("-", ""))

    def score(raw, wav, sr, text):
        rms, _ = frames(wav, sr)
        voiced = rms[rms > rms.max() * 0.1]
        med = np.median(voiced) if len(voiced) else 1e-6
        # judged on the untrimmed render: a take that runs right up to its last
        # sample is a word cut off, one that trails into silence is whole
        raw_rms, _ = frames(raw, sr)
        end = raw_rms[-3:].mean() / med
        win = np.convolve(rms, np.ones(25) / 25, mode="valid") if len(rms) > 25 else rms
        loud = win.max() / med                            # one shouted stretch?
        out = asr({"raw": wav, "sampling_rate": sr}, return_timestamps="word")
        heard = out["text"].strip()
        sim = difflib.SequenceMatcher(None, norm(heard).replace(" ", ""), norm(text).replace(" ", "")).ratio()
        # Whisper writes a shouted line the way it hears it: with "!" or in capitals
        shout = heard.count("!") + (2 if len(heard) > 6 and heard == heard.upper() else 0)
        voice = float(voiceprint(wav, sr) @ ref_print)    # 1.0 = the reference speaker
        speed = pace(wav, sr, text) / ref_pace
        gaps = comma_gaps(out.get("chunks", []), text, wav, sr)
        rushed = sum(1 for g in gaps if g < 0.08) if gaps else 0
        s = (sim * 3 + voice * 6
             - max(0, end - 0.15) * 8 - max(0, loud - 1.8) * 2 - shout * 1.5
             - max(0, speed - 1.1) * 10 - max(0, 0.75 - speed) * 6 - rushed * 1.2)
        return s, med, voice, dict(sim=round(sim, 2), voice=round(voice, 2), speed=round(speed, 2),
                                   commas=None if gaps is None else [round(g, 2) for g in gaps],
                                   end=round(float(end), 2), loud=round(float(loud), 2), shout=shout, heard=heard)

    def best(text):
        takes = []
        for _ in range(TAKES):
            raw, sr = synth(text)
            wav = trim(raw, sr)
            s, med, voice, info = score(raw, wav, sr, text)
            takes.append([s, wav, sr, info, med, voice])
        # judged against the other takes of the same words: one well above the
        # typical level is shouted, one well off the closest voice has drifted
        typical = float(np.median([t[4] for t in takes]))
        closest = max(t[5] for t in takes)
        for t in takes:
            t[0] -= max(0, t[4] / typical - 1.3) * 4
            t[0] -= max(0, closest - t[5] - 0.04) * 20
        takes.sort(key=lambda t: t[0], reverse=True)
        s, wav, sr, info, _, _ = takes[0]
        print(f"    {info}  <- {text[:48]}", flush=True)
        return wav, sr

    def level(wav, sr):
        rms, _ = frames(wav, sr)
        voiced = rms[rms > rms.max() * 0.1]
        return wav * (TARGET_RMS / (np.median(voiced) if len(voiced) else TARGET_RMS))

    def finish(wav, sr):
        n = int(sr * FADE_MS / 1000)
        if len(wav) > n:
            wav = wav.copy()
            wav[-n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
        wav = np.concatenate([wav, np.zeros(int(sr * TAIL_MS / 1000), dtype=wav.dtype)])
        # soft knee above 0.9 rather than turning the whole clip down, so every
        # line keeps the same loudness
        a = np.abs(wav)
        return np.where(a > 0.9, np.sign(wav) * (0.9 + 0.08 * np.tanh((a - 0.9) / 0.08)), wav).astype(np.float32)

    out = {}
    for i, (key, text) in enumerate(lines.items(), 1):
        print(f"[{i}/{len(lines)}] {key}", flush=True)
        spec = split_lines.get(key) or {"parts": [text], "gap_ms": 0}
        chunks, sr = [], 24000
        for j, part in enumerate(spec["parts"]):
            wav, sr = best(part)
            if j:
                chunks.append(np.zeros(int(sr * spec["gap_ms"] / 1000), dtype=np.float32))
            chunks.append(level(wav, sr))
        wav = finish(np.concatenate(chunks), sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        out[key] = buf.getvalue()
    return out


@app.function(image=image, gpu="A10G", timeout=1800)
def transcribe(clips: dict) -> dict:
    """What Whisper hears in each finished clip, for --audit."""
    import io
    import soundfile as sf
    from transformers import pipeline

    asr = pipeline("automatic-speech-recognition", model="openai/whisper-small.en", device=0)
    ecapa = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                           savedir="/tmp/ecapa", run_opts={"device": "cuda"})

    def voiceprint(wav, sr):
        t = torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32))
        if sr != 16000:
            t = torchaudio.functional.resample(t, sr, 16000)
        e = ecapa.encode_batch(t[None].cuda()).squeeze().float()
        return e / e.norm()

    def syllables(text):
        return sum(max(1, len(re.findall(r"[aeiouy]+", w))) for w in re.findall(r"[a-z']+", text.lower()))
    out = {}
    for key, wav in clips.items():
        audio, sr = sf.read(io.BytesIO(wav), dtype="float32")
        out[key] = asr({"raw": audio, "sampling_rate": sr})["text"].strip()
    return out


def audit(dest, all_lines):
    """List every shipped clip Whisper hears as shouted ("!" or all capitals)."""
    import tempfile
    clips = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key in sorted(all_lines):
            m4a = dest / f"{key}.m4a"
            if not m4a.exists():
                continue
            wav = Path(tmp) / f"{key}.wav"
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(m4a), str(wav)],
                           check=True, capture_output=True)
            clips[key] = wav.read_bytes()
    heard = transcribe.remote(clips)
    flagged = [k for k, t in heard.items() if "!" in t or (len(t) > 6 and t == t.upper())]
    for k in sorted(heard):
        print(f"{'SHOUT ' if k in flagged else '      '}{k:28} {heard[k]}")
    print("flagged:", ",".join(sorted(flagged)) or "none")


@app.local_entrypoint()
def main(keys: str = "", audit_only: bool = False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generate_codec_voices import (
        DEST, LINES, REF_AUDIO, REF_TEXT, SPLIT_LINES,
        SNAKE_LINES, SNAKE_REF_AUDIO, SNAKE_REF_TEXT, SNAKE_SPLIT_LINES,
        OTACON_LINES, OTACON_REF_AUDIO, OTACON_REF_TEXT, OTACON_SPLIT_LINES,
    )

    redo = {k.strip() for k in keys.split(",") if k.strip()}
    DEST.mkdir(parents=True, exist_ok=True)
    voices = [
        ("colonel", LINES, SPLIT_LINES, REF_AUDIO, REF_TEXT),
        ("snake", SNAKE_LINES, SNAKE_SPLIT_LINES, SNAKE_REF_AUDIO, SNAKE_REF_TEXT),
        ("otacon", OTACON_LINES, OTACON_SPLIT_LINES, OTACON_REF_AUDIO, OTACON_REF_TEXT),
    ]
    known = set().union(*(v[1] for v in voices))
    if audit_only:
        return audit(DEST, known)
    if redo - known:
        sys.exit(f"no such line: {', '.join(sorted(redo - known))}")

    # one container per character, all three at once
    calls = []
    for name, lines, split_lines, ref_audio, ref_text in voices:
        todo = {k: v for k, v in lines.items()
                if k in redo or (not redo and not (DEST / f"{k}.m4a").exists())}
        print(f"{name}: {len(todo)}/{len(lines)} lines to generate")
        if todo:
            calls.append(generate.spawn(todo, split_lines, ref_audio.read_bytes(), ref_text))

    for call in calls:
        for key, wav in call.get().items():
            tmp = DEST / f"{key}.tmp.wav"
            tmp.write_bytes(wav)
            subprocess.run(
                ["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000",
                 str(tmp), str(DEST / f"{key}.m4a")],
                check=True, capture_output=True,
            )
            tmp.unlink()
            print(f"installed {key}.m4a")
    print("ALL DONE")
