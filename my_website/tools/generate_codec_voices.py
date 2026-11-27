#!/usr/bin/env python3
"""Generate the Colonel's codec voice lines via the Qwen3-TTS HF Space.

Usage:
    pip install gradio_client
    HF_TOKEN=hf_xxx python tools/generate_codec_voices.py   # token optional but avoids quota limits

Skips files that already exist, so it can be re-run until all lines are done.
Output: static/audio/codec/<key>.m4a  (played by the codec dialogue engine)
"""
import os, subprocess, sys, time
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
    "c0_l0": "Snake, this is Nick Burcheck. He's a software developer and A I integration engineer at Viper Imaging.",
    "c0_l1": "Everything we've gathered on him is laid out below. We've also attached his direct links. For anything specific, tune through the other channels, or open MEMORY for the list.",
    "c1_l0": "His operation records. Twelve declassified projects on file.",
    # portfolio.js asks for c1_l0_<count> whenever the count is not twelve
    "c1_l0_13": "His operation records. Thirteen declassified projects on file.",
    "c1_l0_14": "His operation records. Fourteen declassified projects on file.",
    "c1_l0_15": "His operation records. Fifteen declassified projects on file.",
    "c1_l1": "For the details, get Ottacon on the line. Hal's been cataloguing all of it.",
    "c1_l2": "He's already listening.",
    "c2_l0": "He also records as Zero Barbecue. A one-man operation.",
    "c2_l1": "First single's out now. Listen below.",
    "c3_p0": "A private Minecraft world: custom modpack, custom server. Five seasons on record.",
    "c3_p1": "We've opened a portal into it. The live map, who's online, and every boss still standing. Go through it, Snake.",
}

# Lines assembled from separately generated parts with silence between them
# (a TTS can't be trusted to hold a beat). Generators that support it should
# prefer this over the flat LINES text for these keys.
SPLIT_LINES = {
    "c0_l0": {"parts": ["Snake, this is Nick Burcheck.",
                         "He's a software developer and A I integration engineer at Viper Imaging."], "gap_ms": 430},
    "c0_l1": {"parts": ["Everything we've gathered on him is laid out below.",
                         "We've also attached his direct links.",
                         "For anything specific, tune through the other channels, or open MEMORY for the list."], "gap_ms": 430},
    "c1_l0": {"parts": ["His operation records.", "Twelve declassified projects on file."], "gap_ms": 450},
    "c1_l0_13": {"parts": ["His operation records.", "Thirteen declassified projects on file."], "gap_ms": 450},
    "c1_l0_14": {"parts": ["His operation records.", "Fourteen declassified projects on file."], "gap_ms": 450},
    "c1_l0_15": {"parts": ["His operation records.", "Fifteen declassified projects on file."], "gap_ms": 450},
    "c2_l0": {"parts": ["He also records as Zero Barbecue.", "A one-man operation."], "gap_ms": 420},
    "c3_p0": {"parts": ["A private Minecraft world: custom modpack, custom server.",
                         "Five seasons on record."], "gap_ms": 450},
    "c3_p1": {"parts": ["We've opened a portal into it.",
                         "The live map, who's online, and every boss still standing.",
                         "Go through it, Snake."], "gap_ms": 420},
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
}

SNAKE_SPLIT_LINES = {
    # the name rides with the next sentence: on its own the clone garbles it
    "snake_hal": {"parts": ["Hal Emmerick. Been a while since Shadow Moses.",
                             "Patch him in."], "gap_ms": 380},
    "snake_look": {"parts": ["Alright.", "Let's take a look, then."], "gap_ms": 380},
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

# ── Per-project briefings ──
# Clicking a project plays: Snake asks, then Otacon answers in two short lines:
# what it is, then the one thing worth knowing. Short sentences with few commas;
# the clone rushes through long clauses. Spoken text below uses phonetic
# respellings and spelled-out acronyms so the clone pronounces them; the
# on-screen text (portfolio.js PROJECTS) keeps the real spellings.
PROJECT_DIALOGUE = {
    "oculosaurus": {
        "snake": "Ockyulo-saurus. What am I looking at?",
        "otacon": ["Goggles for the visually impaired. Two cameras judge depth the way your eyes do.",
                   "When something gets close, a phone alert warns you. It took first place."],
    },
    "gvoice": {
        "snake": "Gee Voice. What does it do?",
        "otacon": ["It reads Minecraft chat out loud. Every player gets their own voice.",
                   "There are eighteen thousand to choose from. It all runs in one Docker container."],
    },
    "albumdl": {
        "snake": "Album D L. What's this one for?",
        "otacon": ["It downloads whole albums. Covers, tags and lyrics are filled in for you.",
                   "It runs on his home server. That's where his music library lives."],
    },
    "homelab": {
        "snake": "A home lab. What's he running?",
        "otacon": ["An old office PC, rebuilt as a Linux server. It routes the whole house.",
                   "It blocks ads, streams his media, and keeps the music library."],
    },
    "groidberbium": {
        "snake": "Groid-burbium. Sounds unstable.",
        "otacon": ["It's actually very stable. It makes Minecraft draw faster.",
                   "With two hundred forty mods, a MacBook Air still runs at two hundred fifty frames per second."],
    },
    "memprobe": {
        "snake": "Memprobe. Break it down for me.",
        "otacon": ["It reads compiled firmware and shows where every byte of memory goes.",
                   "If a build grows too big, it stops it before it ships."],
    },
    "echo-scout": {
        "snake": "Echo Scout. What does it pick up?",
        "otacon": ["People. Its radar can find someone in the dark.",
                   "A depth sensor maps the room in 3D at the same time."],
    },
    "song2vec": {
        "snake": "Song to Vec. What's the science here?",
        "otacon": ["It places every song on a map. Songs that feel alike land close together.",
                   "Then it paints each one as a blob of color."],
    },
    "bird-classifier": {
        "snake": "Backyard Bird Classifier. Explain.",
        "otacon": ["Play it a bird call and it names the species.",
                   "It knows thirty Alabama birds. You can try it below."],
    },
    "personal-website": {
        "snake": "His personal site. Anything to it?",
        "otacon": ["You're inside it right now. Our voices were cloned with A I.",
                   "Even our mouths move with the audio."],
    },
    "waste-drone": {
        "snake": "Waste Detection Drone. Give me the specs.",
        "otacon": ["A small drone that flies itself and looks for trash.",
                   "A vision model marks every piece it finds."],
    },
    # "2": the app was rewritten, and the first take describes the old one.
    # portfolio.js sets voice:'modpack-updater2' on the project to match.
    "modpack-updater2": {
        "snake": "Groid Pack Updater. What's it do?",
        "otacon": ["It keeps everyone's mods matched to the server. One click and you're current.",
                   "Your worlds and settings are never touched."],
    },
    "visaudio": {
        "snake": "Vizz Audio. Run it down.",
        "otacon": ["An audio toolkit. It converts files and cleans out noise.",
                   "It also draws each file as a waveform."],
    },
    "born-in-spellbooks": {
        "snake": "Born in Spellbooks. A game mod?",
        "otacon": ["A Minecraft mod. It joins two magic mods into one.",
                   "Seventeen new spells, all written from scratch."],
    },
    "minecraft-server": {
        "snake": "The Minecraft server. That's infrastructure.",
        "otacon": ["A private world with its own modpack. Five seasons so far.",
                   "The portal shows who's online right now."],
    },
}


def _sentence_split(text, gap_ms=380):
    """Split a line into sentences so the generator inserts a beat between them."""
    import re
    parts = [p for p in re.split(r"(?<=[.?]) +", text.strip()) if p]
    return {"parts": parts, "gap_ms": gap_ms} if len(parts) > 1 else None


# Fold the per-project briefings into the flat line/split tables by voice.
for _pid, _d in PROJECT_DIALOGUE.items():
    _sk = f"sk_{_pid}"
    # Snake's question is rendered whole. Split, the project name became a
    # one-word sentence of its own, and the clone shouts those.
    SNAKE_LINES[_sk] = _d["snake"]
    for _i, _line in enumerate(_d["otacon"]):
        _ok = f"ot_{_pid}_{_i}"
        OTACON_LINES[_ok] = _line
        if (_sp := _sentence_split(_line)):
            OTACON_SPLIT_LINES[_ok] = _sp


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
