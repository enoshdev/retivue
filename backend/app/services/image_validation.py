import hashlib
import io
import os
import re
import warnings
from dataclasses import dataclass
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageFile, UnidentifiedImageError
from app.core.config import settings

# Do NOT tolerate truncated images; fail loudly on incomplete scanlines
ImageFile.LOAD_TRUNCATED_IMAGES = False

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_BLOCKED_MAGIC_PREFIXES = (
    b"MZ",          # Windows PE executable
    b"\x7fELF",      # Linux ELF binary
    b"#!",           # Shell / script shebang
    b"%PDF-",        # PDF document
    b"PK\x03\x04",   # ZIP / DOCX / JAR archive
    b"<svg",         # SVG vector / script container
    b"<?xml",        # XML document
    b"<html",        # HTML payload
    b"<!DOCTYPE",    # HTML/XML doctype
)

_ALLOWED_MIME_TO_FORMAT = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/pjpeg": "JPEG",
    "image/png": "PNG",
}

_FORMAT_TO_MEDIA_TYPE = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
}

_FORMAT_TO_EXTENSIONS = {
    "JPEG": (".jpg", ".jpeg"),
    "PNG": (".png",),
}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ValidatedRetinalImage:
    raw_bytes: bytes
    sanitized_filename: str
    detected_media_type: str
    canonical_extension: str
    file_size_bytes: int
    width: int
    height: int
    sha256_checksum: str
    has_exif_metadata: bool


def sanitize_display_filename(filename: Optional[str], fallback_ext: str) -> str:
    """
    Sanitize user-supplied filename strictly for display metadata.
    Never used to construct filesystem paths or storage keys.
    """
    if not filename:
        return f"fundus_upload{fallback_ext}"
    base = os.path.basename(filename.strip())
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not cleaned:
        return f"fundus_upload{fallback_ext}"
    if len(cleaned) > 120:
        stem, ext = os.path.splitext(cleaned)
        cleaned = f"{stem[:100]}{ext[:16]}"
    return cleaned


async def read_upload_with_size_limit(file: UploadFile, max_bytes: int) -> bytes:
    """
    Read uploaded stream safely in chunks, aborting immediately if size exceeds limit
    so oversized files or abusive streams do not exhaust server memory.
    """
    chunks = []
    total_size = 0
    chunk_size = 256 * 1024  # 256 KB

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            max_mb = round(max_bytes / (1024 * 1024), 1)
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded file exceeds the maximum allowed limit of {max_mb} MB.",
            )
        chunks.append(chunk)

    return b"".join(chunks)


def validate_and_inspect_image_bytes(
    raw_bytes: bytes,
    claimed_filename: Optional[str],
    claimed_content_type: Optional[str],
) -> ValidatedRetinalImage:
    """
    Perform rigorous server-side validation on uploaded image bytes.
    Supports strictly JPEG and PNG. Preserves raw_bytes completely unaltered.
    """
    # 1. Reject empty files
    if not raw_bytes or len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty.",
        )

    # 2. Enforce exact max byte size
    if len(raw_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = round(settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024), 1)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded file exceeds the maximum allowed limit of {max_mb} MB.",
        )

    # 3. Validate claimed MIME type if provided
    normalized_mime = (claimed_content_type or "").split(";")[0].strip().lower()
    claimed_format: Optional[str] = None
    if normalized_mime:
        if normalized_mime not in _ALLOWED_MIME_TO_FORMAT:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported media type '{normalized_mime}'. Only JPEG and PNG images are supported.",
            )
        claimed_format = _ALLOWED_MIME_TO_FORMAT[normalized_mime]

    # 4. Reject known executable / script / document magic prefixes explicitly
    stripped_lead = raw_bytes[:64].lstrip()
    for blocked_prefix in _BLOCKED_MAGIC_PREFIXES:
        if raw_bytes.startswith(blocked_prefix) or stripped_lead.lower().startswith(blocked_prefix.lower()):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Disallowed file signature detected. Only genuine JPEG and PNG retinal images are accepted.",
            )

    # 5. Inspect genuine image magic bytes
    if raw_bytes.startswith(_JPEG_MAGIC):
        magic_format = "JPEG"
    elif raw_bytes.startswith(_PNG_MAGIC):
        magic_format = "PNG"
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unrecognized file signature. File bytes do not match JPEG or PNG format.",
        )

    # 6. Verify Content-Type consistency against magic bytes
    if claimed_format and claimed_format != magic_format:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"MIME type mismatch: header indicates {claimed_format}, "
                f"but actual file signature is {magic_format}."
            ),
        )

    # 7. Verify file extension consistency if filename has an extension
    if claimed_filename:
        base_name = os.path.basename(claimed_filename.strip())
        _, raw_ext = os.path.splitext(base_name)
        ext_lower = raw_ext.lower()
        if ext_lower:
            expected_exts = _FORMAT_TO_EXTENSIONS[magic_format]
            if ext_lower not in expected_exts:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"File extension '{ext_lower}' does not match detected image format ({magic_format}). "
                        f"Supported extensions for {magic_format}: {', '.join(expected_exts)}."
                    ),
                )

    # 8. Pillow decoding, structural verify, truncation detection, and decompression-bomb guard
    previous_max_pixels = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
    has_exif = False
    width = 0
    height = 0

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            # First pass: open and verify header/CRC integrity
            with Image.open(io.BytesIO(raw_bytes)) as img:
                if img.format != magic_format:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Image decoder format mismatch against file signature.",
                    )
                width, height = img.size
                if width <= 0 or height <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Image reports invalid zero or negative dimensions.",
                    )
                if width * height > settings.MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Image pixel count exceeds safety threshold (decompression bomb protection).",
                    )
                img.verify()

            # Second pass: re-open and force full pixel decode to catch truncated streams
            with Image.open(io.BytesIO(raw_bytes)) as decoded_img:
                width, height = decoded_img.size
                exif_data = decoded_img.getexif()
                has_exif = bool(exif_data and len(exif_data) > 0)
                decoded_img.load()

    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image rejected by decompression-bomb protection due to excessive pixel dimensions.",
        )
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image file is corrupt, truncated, or cannot be safely decoded.",
        )
    finally:
        Image.MAX_IMAGE_PIXELS = previous_max_pixels

    # 9. Validate pixel dimension thresholds
    if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Image dimensions ({width}x{height}) are below the minimum required "
                f"{settings.MIN_IMAGE_WIDTH}x{settings.MIN_IMAGE_HEIGHT} resolution."
            ),
        )
    if width > settings.MAX_IMAGE_WIDTH or height > settings.MAX_IMAGE_HEIGHT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Image dimensions ({width}x{height}) exceed the maximum supported "
                f"{settings.MAX_IMAGE_WIDTH}x{settings.MAX_IMAGE_HEIGHT} limit."
            ),
        )

    # 10. Calculate SHA-256 of exact original bytes
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    canonical_ext = ".jpg" if magic_format == "JPEG" else ".png"
    detected_media_type = _FORMAT_TO_MEDIA_TYPE[magic_format]
    safe_filename = sanitize_display_filename(claimed_filename, canonical_ext)

    return ValidatedRetinalImage(
        raw_bytes=raw_bytes,
        sanitized_filename=safe_filename,
        detected_media_type=detected_media_type,
        canonical_extension=canonical_ext,
        file_size_bytes=len(raw_bytes),
        width=width,
        height=height,
        sha256_checksum=sha256_hex,
        has_exif_metadata=has_exif,
    )

