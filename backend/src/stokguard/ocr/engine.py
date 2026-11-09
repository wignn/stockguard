import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class OcrText:
    text: str


class OcrFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OcrEngine(Protocol):
    def recognize(self, image_path: Path, timeout_seconds: int) -> OcrText: ...


class TesseractEngine:
    def __init__(self, command: str, languages: str):
        self.command = command
        self.languages = languages

    def available(self) -> bool:
        return shutil.which(self.command) is not None

    def recognize(self, image_path: Path, timeout_seconds: int) -> OcrText:
        if not self.available():
            raise OcrFailure("ocr_unavailable")
        try:
            result = subprocess.run(
                [self.command, str(image_path), "stdout", "-l", self.languages, "--psm", "6"],
                shell=False,
                timeout=timeout_seconds,
                capture_output=True,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrFailure("ocr_timeout") from exc
        except OSError as exc:
            raise OcrFailure("ocr_unavailable") from exc
        if result.returncode != 0:
            raise OcrFailure("ocr_failed")
        if len(result.stdout) > 1024 * 1024:
            raise OcrFailure("ocr_output_too_large")
        return OcrText(result.stdout.decode("utf-8", errors="replace"))
