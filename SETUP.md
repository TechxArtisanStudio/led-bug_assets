# LED-Bug Assets — Setup Guide

## Prerequisites

- GitHub repository: `TechxArtisanStudio/led-bug_assets`
- Python 3.11+
- For local builds: `cwebp` (`brew install webp`), `uglify-js`, `csso-cli` (global npm)

## Step 1: Configure `config.toml`

Already set for LED-Bug:

```toml
[repository]
base_url = "https://assets.led-bug.com"
```

## Step 2: GitHub Pages

1. Push to the `main` branch
2. Repository **Settings → Pages**
3. **Source**: Deploy from branch **`gh-pages`**, folder **`/` (root)**
4. The workflow in `.github/workflows/deploy.yml` builds and pushes `dist/` to `gh-pages` on each push to `main`

## Step 3: Custom Domain (DNS)

1. Add a **CNAME** record: host `assets` on `led-bug.com` → **`TechxArtisanStudio.github.io`** (must match the GitHub org name; `techxartisan.github.io` is a different account and will 404)
2. In **Settings → Pages**, set custom domain to `assets.led-bug.com`
3. After deploy, `gh-pages` includes `CNAME` with `assets.led-bug.com` (written automatically in CI from `config.toml`)

## Step 4: Password Gate

The asset browser at `/` is protected by a shared team password (frontend only — CDN URLs remain public).

1. Choose a team password
2. Compute its SHA-256 hash:

```bash
echo -n 'YOUR_PASSWORD' | shasum -a 256
```

3. Update `PASSWORD_HASH` in `src/site/gate.js` with the hex output
4. Commit and push

Use **Log out** on shared machines. “Remember on this device” stores access for 30 days in `localStorage`.

## Step 5: Add Assets

Place files under `src/images/`, `src/data/`, etc., then push to `main`:

```bash
./build.sh
python scripts/generate_url.py
python scripts/generate_manifest.py
```

Or let CI run the full pipeline on push.

### Upload helper

```bash
python scripts/upload_images.py /path/to/images
```

Filename keywords route into subfolders: `sr`, `mini`, `product`, `icon`, `blog`, `branding` (see `SUBDIR_RULES` in `scripts/upload_images.py`).

## Manual Setup Checklist

- [ ] `config.toml` `base_url` is correct
- [ ] GitHub Pages source = GitHub Actions
- [ ] DNS CNAME for `assets.led-bug.com`
- [ ] Password hash set in `src/site/gate.js`
- [ ] First push to `main` succeeded in Actions
- [ ] `https://assets.led-bug.com/` loads the browser

## Troubleshooting

**Build fails locally** — Install `webp`, `uglify-js`, `csso-cli`; run `chmod +x build.sh`.

**Empty asset grid** — Add files under `src/images/` (or other dirs) and rebuild; `dist/assets.json` is generated after `./build.sh`.

**Pages not updating** — Check Actions logs; confirm `dist/index.html` and `dist/assets.json` exist after build.
