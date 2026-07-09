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
    "c1_l1": "For the details, get Ottacon on the line. Hal's been cataloguing all of it.",
    "c1_l2": "He's already listening.",
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
    "c1_l1": {"parts": ["For the details, get Ottacon on the line.",
                         "Hal's been cataloguing all of it."], "gap_ms": 420},
    "c2_l0": {"parts": ["He also records as Zero Barbecue.", "A one-man operation."], "gap_ms": 420},
    "c2_l1": {"parts": ["First single's out now.", "Listen below."], "gap_ms": 450},
    "c3_l1": {"parts": ["We gathered enough information to make a 3D reconstruction.",
                         "The map below is rendering live."], "gap_ms": 450},
    "c4_l0": {"parts": ["These are his direct channels.", "They're secure.", "Use them."], "gap_ms": 400},
}


# ── Snake (right portrait) ──
# Voice clone reference: all four real Snake clips concatenated (tools/ref/).
SNAKE_REF_AUDIO = Path(__file__).resolve().parent / "ref" / "snake_ref.wav"
SNAKE_REF_TEXT = ("Everyone decides their own fate, no matter where they were born. "
                  "He looks and smells like he's been dead for days. "
                  "I am relaxed. I just don't know how to kill time here. "
                  "Please, talk to me.")

# One shared "Hmmm..." grunt reused for every project click (the project name
# is shown as on-screen text, not spoken), plus his intro replies and the
# contact-channel reply.
SNAKE_LINES = {
    "snake_hmm": "Hmmm...",
    "snake_hal": "Hal Emmerick. Been a while since Shadow Moses. Patch him in.",
    "snake_look": "Alright. Let's take a look, then.",
    "c4_l1": "Got it. I'll make contact.",
}

SNAKE_SPLIT_LINES = {
    "snake_hal": {"parts": ["Hal Emmerick.", "Been a while since Shadow Moses.",
                             "Patch him in."], "gap_ms": 380},
    "snake_look": {"parts": ["Alright.", "Let's take a look, then."], "gap_ms": 380},
    "c4_l1": {"parts": ["Got it.", "I'll make contact."], "gap_ms": 380},
}

# ── Otacon (Hal Emmerich, left portrait on the PROJECTS channel) ──
OTACON_REF_AUDIO = Path(__file__).resolve().parent / "ref" / "otacon_ref.wav"
OTACON_REF_TEXT = ("About the elevator that I checked out. Are you in the boiler room? "
                   "At least I know who I am, where I came from. "
                   "But if they hit you directly, you'll be sorry. Be careful.")
OTACON_LINES = {
    "ot_hello": "Hey, Snake. It's been a while.",
    "ot_brief": "Click on any project to see the full briefing. I can fill you in on the details, too.",
    "ot_repeat": "Want to learn more about any projects?",
}
OTACON_SPLIT_LINES = {
    "ot_hello": {"parts": ["Hey, Snake.", "It's been a while."], "gap_ms": 380},
    "ot_brief": {"parts": ["Click on any project to see the full briefing.",
                            "I can fill you in on the details, too."], "gap_ms": 420},
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
