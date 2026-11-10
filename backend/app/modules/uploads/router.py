import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from app.core.config import settings
from app.modules.sellers.dependencies import get_approved_seller
from app.modules.sellers.models import Seller

router = APIRouter(prefix="/uploads", tags=["uploads"])

MEDIA_URL = "/api/v1/media"
UPLOAD_ROOT = Path(settings.upload_dir)

# Detected from the file's leading bytes, never from the client-supplied filename or Content-Type.
# SVG is deliberately not allowed (it can carry scripts).
SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
]


def detect_extension(head: bytes) -> str | None:
    for magic, ext in SIGNATURES:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


class UploadOut(BaseModel):
    url: str


@router.post("/images", response_model=UploadOut, status_code=201)
async def upload_image(file: UploadFile = File(...), seller: Seller = Depends(get_approved_seller)):
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # never buffer more than limit+1 bytes
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Image must be at most {settings.max_upload_mb} MB")
    ext = detect_extension(data[:16])
    if ext is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG, WebP or GIF images are allowed")
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_ROOT / name).write_bytes(data)
    return UploadOut(url=f"{MEDIA_URL}/{name}")


class MediaFiles(StaticFiles):
    """Static image serving that forbids content sniffing and allows long caching (names are random)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def media_app() -> MediaFiles:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return MediaFiles(directory=UPLOAD_ROOT)
