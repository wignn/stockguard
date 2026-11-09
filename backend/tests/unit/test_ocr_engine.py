import subprocess
from pathlib import Path

import pytest

from stokguard.ocr.engine import OcrFailure, TesseractEngine


def test_tesseract_subprocess_timeout_is_safe(monkeypatch):
    observed = {}
    monkeypatch.setattr(TesseractEngine, "available", lambda self: True)

    def timeout(args, **kwargs):
        observed.update(args=args, **kwargs)
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(OcrFailure) as error:
        TesseractEngine("tesseract", "eng").recognize(Path("private image.png"), 60)
    assert error.value.code == "ocr_timeout"
    assert observed["args"] == [
        "tesseract",
        "private image.png",
        "stdout",
        "-l",
        "eng",
        "--psm",
        "6",
    ]
    assert observed["shell"] is False and observed["timeout"] == 60
