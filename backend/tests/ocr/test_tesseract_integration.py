import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from stokguard.core.config import Settings


def test_real_tesseract_synthetic_printed_receipt(tmp_path):
    from stokguard.ocr.engine import TesseractEngine

    settings = Settings()
    if not shutil.which(settings.tesseract_command):
        pytest.skip("Tesseract executable unavailable; real OCR not verified")
    image = Image.new("RGB", (1400, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text(
        (50, 50),
        "SYNTHETIC RECEIPT\nNo Nota: SYN-123\nTanggal: 2026-11-09\nRoti 2 12000",
        fill="black",
        font=ImageFont.load_default(size=48),
        spacing=20,
    )
    path = tmp_path / "synthetic-receipt.png"
    image.save(path)
    result = TesseractEngine(settings.tesseract_command, settings.ocr_languages).recognize(path, 60)
    assert "SYN" in result.text and "2026" in result.text
