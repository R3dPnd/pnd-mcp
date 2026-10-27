"""Command-line options shared by the wake-word scripts, so a persona can train
its own phrase without editing them. Kept free of heavy imports (piper, torch)
so it can be imported and tested on its own.

With no options the scripts behave as they always have: "ok Dann" phrases,
training/ clips, models/ok_dann.onnx.

A phrases file is YAML with `positive:` and/or `adversarial:` lists. Phrases
go to Piper exactly as written, so spell the wake word the way it's actually
pronounced (e.g. "okay uh-kane" for an Akane said uh-KANE).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

DEFAULT_POSITIVE_PHRASES = [
    "ok dann", "okay dann", "ok dan", "okay dan",
    "ok Dann", "okay Dann", "ok then Dann",
]

DEFAULT_ADVERSARIAL_PHRASES = [
    "ok jan",  "ok man",  "ok can",  "ok ann",  "ok van",  "ok ran",
    "hey dan", "hey dann", "hey jan",
    "ok google", "hey jarvis", "alexa",
    "okay then", "ok thanks", "ok good", "ok sure",
]


def load_phrases(path: Path | None) -> tuple[list[str], list[str]]:
    """(positive, adversarial) phrases — from *path* where it has them,
    otherwise the ok-Dann defaults."""
    data = (yaml.safe_load(path.read_text()) or {}) if path else {}
    return (
        list(data.get("positive") or DEFAULT_POSITIVE_PHRASES),
        list(data.get("adversarial") or DEFAULT_ADVERSARIAL_PHRASES),
    )


def parse_generate_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic wake-word training clips with Piper.")
    p.add_argument("--phrases-file", type=Path, help="YAML with positive:/adversarial: phrase lists")
    p.add_argument("--out-dir", type=Path, help="where positive/ and adversarial/ clips go (default: training/)")
    p.add_argument("--voice-model", type=Path, help="Piper .onnx voice to synthesize with")
    return p.parse_args(argv)


def parse_train_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train an openWakeWord model from generated clips.")
    p.add_argument("--out-model", type=Path, help="output .onnx (default: models/ok_dann.onnx)")
    p.add_argument("--clips-dir", type=Path, help="dir holding positive/, positive_real/, adversarial/ (default: training/)")
    p.add_argument("--voice-model", type=Path, help="Piper .onnx voice for the extra negative clips")
    return p.parse_args(argv)


def output_name(model_path: Path) -> str:
    """The ONNX output name openWakeWord reports detections under — the
    model file's stem, e.g. models/ok_akane.onnx → "ok_akane"."""
    return model_path.stem
