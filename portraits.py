"""
Character portraits.

An uploaded image is downscaled and copied into ``portraits/`` inside the user
data folder; the character sheet only stores the file name. Keeping the pixels
out of ``character_sheets.json`` keeps that file small and quick to save.

Exporting a character embeds its portrait (base64) so it travels with the
sheet; importing writes it back out.
"""

import base64
import hashlib
import io
import os
import re
from typing import Optional

from paths import user_data_path

MAX_SIDE = 900                      # stored portraits are downscaled to fit this square
ACCEPTED_TYPES = [("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")]


def portrait_dir() -> str:
    path = user_data_path("portraits")
    os.makedirs(path, exist_ok=True)
    return path


def portrait_path(filename: str) -> Optional[str]:
    """Absolute path of a stored portrait, or None if it is not there."""
    if not filename:
        return None
    path = os.path.join(portrait_dir(), os.path.basename(filename))
    return path if os.path.isfile(path) else None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "character").lower()).strip("-")[:40] or "character"


def _store(image, character_name: str) -> str:
    """Save a PIL image as a PNG under a content-based name; returns the file name."""
    from PIL import Image
    image = image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    filename = f"{_slug(character_name)}-{hashlib.sha1(data).hexdigest()[:10]}.png"
    with open(os.path.join(portrait_dir(), filename), "wb") as f:
        f.write(data)
    return filename


def import_portrait(source_path: str, character_name: str) -> str:
    """Copy an image file into the portrait folder. Raises if it is not an image."""
    from PIL import Image
    with Image.open(source_path) as img:
        img.load()
        return _store(img, character_name)


def load_image(filename: str):
    """The stored portrait as a PIL image (or None)."""
    path = portrait_path(filename)
    if path is None:
        return None
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.load()
            return img.copy()
    except Exception:
        return None


def delete_portrait(filename: str, still_used_by: Optional[list] = None):
    """Remove a stored portrait unless another sheet still uses it."""
    if not filename or (still_used_by and filename in still_used_by):
        return
    path = portrait_path(filename)
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def encode_portrait(filename: str) -> Optional[str]:
    """Base64 of a stored portrait, for embedding in an export."""
    path = portrait_path(filename)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


def decode_portrait(data: str, character_name: str) -> str:
    """Write an embedded portrait back to disk; returns its file name ("" on failure)."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(base64.b64decode(data))) as img:
            img.load()
            return _store(img, character_name)
    except Exception:
        return ""
