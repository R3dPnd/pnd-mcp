"""
Generate synthetic wake-word training samples using the installed piper-tts.
Defaults to "ok Dann"; pass --phrases-file for another persona (see wakeword_args.py).

Outputs 16 kHz mono WAV files to:
  training/positive/    — 3 000 clips of "ok dann" variants
  training/adversarial/ — 1 500 clips of similar-sounding phrases

Run:
    .venv/Scripts/python.exe scripts/generate_wakeword_samples.py
"""

import random
import sys
import wave
from pathlib import Path

import numpy as np
import scipy.signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # wakeword_args

from piper import PiperVoice, SynthesisConfig

from wakeword_args import load_phrases, parse_generate_args

# ── Config ────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).resolve().parents[1]
VOICE_MODEL = REPO_ROOT / "models" / "pieper" / "en_GB-northern_english_male-medium.onnx"

PIPER_RATE   = 22050   # this voice outputs 22 050 Hz
TARGET_RATE  = 16000   # OpenWakeWord requires 16 kHz
CLIP_SAMPLES = TARGET_RATE * 3  # 3-second clips → 48 000 samples

N_POSITIVE    = 3000
N_ADVERSARIAL = 1500

LENGTH_SCALES  = [0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.35, 1.50]
NOISE_SCALES   = [0.333, 0.500, 0.667, 0.800, 1.000]
NOISE_W_SCALES = [0.60, 0.80, 1.00]

# ── Helpers ───────────────────────────────────────────────────────────────────

def synthesize(voice: PiperVoice, text: str) -> np.ndarray:
    cfg = SynthesisConfig(
        length_scale=random.choice(LENGTH_SCALES),
        noise_scale=random.choice(NOISE_SCALES),
        noise_w_scale=random.choice(NOISE_W_SCALES),
    )
    chunks = list(voice.synthesize(text.strip(), cfg))
    audio  = np.frombuffer(b"".join(c.audio_int16_bytes for c in chunks), dtype=np.int16)
    # Resample 22 050 → 16 000 Hz  (ratio = 320/441)
    f = audio.astype(np.float32) / 32767.0
    r = scipy.signal.resample_poly(f, 320, 441)
    return np.clip(r * 32767, -32768, 32767).astype(np.int16)


def embed_in_clip(audio: np.ndarray) -> np.ndarray:
    """Place audio at a random offset inside a 3-second silence-padded clip."""
    clip = np.zeros(CLIP_SAMPLES, dtype=np.int16)
    if len(audio) >= CLIP_SAMPLES:
        return audio[:CLIP_SAMPLES]
    offset = random.randint(0, CLIP_SAMPLES - len(audio))
    clip[offset:offset + len(audio)] = audio
    return clip


def save_wav(samples: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_RATE)
        wf.writeframes(samples.tobytes())


def generate_set(voice: PiperVoice, phrases: list, out_dir: Path, prefix: str, n: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        audio = synthesize(voice, phrases[i % len(phrases)])
        save_wav(embed_in_clip(audio), out_dir / f"{prefix}_{i:05d}.wav")
        if (i + 1) % 250 == 0:
            print(f"  {i + 1}/{n}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_generate_args()
    voice_model = args.voice_model or VOICE_MODEL
    out_dir = args.out_dir or REPO_ROOT / "training"
    positive_phrases, adversarial_phrases = load_phrases(args.phrases_file)

    if not voice_model.exists():
        print(f"ERROR: voice model not found at {voice_model}")
        sys.exit(1)

    print("Loading voice model…", flush=True)
    voice = PiperVoice.load(str(voice_model), use_cuda=False)

    print(f"Generating {N_POSITIVE} positive clips → {out_dir / 'positive'}/", flush=True)
    generate_set(voice, positive_phrases, out_dir / "positive", "pos", N_POSITIVE)

    print(f"Generating {N_ADVERSARIAL} adversarial clips → {out_dir / 'adversarial'}/", flush=True)
    generate_set(voice, adversarial_phrases, out_dir / "adversarial", "adv", N_ADVERSARIAL)

    print("Done. Run scripts/train_wakeword.py next.", flush=True)


if __name__ == "__main__":
    main()
