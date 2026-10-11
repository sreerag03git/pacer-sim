"""Golden regression + determinism tests for the PACER engine.

These assert three things the Phase-0 gate requires:

  1. The engine package imports nothing from Streamlit (it is UI-free).
  2. Seed 7 reproduces the engine's own documented output (the committed
     fixture tests/golden_seed7.json) exactly.
  3. Re-running the same seed + config is byte-identical.

Run with pytest (``python -m pytest tests``) or standalone
(``python tests/test_golden.py``).
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

# Allow running both via pytest and standalone (python tests/test_golden.py):
# ensure the project root (which contains the engine/ and tests/ packages) is
# importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import ControllerMode
from tests.golden_util import GOLDEN_CONFIG, golden_payload

_FIXTURE = pathlib.Path(__file__).with_name("golden_seed7.json")


def _load_fixture() -> dict:
    with open(_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def test_engine_has_no_streamlit_import() -> None:
    """engine/ must be free of any Streamlit dependency."""
    engine_dir = pathlib.Path(__file__).resolve().parent.parent / "engine"
    offenders = []
    for path in engine_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        if "import streamlit" in text or "from streamlit" in text:
            offenders.append(path.name)
    assert not offenders, f"Streamlit imported in engine modules: {offenders}"


def test_seed7_matches_golden_fixture() -> None:
    """Seed 7 reproduces the committed golden output exactly."""
    expected = _load_fixture()
    actual = golden_payload(GOLDEN_CONFIG)
    # Compare as canonical JSON so any drift in any field fails loudly.
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_reruns_are_byte_identical() -> None:
    """Two independent runs of the same config produce identical payloads."""
    a = json.dumps(golden_payload(GOLDEN_CONFIG), sort_keys=True)
    b = json.dumps(golden_payload(GOLDEN_CONFIG), sort_keys=True)
    assert a == b


def test_mode_ordering_is_physical() -> None:
    """Baseline must blow out at least as often as PACER, which blows at least as
    often as PACER + Beacon. (Sanity, not a tuned target.)"""
    payload = _load_fixture()
    by_mode = {row["mode"]: row["blowout_runs"] for row in payload["headline"]}
    assert by_mode[ControllerMode.BASELINE.value] >= by_mode[ControllerMode.PACER.value]
    assert by_mode[ControllerMode.PACER.value] >= by_mode[ControllerMode.PACER_BEACON.value]


def _run_standalone() -> int:
    tests = [
        test_engine_has_no_streamlit_import,
        test_seed7_matches_golden_fixture,
        test_reruns_are_byte_identical,
        test_mode_ordering_is_physical,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
