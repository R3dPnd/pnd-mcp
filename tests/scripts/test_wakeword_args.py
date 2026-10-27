"""Argument handling for the wake-word scripts — a persona supplies its own
phrases (spelled the way its wake word is actually pronounced), output paths
and model name; with no arguments they behave exactly as before (ok Dann)."""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wakeword" / "wakeword_args.py"
_spec = importlib.util.spec_from_file_location("wakeword_args", _PATH)
wa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wa)


def test_default_phrases_keep_ok_dann():
    pos, adv = wa.load_phrases(None)
    assert pos[0] == "ok dann"
    assert "ok jan" in adv


def test_phrases_file_overrides_both_lists(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text("positive: [okay uh-kane]\nadversarial: [okay cane]\n")
    args = wa.parse_generate_args(["--phrases-file", str(f)])
    assert wa.load_phrases(args.phrases_file) == (["okay uh-kane"], ["okay cane"])


def test_phrases_file_missing_list_keeps_default(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text("positive: [okay uh-kane]\n")
    pos, adv = wa.load_phrases(f)
    assert pos == ["okay uh-kane"] and "ok jan" in adv


def test_generate_args_default_to_none():
    args = wa.parse_generate_args([])
    assert args.phrases_file is None and args.out_dir is None and args.voice_model is None


def test_train_args(tmp_path):
    args = wa.parse_train_args(["--out-model", "models/ok_akane.onnx", "--clips-dir", str(tmp_path)])
    assert args.out_model == Path("models/ok_akane.onnx") and args.clips_dir == tmp_path


def test_output_name_from_model_stem():
    assert wa.output_name(Path("models/ok_akane.onnx")) == "ok_akane"
    assert wa.output_name(Path("models/ok_dann.onnx")) == "ok_dann"
