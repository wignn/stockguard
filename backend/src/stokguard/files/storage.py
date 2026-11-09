import hashlib
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from stokguard.core.errors import DomainError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000


@dataclass(frozen=True)
class StoredUpload:
    key: str
    original_name: str
    mime_type: str
    sha256: str
    size_bytes: int
    width: int
    height: int


def safe_name(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^\w. ()-]", "_", name)[:120].strip(" .")
    return name or "bukti"


def stage_upload(root: Path, stream: BinaryIO, original_name: str) -> StoredUpload:
    root.mkdir(parents=True, exist_ok=True)
    key = uuid4().hex
    temporary = root / f"{key}.part"
    final = root / key
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("xb") as destination:
            while block := stream.read(64 * 1024):
                size += len(block)
                if size > MAX_BYTES:
                    raise DomainError("file_too_large", 413, "Batas ukuran foto adalah 5 MiB.")
                digest.update(block)
                destination.write(block)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(temporary) as image:
                    fmt, width, height = image.format, image.width, image.height
                    if fmt not in {"JPEG", "PNG"} or width * height > MAX_PIXELS:
                        raise ValueError("unsupported image")
                    if getattr(image, "n_frames", 1) != 1:
                        raise ValueError("animated image")
                    image.verify()
                with Image.open(temporary) as image:
                    image.load()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise DomainError(
                "invalid_image", 422, "Gunakan JPG atau PNG valid, maksimal 20 megapiksel."
            ) from exc
        temporary.replace(final)
        return StoredUpload(
            key,
            safe_name(original_name),
            "image/jpeg" if fmt == "JPEG" else "image/png",
            digest.hexdigest(),
            size,
            width,
            height,
        )
    finally:
        temporary.unlink(missing_ok=True)


def content_path(root: Path, key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    path = root / key
    if path.is_symlink() or not path.is_file():
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return path
