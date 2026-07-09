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

# ── Per-project briefings ──
# Clicking a project plays: Snake asks, then Otacon explains it (scientific,
# two lines, with the tech/software/usage). Spoken text below uses phonetic
# respellings and spelled-out acronyms so the clone pronounces them; the
# on-screen text (portfolio.js CX_PROJECT_DIALOGUE) keeps the real spellings.
PROJECT_DIALOGUE = {
    "oculosaurus": {
        "snake": "Oculosaurus. What am I looking at?",
        "otacon": [
            "A stereo vision rig for the visually impaired. Two cameras on a Raspberry Pie headset triangulate depth in real time, the way your own eyes judge distance.",
            "It runs Yolo object recognition and streams a live 3D point cloud to the cloud, firing proximity alerts to your phone. Took first place, by the way.",
        ],
    },
    "memprobe": {
        "snake": "Memprobe. Break it down for me.",
        "otacon": [
            "It's a firmware forensics tool. You upload a compiled elf binary and it parses the dwarf debug data to map exactly where every byte of flash and RAM goes.",
            "A Jango front end, serverless parsing on Modal, a Postgres build history, and a command line tool that fails your build if the firmware grows too large.",
        ],
    },
    "echo-scout": {
        "snake": "Echo Scout. This one's yours in the field.",
        "otacon": [
            "A handheld scanner built on an E S P thirty-two. Millimeter wave radar sweeps an eighty degree arc to detect people in the dark, even behind thin cover.",
            "An eight by eight time of flight sensor rebuilds the room as a 3D point cloud, while the inertial sensor keeps a live compass on the touchscreen. Written in C plus plus.",
        ],
    },
    "song2vec": {
        "snake": "Song to Vec. What's the science here?",
        "otacon": [
            "It takes word embedding theory and applies it to music. A skip gram model learns vectors for genres, tags, and songs in one shared latent space.",
            "A variational autoencoder compresses each track into sixteen dimensions and paints a color blob from its mood. Built in PyTorch, projecting over two thousand vectors with principal component analysis.",
        ],
    },
    "bird-classifier": {
        "snake": "Backyard Bird Classifier. Explain.",
        "otacon": [
            "A convolutional neural network trained to identify thirty Alabama bird species purely from their calls.",
            "It turns each recording into a mel spectrogram, an image of sound, then classifies it. Wrapped in a Jango app that returns the top five guesses and the spectrogram itself.",
        ],
    },
    "personal-website": {
        "snake": "His personal site. Anything to it?",
        "otacon": [
            "You're standing in it, Snake. A Jango backend for a secure core, with Tailwind and Daisy U I driving the front end.",
            "It even serves live machine learning inference, hosting the bird classifier model right alongside the portfolio.",
        ],
    },
    "waste-drone": {
        "snake": "Waste Detection Drone. Give me the specs.",
        "otacon": [
            "An autonomous quadcopter for environmental monitoring. A custom Yolo vee five model, trained on annotated waste imagery, spots litter from the air.",
            "It flies programmatically through the Tello software kit, logging telemetry and tagging every detection for spatial analysis.",
        ],
    },
    "modpack-updater": {
        "snake": "Modpack Updater. What's it do?",
        "otacon": [
            "A cross platform desktop client that syncs Minecraft modpacks across a group using Amazon S three as the backing store.",
            "It uses Git style change tracking against a manifest, so one click pulls only the differences. Built in Java and Java F X, packaged with Gradle.",
        ],
    },
    "visaudio": {
        "snake": "Vis Audio. Run it down.",
        "otacon": [
            "An audio workbench in Python. Format conversion, bitrate resampling, spectral noise reduction, even a built in downloader.",
            "It visualizes every file as a waveform and a mel spectrogram through Librosa, wrapped in a Pie Q T interface. Handles nearly every codec you'd throw at it.",
        ],
    },
    "born-in-spellbooks": {
        "snake": "Born in Spellbooks. A game mod?",
        "otacon": [
            "A compatibility mod for Minecraft Forge, bridging two combat systems into one. Seventeen spells coded from scratch.",
            "Custom rendering, layered animation, and shared entity logic keep it stable. Open source, three alpha releases deep.",
        ],
    },
    "fretwatch": {
        "snake": "Fretwatch. What's the readout?",
        "otacon": [
            "Real time guitar transcription. It fuses two signals, the audio and the video of your hands, to detect notes and chords as you play.",
            "Librosa extracts the spectral features while Open C V tracks the fretboard frame by frame. Still in development.",
        ],
    },
    "minecraft-server": {
        "snake": "The Minecraft server. That's infrastructure.",
        "otacon": [
            "A fully custom world, administered on a Linux host. Curated mods, resource packs, and hand built data packs.",
            "The data packs are scripted in Jason and M C script to generate custom mobs, biomes, loot tables, and structures. Ongoing network and config management.",
        ],
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
    SNAKE_LINES[_sk] = _d["snake"]
    if (_sp := _sentence_split(_d["snake"])):
        SNAKE_SPLIT_LINES[_sk] = _sp
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
