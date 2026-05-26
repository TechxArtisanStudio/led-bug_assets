# LED-Bug Assets

Static asset CDN and team asset browser for the LED-Bug project. Built from the [static-assets-template](https://github.com/youyoubilly/static-assets-template) pattern.

**CDN base URL:** [https://assets.led-bug.com](https://assets.led-bug.com)

Public GitHub repository for the LED-Bug static asset CDN. Internal build-time tooling and team-only scripts live in the private **`lb-site-dev-tool`** repo; the public website is [**led-bug**](https://github.com/TechxArtisanStudio/led-bug).

## Overview

- **Automated build pipeline**: WebP conversion, CSS/JS minification, preview thumbnails
- **GitHub Actions**: Deploy `dist/` to GitHub Pages (`gh-pages`) on push to `main`
- **URL generation**: Markdown link lists in `links/`
- **Asset browser**: Password-gated gallery at the site root (search, filter, copy CDN links)
- **Configuration**: `config.toml`

## Quick Start

See [**SETUP.md**](SETUP.md) for GitHub Pages, DNS, and password gate setup.

### Local build

```bash
pip install -r requirements.txt
npm install -g uglify-js csso-cli
brew install webp   # macOS

./build.sh
python scripts/generate_url.py
python scripts/generate_manifest.py

python -m http.server 8080 --directory dist
# Open http://localhost:8080/
```

## Project Structure

```
led-bug_assets/
├── .github/workflows/deploy.yml
├── build.sh
├── config.toml
├── requirements.txt
├── scripts/
│   ├── generate_manifest.py
│   ├── generate_url.py
│   ├── generate_thumbs.py
│   ├── upload_images.py
│   └── image_resizer.py
├── src/
│   ├── images/          # Image assets (source of truth)
│   ├── css/             # CDN CSS
│   ├── js/              # CDN JS
│   ├── data/            # Data files (JSON, APK, etc.)
│   ├── md/              # Markdown files
│   └── site/            # Asset browser UI
├── links/               # Generated URL markdown (after build)
└── dist/                # Build output (gitignored)
```

## Adding Assets

- `src/images/` — PNG, JPG, JPEG (auto WebP), SVG, GIF, WebP
- `src/css/` — minified to `.min.css`
- `src/js/` — minified to `.min.js`
- `src/data/` — copied as-is (CSV, JSON, TXT, XML, APK)

Bulk import helper:

```bash
python scripts/upload_images.py /path/to/folder
```

## Asset Browser

- Search, category filters, sort, masonry/comfortable/compact views
- Copy raw URL, markdown link, or image syntax
- Password gate on the homepage only (not CDN URLs)

Change the gate password before production — see SETUP.md.

## Configuration

Edit `config.toml`:

```toml
[repository]
base_url = "https://assets.led-bug.com"
```

## License

MIT License — see LICENSE file.
