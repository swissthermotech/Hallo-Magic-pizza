"""Product photos: upload (optimised with Pillow) to Emergent Object Storage, served publicly through the API.
Menu photos are public, so reads need no auth. Files are cached on local disk to keep storage reads low."""
import io
import logging
import os
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "hallo-magic-pizza"
CACHE_DIR = Path(os.environ.get("PHOTO_CACHE_DIR", "/tmp/hmp_photo_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_EDGE = 1600       # long edge in px – sharp on phones and retina web without huge files
JPEG_QUALITY = 86
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

storage_key = None
router = APIRouter()


def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def _put(path: str, data: bytes, content_type: str) -> dict:
    global storage_key
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 503:  # stale key -> re-init once
        storage_key = None
        key = init_storage()
        resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 402:
        raise HTTPException(402, "Stockage: crédits épuisés – impossible de téléverser pour le moment")
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> bytes:
    global storage_key
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 503:
        storage_key = None
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if not resp.ok:
        raise HTTPException(404, "Photo not found")
    return resp.content


def optimise(raw: bytes) -> bytes:
    """Fix EXIF orientation, downscale to MAX_EDGE, re-encode as progressive JPEG (quality 86)."""
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception:
        raise HTTPException(400, "Fichier image invalide")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    scale = MAX_EDGE / max(w, h)
    if scale < 1:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out.getvalue()


def _manager():
    import staff_auth
    return staff_auth.require_roles("manager")


@router.post("/uploads/product-photo")
async def upload_product_photo(file: UploadFile = File(...), _: dict = Depends(_manager())):
    """Admin upload. Returns the public API url to store on the product (image_url / images[])."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image trop volumineuse (max 15 MB)")
    data = await run_in_threadpool(optimise, raw)
    path = f"{APP_NAME}/products/{uuid.uuid4().hex}.jpg"
    await run_in_threadpool(_put, path, data, "image/jpeg")
    (CACHE_DIR / path.replace("/", "__")).write_bytes(data)
    return {"path": path, "url": f"/api/files/{path}", "size": len(data)}


@router.get("/files/{path:path}")
async def get_file(path: str):
    if not path.startswith(f"{APP_NAME}/"):
        raise HTTPException(404, "Not found")
    cached = CACHE_DIR / path.replace("/", "__")
    if cached.exists():
        data = cached.read_bytes()
    else:
        data = await run_in_threadpool(_get, path)
        cached.write_bytes(data)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})
