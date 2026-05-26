#!/usr/bin/env python3
"""
Generate grid preview thumbnails under dist/images/_thumbs/ (build output only).
Mirrors dist/images/** raster layout; full-size assets stay at asset.url for CDN copy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_IMAGES = PROJECT_ROOT / "dist" / "images"
THUMBS_PREFIX = "_thumbs"

RASTER_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}
SKIP_EXTENSIONS = {".svg", ".gif"}

DEFAULT_THUMB_MAX_WIDTH = 560
DEFAULT_THUMB_WEBP_QUALITY = 78
DEFAULT_SKIP_IF_SMALLER = True


def load_thumb_config() -> Dict:
    config_path = PROJECT_ROOT / "config.toml"
    defaults = {
        "thumb_max_width": DEFAULT_THUMB_MAX_WIDTH,
        "thumb_webp_quality": DEFAULT_THUMB_WEBP_QUALITY,
        "thumb_skip_if_smaller": DEFAULT_SKIP_IF_SMALLER,
    }
    if not config_path.exists() or tomllib is None:
        return defaults
    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        build = raw.get("build", {})
        for key in defaults:
            if key in build:
                defaults[key] = build[key]
    except Exception as e:
        print(f"Warning: Could not read config.toml: {e}")
    return defaults


def is_source_raster(rel: Path) -> bool:
    parts = rel.parts
    if not parts or parts[0] != "images":
        return False
    if THUMBS_PREFIX in parts:
        return False
    return rel.suffix.lower() == ".webp"


def thumb_rel_path(source_rel: str) -> str:
    """images/foo/bar.webp -> images/_thumbs/foo/bar.webp"""
    if not source_rel.startswith("images/"):
        raise ValueError(source_rel)
    sub = Path(source_rel[len("images/") :]).with_suffix(".webp")
    return f"images/{THUMBS_PREFIX}/{sub.as_posix()}"


def iter_source_images() -> list[Path]:
    if not DIST_IMAGES.exists():
        return []
    files: list[Path] = []
    for path in DIST_IMAGES.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PROJECT_ROOT / "dist")
        if is_source_raster(rel):
            files.append(path)
    return sorted(files)


def resize_to_webp(
    src: Path, dest: Path, max_width: int, quality: int
) -> Tuple[int, int, int]:
    """Return (out_width, out_height, out_bytes)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.load()
        w, h = im.size
        if w > max_width:
            new_h = max(1, round(h * max_width / w))
            resized = im.resize((max_width, new_h), Image.Resampling.LANCZOS)
        else:
            resized = im.copy()
        if resized.mode not in ("RGB", "RGBA"):
            resized = resized.convert("RGBA" if "A" in resized.getbands() else "RGB")
        out_w, out_h = resized.size
        resized.save(dest, "WEBP", quality=quality, method=6)
    return out_w, out_h, dest.stat().st_size


def main() -> int:
    cfg = load_thumb_config()
    max_width = int(cfg["thumb_max_width"])
    quality = int(cfg["thumb_webp_quality"])
    skip_if_smaller = bool(cfg["thumb_skip_if_smaller"])

    sources = iter_source_images()
    if not sources:
        print("No raster images in dist/images/ — skipping thumbnail generation.")
        return 0

    generated = 0
    skipped = 0
    skipped_small = 0
    full_bytes = 0
    thumb_bytes = 0

    for src in sources:
        rel = src.relative_to(PROJECT_ROOT / "dist").as_posix()
        dest = PROJECT_ROOT / "dist" / thumb_rel_path(rel)

        try:
            with Image.open(src) as probe:
                src_w, _ = probe.size
        except Exception as e:
            print(f"  ✗ Skip (unreadable): {rel} — {e}")
            skipped += 1
            continue

        src_size = src.stat().st_size
        full_bytes += src_size

        if skip_if_smaller and src_w <= max_width:
            skipped_small += 1
            continue

        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            thumb_bytes += dest.stat().st_size
            skipped += 1
            continue

        try:
            out_w, out_h, out_size = resize_to_webp(src, dest, max_width, quality)
            thumb_bytes += out_size
            generated += 1
            print(f"  ✓ {rel} -> {thumb_rel_path(rel)} ({out_w}x{out_h}, {out_size // 1024}KB)")
        except Exception as e:
            print(f"  ✗ Failed: {rel} — {e}")
            skipped += 1

    saved = full_bytes - thumb_bytes if thumb_bytes else 0
    print(
        f"Thumbnails: {generated} generated, {skipped} up-to-date, "
        f"{skipped_small} skipped (already ≤{max_width}px wide)"
    )
    if generated or thumb_bytes:
        print(
            f"  Full-size total scanned: {full_bytes // 1024}KB | "
            f"Thumbs on disk: {thumb_bytes // 1024}KB"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
