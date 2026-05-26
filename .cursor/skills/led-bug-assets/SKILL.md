---
name: led-bug-assets
description: >-
  Upload images and static files to the LED-Bug CDN repo, run the build pipeline,
  and return live URLs at assets.led-bug.com. Use when working in led-bug_assets,
  when the user asks to upload/host assets, get CDN links, deploy media, or reference
  assets.led-bug.com.
---

# LED-Bug Assets CDN

Public static asset CDN for LED-Bug. Source lives in `src/`; CI builds `dist/` and deploys to GitHub Pages at **https://assets.led-bug.com**.

Related repos (sibling folders under `website/`):

| Repo | Role |
|------|------|
| **led-bug_assets** (this repo) | CDN + asset browser |
| **led-bug** | Marketing site at led-bug.com |
| **lb-site-dev-tool** | Private dev tooling (not for CDN uploads) |

## CDN URL rules

Read `config.toml` → `[repository].base_url` (default `https://assets.led-bug.com`).

| Source path | Deployed URL path | Notes |
|-------------|-------------------|-------|
| `src/images/**/{name}.png\|jpg\|jpeg` | `/images/**/{name}.webp` | Build converts to WebP; **link to `.webp`** |
| `src/images/**/{name}.svg\|gif\|webp` | `/images/**/{name}.{ext}` | No conversion |
| `src/css/**/{name}.css` | `/css/**/{name}.min.css` | Minified |
| `src/js/**/{name}.js` | `/js/**/{name}.min.js` | Minified |
| `src/data/**` | `/data/**` | Copied as-is (JSON, CSV, APK, etc.) |
| `src/md/**` | `/md/**` | Copied as-is |

**Formula:** `{base_url}/{deployed-path}` — e.g. `https://assets.led-bug.com/images/product/hero.webp`

PNG/JPG sources also exist in `dist/` after build, but prefer the `.webp` URL for site use.

## Primary workflow: upload images and return URLs

Use this when the user provides local image files or a folder.

### 1. Prepare environment (once per machine)

```bash
cd /path/to/led-bug_assets
pip install -r requirements.txt
# For full local build only: brew install webp && npm install -g uglify-js csso-cli
```

### 2. Upload with the helper script

```bash
python scripts/upload_images.py /path/to/image-or-folder
# Optional: --output links/my-batch.md
```

The script will:

- Optimize images (resize, compress)
- Copy into `src/images/` (auto-routed by filename keywords)
- Print a table with **predicted CDN URLs**
- Write markdown links to `links/new-links-<timestamp>.md`

**Subdirectory routing** (first match in filename, case-insensitive):

| Keyword in filename | Target folder |
|---------------------|---------------|
| `sr`, `led-bug_sr`, `sr_intro`, … | `src/images/sr/` |
| `mini`, `led-bug_mini`, `mini_intro`, … | `src/images/mini/` |
| `product` | `src/images/product/` |
| `branding`, `cover`, `favicon`, `logo` | `src/images/branding/` |
| `icon` | `src/images/icon/` |
| `blog` | `src/images/blog/` |
| (none) | `src/images/` (root) |

If the user specifies a folder, copy manually instead: `src/images/{subdir}/`.

### 3. Deploy to make URLs live

Push to `main` — GitHub Actions runs `./build.sh`, `generate_url.py`, `generate_manifest.py`, then deploys `dist/` to `gh-pages`.

```bash
git add src/images/ links/   # include links/ if generated
git commit -m "add images: <filenames>"
git push origin main
```

Only commit when the user asks. After push, URLs are live within ~1–2 minutes (check Actions tab if needed).

**Local preview** (optional, not required for deploy):

```bash
./build.sh && python scripts/generate_manifest.py
python -m http.server 8080 --directory dist
```

### 4. Return URLs to the user

Always give **full deployed CDN URLs**, not local paths. Format:

```
https://assets.led-bug.com/images/{subdir}/{filename}.webp
```

Also offer copy-paste variants when useful:

```markdown
![alt text](https://assets.led-bug.com/images/product/hero.webp)
```

```html
<img src="https://assets.led-bug.com/images/product/hero.webp" alt="hero" />
```

If upload just ran, URLs from script output are correct **after deploy**. Tell the user deploy is pending until push completes.

## Other asset types

| Type | Action | Example URL |
|------|--------|-------------|
| Data (JSON, CSV, APK) | Copy to `src/data/` | `https://assets.led-bug.com/data/file.json` |
| CSS | Copy to `src/css/` | `https://assets.led-bug.com/css/style.min.css` |
| JS | Copy to `src/js/` | `https://assets.led-bug.com/js/app.min.js` |
| Markdown | Copy to `src/md/` | `https://assets.led-bug.com/md/doc.md` |

Then commit, push to `main`, and return the URL using the rules above.

## Look up existing assets

1. **Generated link lists** — `links/webp.md`, `links/svg.md`, `links/data.md`, etc. (regenerated on CI)
2. **Asset browser** — https://assets.led-bug.com/ (password-gated UI; CDN URLs themselves are public)
3. **Regenerate locally:**

```bash
python scripts/generate_url.py          # predict from src/
python scripts/generate_url.py --dist   # actual files in dist/ after build
```

## Agent checklist

When helping upload assets:

- [ ] Confirm files are in `src/` (via `upload_images.py` or manual copy)
- [ ] Use `.webp` URLs for PNG/JPG/JPEG sources
- [ ] Commit + push to `main` if user wants live URLs (ask before committing)
- [ ] Return full `https://assets.led-bug.com/...` URLs in the response
- [ ] Do not put CDN assets in `led-bug` or `lb-site-dev-tool` — they belong here

## Do not

- Commit `dist/` (gitignored; CI builds it)
- Change `config.toml` base_url without team approval
- Put secrets or private content here (public repo + public CDN URLs)
- Edit `src/site/gate.js` password unless the user explicitly asks

## Troubleshooting

| Issue | Fix |
|-------|-----|
| URL 404 after upload | Push to `main` and wait for Actions; verify file under `src/images/` |
| Wrong subfolder | Rename file to include routing keyword, or move manually in `src/images/` |
| `upload_images.py` import error | `pip install -r requirements.txt` |
| Local build fails | Install `cwebp` (`brew install webp`); CI still works if you only push source files |

See [SETUP.md](../../../SETUP.md) and [README.md](../../../README.md) for DNS, GitHub Pages, and password gate setup.
