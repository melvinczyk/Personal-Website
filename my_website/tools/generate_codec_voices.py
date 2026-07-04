#!/usr/bin/env python3
"""Generate the Colonel's codec voice lines via the Qwen3-TTS HF Space.

Usage:
    pip install gradio_client
    HF_TOKEN=hf_xxx python tools/generate_codec_voices.py   # token optional but avoids quota limits

Skips files that already exist, so it can be re-run until all lines are done.
Output: static/audio/codec/<key>.m4a  (played by the codec dialogue engine)
"""
import os, shutil, subprocess, sys, time
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "static" / "audio" / "codec"

# Voice clone reference: all seven real Campbell clips concatenated (tools/ref/).
REF_AUDIO = Path(__file__).resolve().parent / "ref" / "campbell_ref.wav"
REF_TEXT = ("Tomorrow, the president and his Russian counterpart are scheduled to sign the START-3 Accord. "
            "Get back to the control room, and use that key to re-input the power codes. Stop that launch! "
            "Right now your job is to stop Metal Gear. "
            "You've got to understand, I'm just the middleman in this operation. "
            "I'm sorry to have to lay it all in your lap, but you're all I've got. "
            "Hurry up and get to Metal Gear's underground base. "
            "Watch out for the steam, it's dangerous.")

# Spoken text uses phonetic respellings (Burcheck, Tie-tans, Sandeea) so the
# clone pronounces things right; the on-screen text keeps real spellings.
LINES = {
    "c0_l0": "Snake, this is Nick Burcheck. A software engineer who dabbles in audio, vision, and embedded systems. He's currently stationed at Sandia National Labs as a Titans software R and D intern.",
    "c0_l1": "Everything we've gathered on him is laid out on this codec. For specific information look through different channels, or open MEMORY for the full contact list.",
    "c1_l0": "His operation records. Twelve declassified projects on file.",
    "c1_l1": "Select a target below for the full briefing.",
    "c2_l0": "He also records as Zero Barbecue. A one-man operation.",
    "c2_l1": "First single's out now. Listen below.",
    "c3_l0": "A private Minecraft world: custom modpack, custom server.",
    "c3_l1": "We gathered enough information to make a 3D reconstruction. The map below is rendering live.",
    "c4_l0": "These are his direct channels. They're secure. Use them.",
}

# Lines assembled from separately generated parts with silence between them
# (a TTS can't be trusted to hold a beat). Generators that support it should
# prefer this over the flat LINES text for these keys.
SPLIT_LINES = {
    "c1_l0": {"parts": ["His operation records.", "Twelve declassified projects on file."], "gap_ms": 450},
    "c2_l1": {"parts": ["First single's out now.", "Listen below."], "gap_ms": 450},
    "c3_l1": {"parts": ["We gathered enough information to make a 3D reconstruction.",
                         "The map below is rendering live."], "gap_ms": 450},
    "c4_l0": {"parts": ["These are his direct channels.", "They're secure.", "Use them."], "gap_ms": 400},
}


def main():
    from gradio_client import Client, handle_file  # lazy: keep module importable without it
    DEST.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    client = Client("Qwen/Qwen3-TTS", hf_token=token) if token else Client("Qwen/Qwen3-TTS")
    done, failed = 0, []
    for key, text in LINES.items():
        out = DEST / f"{key}.m4a"
        if out.exists():
            done += 1
            continue
        try:
            t = time.time()
            audio, _status = client.predict(
                ref_audio=handle_file(str(REF_AUDIO)),
                ref_text=REF_TEXT,
                target_text=text,
                language="English",
                use_xvector_only=False,
                model_size="1.7B",
                api_name="/generate_voice_clone",
            )
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "49152",
                            audio, str(out)], check=True, capture_output=True)
            done += 1
            print(f"[{done}/{len(LINES)}] {key} ({time.time()-t:.0f}s)", flush=True)
            time.sleep(2)
        except Exception as e:  # quota errors etc: re-run later, existing files are kept
            failed.append(key)
            print(f"FAIL {key}: {type(e).__name__} {str(e)[:140]}", flush=True)
            time.sleep(5)
    print(f"done={done}/{len(LINES)} failed={failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
