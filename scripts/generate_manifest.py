#!/usr/bin/env python3
"""
Generate dist/assets.json for the static asset browser.
Scans dist/ after build, dedupes raster pairs (jpg/png + webp), and groups by category.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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

DEFAULT_BASE_URL = "https://assets.led-bugs.com"

EXCLUDE_NAMES = {
    "CNAME",
    "assets.json",
    "index.html",
    "styles.css",
    "app.js",
    "gate.js",
    "favicon.svg",
}

IMAGE_EXTENSIONS = {".webp", ".svg", ".png", ".jpg", ".jpeg", ".gif"}
RASTER_DEDUPE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
PREFERRED_RASTER = ".webp"
THUMBS_DIR_PREFIX = "images/_thumbs/"


def is_thumb_asset_path(rel_str: str) -> bool:
    return rel_str.startswith(THUMBS_DIR_PREFIX)


def thumb_path_for_asset(rel_str: str) -> Optional[str]:
    """images/foo/bar.webp -> images/_thumbs/foo/bar.webp"""
    if not rel_str.startswith("images/") or is_thumb_asset_path(rel_str):
        return None
    return f"images/_thumbs/{rel_str[len('images/'):]}"

CATEGORY_ORDER = [
    ("images", "Images", IMAGE_EXTENSIONS),
    ("data", "Data", {".csv", ".json", ".txt", ".xml", ".apk"}),
    ("css", "CSS", {".css", ".min.css"}),
    ("js", "JavaScript", {".js", ".min.js"}),
    ("md", "Markdown", {".md"}),
]


def load_config(project_root: Path) -> Dict:
    config_path = project_root / "config.toml"
    if not config_path.exists() or tomllib is None:
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Could not read config.toml: {e}")
        return {}


def get_base_url(project_root: Path) -> str:
    config = load_config(project_root)
    if "repository" in config and "base_url" in config["repository"]:
        return config["repository"]["base_url"].rstrip("/")
    return DEFAULT_BASE_URL


def ext_category(ext: str, rel_path: str) -> str:
    ext = ext.lower()
    top = rel_path.split("/")[0] if "/" in rel_path else rel_path
    if top == "images" and ext in IMAGE_EXTENSIONS:
        return "images"
    if top == "data":
        return "data"
    if top == "css":
        return "css"
    if top == "js":
        return "js"
    if top == "md":
        return "md"
    return "other"


def _dimensions_from_bytes(data: bytes, ext: str) -> Tuple[Optional[int], Optional[int]]:
    ext = ext.lower()
    if ext == ".webp" and len(data) >= 30 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        tag = data[12:16]
        if tag == b"VP8 " and len(data) >= 30:
            w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return w, h
        if tag == b"VP8L" and len(data) >= 25:
            bits = struct.unpack("<I", data[21:25])[0]
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if tag == b"VP8X" and len(data) >= 30:
            w = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
            h = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
            return w, h
    if ext in {".png", ".apng"} and len(data) >= 24 and data[0:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if ext in {".jpg", ".jpeg"} and len(data) >= 4 and data[0:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = struct.unpack(">H", data[i + 5 : i + 7])[0]
                w = struct.unpack(">H", data[i + 7 : i + 9])[0]
                return w, h
            if marker in (0xD8, 0xD9) or marker == 0x01:
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + seg_len
    return None, None


def image_dimensions(dist_file: Path) -> Tuple[Optional[int], Optional[int]]:
    """Pixel size of a raster image in dist/ (for masonry placeholders)."""
    if not dist_file.exists():
        return None, None
    ext = dist_file.suffix.lower()
    if ext in {".svg", ".gif"}:
        return None, None
    try:
        from PIL import Image

        with Image.open(dist_file) as im:
            w, h = im.size
            if w > 0 and h > 0:
                return int(w), int(h)
    except Exception:
        pass
    try:
        with open(dist_file, "rb") as f:
            head = f.read(512)
        return _dimensions_from_bytes(head, ext)
    except Exception:
        return None, None


def dedupe_key(rel_path: str) -> str:
    """Group rasters that share stem+parent dir (foo.jpg vs foo.webp)."""
    p = Path(rel_path)
    parent = str(p.parent)
    stem = p.stem
    return f"{parent}/{stem}".lower()


def git_last_modified_ts(project_root: Path, src_path: Path) -> Optional[int]:
    """Last commit time touching src_path (proxy for upload/update date)."""
    if not src_path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(src_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def src_candidates_for_dist(dist_rel: str) -> List[Path]:
    """Map a dist-relative path to possible src/ paths (handles webp siblings)."""
    p = Path(dist_rel)
    candidates = [Path("src") / dist_rel]
    if dist_rel.startswith("images/"):
        base = Path("src") / dist_rel
        stem = base.with_suffix("")
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
            candidates.append(stem.with_suffix(ext))
    elif dist_rel.startswith(("css/", "js/")):
        p = Path(dist_rel)
        name = p.name
        # Path.suffix is only ".css"/".js" for "*.min.css" — match full name instead
        if name.endswith(".min.css"):
            candidates.append(Path("src") / p.parent / name.replace(".min.css", ".css"))
        elif name.endswith(".min.js"):
            candidates.append(Path("src") / p.parent / name.replace(".min.js", ".js"))
    return candidates


def modified_timestamp(
    project_root: Path, dist_dir: Path, dist_paths: List[str]
) -> Tuple[int, Optional[str]]:
    """Best-effort modified time from git history on src/, then src/dist file mtime.

    Dist file mtime is only used as a last resort (e.g. generated outputs with no
    src mapping). Using dist mtime after every build would make all assets share
    the build time and break newest/oldest sorting.
    """
    best_ts = 0
    for dist_rel in dist_paths:
        for src_path in src_candidates_for_dist(dist_rel):
            if not src_path.exists():
                continue
            ts = git_last_modified_ts(project_root, src_path)
            if ts is None:
                ts = int(src_path.stat().st_mtime)
            if ts > best_ts:
                best_ts = ts
    if not best_ts:
        for dist_rel in dist_paths:
            dist_file = dist_dir / dist_rel
            if dist_file.exists():
                ts = int(dist_file.stat().st_mtime)
                if ts > best_ts:
                    best_ts = ts
    if not best_ts:
        return 0, None
    iso = datetime.fromtimestamp(best_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return best_ts, iso


def pick_primary(paths: List[str]) -> Tuple[str, List[str]]:
    """Choose primary URL path; return (primary, alternates)."""
    webp = [p for p in paths if p.lower().endswith(".webp")]
    if webp:
        primary = sorted(webp)[0]
        alts = [p for p in paths if p != primary]
        return primary, alts
    return sorted(paths)[0], paths[1:]


def scan_dist(dist_dir: Path) -> List[Path]:
    files: List[Path] = []
    if not dist_dir.exists():
        return files
    for root, _dirs, filenames in os.walk(dist_dir):
        for name in filenames:
            if name in EXCLUDE_NAMES:
                continue
            full = Path(root) / name
            try:
                rel = full.relative_to(dist_dir)
            except ValueError:
                continue
            rel_str = rel.as_posix()
            if is_thumb_asset_path(rel_str):
                continue
            # Skip site assets at dist root (handled separately)
            if len(rel.parts) == 1 and rel.suffix.lower() in {".html", ".css", ".js", ".json"}:
                if rel.name in EXCLUDE_NAMES:
                    continue
            files.append(rel)
    return sorted(files, key=lambda p: str(p).lower())


def build_assets(project_root: Path, dist_dir: Path, base_url: str) -> List[Dict]:
    raw_files = scan_dist(dist_dir)
    raster_exts = RASTER_DEDUPE_EXTENSIONS | {".webp"}

    groups: Dict[str, List[str]] = {}
    for rel in raw_files:
        rel_str = rel.as_posix()
        ext = rel.suffix.lower()
        if rel_str.startswith("images/") and ext in raster_exts:
            key = dedupe_key(rel_str)
            groups.setdefault(key, []).append(rel_str)

    processed: Set[str] = set()
    entries: List[Dict] = []

    for paths in sorted(groups.values(), key=lambda ps: ps[0].lower()):
        primary, alternates = pick_primary(paths)
        entries.append(_make_entry(primary, base_url, dist_dir, project_root, alternates, paths))
        processed.update(paths)

    for rel in raw_files:
        rel_str = rel.as_posix()
        if rel_str in processed:
            continue
        entries.append(_make_entry(rel_str, base_url, dist_dir, project_root, [], [rel_str]))

    return entries


def _make_entry(
    rel_str: str,
    base_url: str,
    dist_dir: Path,
    project_root: Path,
    alternate_paths: List[str],
    mtime_paths: List[str],
) -> Dict:
    full = dist_dir / rel_str
    p = Path(rel_str)
    ext = p.suffix.lower()
    name = p.stem
    folder = p.parent.as_posix() if p.parent != Path(".") else ""
    if folder.startswith("images/"):
        folder = folder[len("images/") :] or "(root)"
    elif folder in ("images",):
        folder = "(root)"
    else:
        folder = folder or "(root)"

    category = ext_category(ext, rel_str)
    is_image = ext in IMAGE_EXTENSIONS and rel_str.startswith("images/")

    size_bytes = full.stat().st_size if full.exists() else 0
    modified_ts, modified_at = modified_timestamp(project_root, dist_dir, mtime_paths)
    url = f"{base_url}/{rel_str}"

    alternates = []
    for alt in alternate_paths:
        alternates.append(
            {
                "path": alt,
                "url": f"{base_url}/{alt}",
                "ext": Path(alt).suffix.lower(),
            }
        )

    search_text = " ".join(
        filter(
            None,
            [
                name.lower(),
                rel_str.lower(),
                folder.lower().replace("(root)", "root"),
                ext.lstrip("."),
                category,
            ],
        )
    )

    width, height = None, None
    if is_image and full.exists():
        width, height = image_dimensions(full)

    entry = {
        "name": name,
        "path": rel_str,
        "url": url,
        "ext": ext,
        "is_image": is_image,
        "folder": folder,
        "category": category,
        "size_bytes": size_bytes,
        "modified_ts": modified_ts,
        "modified_at": modified_at,
        "search_text": search_text,
        "alternates": alternates,
    }
    if width and height:
        entry["width"] = width
        entry["height"] = height

    if is_image and ext in RASTER_DEDUPE_EXTENSIONS | {".webp"}:
        thumb_rel = thumb_path_for_asset(rel_str)
        if thumb_rel:
            thumb_file = dist_dir / thumb_rel
            if thumb_file.exists():
                tw, th = image_dimensions(thumb_file)
                entry["thumb_url"] = f"{base_url}/{thumb_rel}"
                entry["thumb_bytes"] = thumb_file.stat().st_size
                if tw and th:
                    entry["thumb_width"] = tw
                    entry["thumb_height"] = th

    return entry


def group_by_category(assets: List[Dict]) -> List[Dict]:
    by_id: Dict[str, List[Dict]] = {cid: [] for cid, _, _ in CATEGORY_ORDER}
    by_id["other"] = []

    for asset in assets:
        cat = asset.get("category", "other")
        if cat not in by_id:
            by_id["other"].append(asset)
        else:
            by_id[cat].append(asset)

    categories = []
    for cid, title, _exts in CATEGORY_ORDER:
        items = sorted(by_id.get(cid, []), key=lambda a: a["path"].lower())
        if items:
            categories.append({"id": cid, "title": title, "assets": items})

    other = sorted(by_id.get("other", []), key=lambda a: a["path"].lower())
    if other:
        categories.append({"id": "other", "title": "Other", "assets": other})

    return categories


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "dist"
    base_url = get_base_url(project_root)

    if not dist_dir.exists():
        print("ERROR: dist/ not found. Run ./build.sh first.")
        return 1

    assets = build_assets(project_root, dist_dir, base_url)
    categories = group_by_category(assets)

    stats: Dict[str, int] = {"total": len(assets)}
    for cat in categories:
        stats[cat["id"]] = len(cat["assets"])

    commit = os.environ.get("GITHUB_SHA", "")[:7] or None
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "base_url": base_url,
        "generated_at": generated_at,
        "commit": commit,
        "stats": stats,
        "categories": categories,
    }

    out_path = dist_dir / "assets.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({stats['total']} assets, {len(categories)} categories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
