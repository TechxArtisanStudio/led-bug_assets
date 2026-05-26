(function () {
    'use strict';

    const ICON_LINK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>';
    const ICON_MD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
    const ICON_IMG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
    const ICON_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

    const CATEGORY_LABELS = {
        images: 'Image',
        data: 'Data',
        css: 'CSS',
        js: 'JS',
        md: 'MD',
        other: 'Other',
    };

    const VIEW_STORAGE_KEY = 'ledbug_assets_view_v2';
    const SORT_STORAGE_KEY = 'ledbug_assets_sort';

    const SORT_LABELS = {
        name: 'Name A–Z',
        'date-desc': 'Newest first',
        'date-asc': 'Oldest first',
    };

    const VIEW_MODES = ['masonry', 'comfortable', 'compact'];
    const MASONRY_GAP = 18;
    const MASONRY_MIN_COL = 200;
    const MASONRY_MAX_COL = 300;
    const MASONRY_BODY_FALLBACK = 52;
    const MASONRY_FILE_ASPECT = 0.75;
    const THUMB_ROOT_MARGIN = {
        compact: '150px 0px',
        comfortable: '250px 0px',
        masonry: '400px 0px',
    };

    let manifest = null;
    let masonryLayoutRaf = null;
    let masonryPendingMinIdx = null;
    let masonryCards = [];
    let masonryGeometry = null;
    let masonryHeightCache = new WeakMap();
    let thumbObserver = null;
    let gridResizeObserver = null;
    let viewMode = 'masonry';
    let sortMode = 'name';
    let activeCategory = 'all';
    let searchQuery = '';
    let debounceTimer = null;
    let lightboxUrl = '';

    const statsBar = document.getElementById('stats-bar');
    const domainLink = document.getElementById('domain-link');
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    const categoryTabs = document.getElementById('category-tabs');
    const statusEl = document.getElementById('status');
    const gridEl = document.getElementById('grid');
    const emptyState = document.getElementById('empty-state');
    const scrollTopBtn = document.getElementById('scroll-top');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const lightboxOpen = document.getElementById('lightbox-open');
    const lightboxCopy = document.getElementById('lightbox-copy');
    const viewToggle = document.getElementById('view-toggle');
    const sortSelect = document.getElementById('sort-select');

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /** Encode path segments so +, &, spaces in filenames load correctly. */
    function toMediaUrl(url) {
        try {
            const u = new URL(url);
            u.pathname = u.pathname
                .split('/')
                .map((seg, i) => (i === 0 ? seg : encodeURIComponent(decodeURIComponent(seg))))
                .join('/');
            return u.href;
        } catch {
            return url;
        }
    }

    /** Grid thumbnails: small preview first, then full URL on error. */
    function thumbCandidateUrls(asset) {
        const seen = new Set();
        const list = [];
        const add = (url) => {
            if (url && !seen.has(url)) {
                seen.add(url);
                list.push(url);
            }
        };
        add(asset.thumb_url);
        add(asset.url);
        (asset.alternates || []).forEach((a) => add(a.url));
        return list;
    }

    /** Lightbox / full preview: always prefer full-size CDN URL. */
    function previewCandidateUrls(asset) {
        const seen = new Set();
        const list = [];
        const add = (url) => {
            if (url && !seen.has(url)) {
                seen.add(url);
                list.push(url);
            }
        };
        add(asset.url);
        (asset.alternates || []).forEach((a) => add(a.url));
        return list;
    }

    function getThumbRootMargin() {
        return THUMB_ROOT_MARGIN[viewMode] || THUMB_ROOT_MARGIN.comfortable;
    }

    function assetAspectRatio(asset) {
        if (asset.width && asset.height) return asset.width / asset.height;
        return 16 / 9;
    }

    function applyThumbPlaceholder(img, asset) {
        const wrap = img.closest('.thumb-wrap');
        if (wrap && asset.is_image) {
            if (viewMode === 'masonry') {
                wrap.style.aspectRatio = '';
            } else {
                const w = asset.width || 16;
                const h = asset.height || 9;
                wrap.style.aspectRatio = `${w} / ${h}`;
            }
        }
        img.classList.add('thumb--loading');
        img.removeAttribute('src');
        img.dataset.candidates = JSON.stringify(thumbCandidateUrls(asset).map(toMediaUrl));
    }

    function loadThumbFromDataset(img) {
        let candidates = [];
        try {
            candidates = JSON.parse(img.dataset.candidates || '[]');
        } catch {
            candidates = [];
        }
        let attempt = 0;
        const onFail = () => {
            if (attempt < candidates.length) {
                img.src = candidates[attempt++];
            } else {
                img.classList.add('thumb--error');
                img.classList.remove('thumb--loading');
                onThumbLoaded(img);
            }
        };
        const onSuccess = () => {
            img.classList.remove('thumb--loading');
            img.removeEventListener('error', onFail);
            onThumbLoaded(img);
        };
        img.addEventListener('error', onFail);
        img.addEventListener('load', onSuccess, { once: true });
        if (candidates.length) {
            img.src = candidates[attempt++];
        } else {
            onFail();
        }
    }

    function onThumbLoaded(img) {
        if (viewMode !== 'masonry') return;
        const card = img.closest('.asset-card');
        if (card) scheduleMasonryLayout(card);
    }

    function resetThumbObserver() {
        if (thumbObserver) {
            thumbObserver.disconnect();
            thumbObserver = null;
        }
    }

    function initThumbObserver() {
        resetThumbObserver();
        thumbObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    const img = entry.target;
                    thumbObserver.unobserve(img);
                    if (!img.src && img.dataset.candidates) {
                        loadThumbFromDataset(img);
                    }
                });
            },
            { root: null, rootMargin: getThumbRootMargin(), threshold: 0.01 }
        );
    }

    function observeThumb(img, asset) {
        applyThumbPlaceholder(img, asset);
        if (!thumbObserver) return;
        const card = img.closest('.asset-card');
        if (card && !card.classList.contains('hidden')) {
            thumbObserver.observe(img);
        }
    }

    function refreshThumbObservation() {
        if (!thumbObserver) return;
        gridEl.querySelectorAll('.thumb').forEach((img) => {
            thumbObserver.unobserve(img);
            const card = img.closest('.asset-card');
            if (card && !card.classList.contains('hidden') && !img.src && img.dataset.candidates) {
                thumbObserver.observe(img);
            }
        });
    }

    function clearMasonryPositions() {
        gridEl.querySelectorAll('.asset-card').forEach((card) => {
            card.style.position = '';
            card.style.left = '';
            card.style.top = '';
            card.style.width = '';
        });
        gridEl.style.height = '';
        masonryCards = [];
        masonryGeometry = null;
        masonryHeightCache = new WeakMap();
    }

    function getMasonryOffsetX(colWidth, cols, gap) {
        const totalWidth = cols * colWidth + (cols - 1) * gap;
        return Math.max(0, (gridEl.clientWidth - totalWidth) / 2);
    }

    function getCardHeightForLayout(card, colWidth, preferLive) {
        if (preferLive) {
            const live = card.offsetHeight;
            if (live > 0) {
                masonryHeightCache.set(card, live);
                return live;
            }
        }
        const cached = masonryHeightCache.get(card);
        if (cached) return cached;
        const h = measureCardHeight(card, colWidth);
        masonryHeightCache.set(card, h);
        return h;
    }

    function positionMasonryRange(cards, startIdx, colWidth, cols, gap, offsetX, colHeights) {
        for (let i = startIdx; i < cards.length; i++) {
            const card = cards[i];
            const preferLive = i === startIdx;
            const h = getCardHeightForLayout(card, colWidth, preferLive);

            let col = 0;
            for (let j = 1; j < cols; j++) {
                if (colHeights[j] < colHeights[col]) col = j;
            }

            const left = offsetX + col * (colWidth + gap);
            const top = colHeights[col];

            card.style.position = 'absolute';
            card.style.width = colWidth + 'px';
            card.style.left = left + 'px';
            card.style.top = top + 'px';

            colHeights[col] += h + gap;
        }
        gridEl.style.height = Math.max(...colHeights, 0) + 'px';
    }

    function layoutMasonryFull() {
        if (viewMode !== 'masonry' || !manifest) return;
        const cards = [...gridEl.querySelectorAll('.asset-card:not(.hidden)')];
        masonryCards = cards;
        if (!cards.length) {
            gridEl.style.height = '0px';
            masonryGeometry = null;
            return;
        }

        const { colWidth, cols, gap } = getMasonryLayout();
        const offsetX = getMasonryOffsetX(colWidth, cols, gap);
        masonryGeometry = { colWidth, cols, gap, offsetX };
        masonryHeightCache = new WeakMap();
        positionMasonryRange(cards, 0, colWidth, cols, gap, offsetX, new Array(cols).fill(0));
    }

    function relayoutMasonryFromIndex(startIdx) {
        if (viewMode !== 'masonry' || !manifest) return;
        const cards = [...gridEl.querySelectorAll('.asset-card:not(.hidden)')];
        masonryCards = cards;
        if (!cards.length) {
            gridEl.style.height = '0px';
            masonryGeometry = null;
            return;
        }

        const { colWidth, cols, gap } = getMasonryLayout();
        if (startIdx < 0 || !masonryGeometry || masonryGeometry.colWidth !== colWidth) {
            layoutMasonryFull();
            return;
        }

        const offsetX = getMasonryOffsetX(colWidth, cols, gap);
        masonryGeometry = { colWidth, cols, gap, offsetX };
        const colHeights = new Array(cols).fill(0);

        for (let i = 0; i < startIdx; i++) {
            const h = getCardHeightForLayout(cards[i], colWidth);
            let col = 0;
            for (let j = 1; j < cols; j++) {
                if (colHeights[j] < colHeights[col]) col = j;
            }
            colHeights[col] += h + gap;
        }

        positionMasonryRange(cards, startIdx, colWidth, cols, gap, offsetX, colHeights);
    }

    function relayoutMasonryFromCard(changedCard) {
        const cards = masonryCards.length
            ? masonryCards
            : [...gridEl.querySelectorAll('.asset-card:not(.hidden)')];
        relayoutMasonryFromIndex(cards.indexOf(changedCard));
    }

    function scheduleMasonryLayout(changedCard) {
        if (viewMode !== 'masonry') return;
        if (changedCard) {
            const cards = masonryCards.length
                ? masonryCards
                : [...gridEl.querySelectorAll('.asset-card:not(.hidden)')];
            const idx = cards.indexOf(changedCard);
            if (idx >= 0) {
                masonryPendingMinIdx =
                    masonryPendingMinIdx === null ? idx : Math.min(masonryPendingMinIdx, idx);
            }
        }
        if (masonryLayoutRaf) return;
        masonryLayoutRaf = requestAnimationFrame(() => {
            masonryLayoutRaf = null;
            const startIdx = masonryPendingMinIdx;
            masonryPendingMinIdx = null;
            if (startIdx !== null && masonryCards.length) {
                relayoutMasonryFromIndex(startIdx);
            } else {
                layoutMasonryFull();
            }
        });
    }

    function layoutMasonry() {
        layoutMasonryFull();
    }

    function getMasonryLayout() {
        const w = gridEl.clientWidth;
        let colWidth = MASONRY_MIN_COL;
        if (w >= 900) colWidth = 260;
        if (w >= 1200) colWidth = 280;
        colWidth = Math.min(MASONRY_MAX_COL, Math.max(MASONRY_MIN_COL, colWidth));
        const cols = Math.max(1, Math.floor((w + MASONRY_GAP) / (colWidth + MASONRY_GAP)));
        return { colWidth, cols, gap: MASONRY_GAP };
    }

    function estimateCardHeightFromCard(card, colWidth) {
        const w = parseInt(card.dataset.imgWidth, 10);
        const h = parseInt(card.dataset.imgHeight, 10);
        let bodyH = MASONRY_BODY_FALLBACK;
        const bodyEl = card.querySelector('.card-body');
        if (bodyEl && bodyEl.offsetHeight > 0) {
            bodyH = bodyEl.offsetHeight;
        }
        if (card.classList.contains('asset-card-image')) {
            if (w > 0 && h > 0) {
                let imgH = colWidth * (h / w);
                const maxH = window.innerHeight * 0.55;
                if (imgH > maxH) imgH = maxH;
                return imgH + bodyH;
            }
            return colWidth * (9 / 16) + bodyH;
        }
        return colWidth * MASONRY_FILE_ASPECT + bodyH;
    }

    function getMasonryMeasureGrid() {
        return document.getElementById('masonry-measure-grid');
    }

    function prepareMasonryMeasureClone(card, colWidth) {
        const clone = card.cloneNode(true);
        clone.style.position = 'static';
        clone.style.left = '';
        clone.style.top = '';
        clone.style.width = '100%';
        clone.classList.remove('hidden');
        const wrap = clone.querySelector('.thumb-wrap');
        if (wrap) {
            wrap.style.aspectRatio = '';
            if (card.classList.contains('asset-card-image')) {
                const w = parseInt(card.dataset.imgWidth, 10);
                const h = parseInt(card.dataset.imgHeight, 10);
                if (w > 0 && h > 0 && colWidth > 0) {
                    let imgH = colWidth * (h / w);
                    const maxH = window.innerHeight * 0.55;
                    if (imgH > maxH) imgH = maxH;
                    wrap.style.minHeight = Math.round(imgH) + 'px';
                }
            }
        }
        const thumb = clone.querySelector('.thumb');
        if (thumb) thumb.classList.remove('thumb--loading', 'thumb--error');
        return clone;
    }

    function measureCardHeight(card, colWidth) {
        const grid = getMasonryMeasureGrid();
        if (!grid) {
            return estimateCardHeightFromCard(card, colWidth);
        }
        grid.style.width = colWidth + 'px';
        grid.innerHTML = '';
        const clone = prepareMasonryMeasureClone(card, colWidth);
        grid.appendChild(clone);
        const h = clone.offsetHeight;
        grid.innerHTML = '';
        if (h > 0) return h;
        return estimateCardHeightFromCard(card, colWidth);
    }

    function refreshThumbAspectRatios() {
        gridEl.querySelectorAll('.thumb-wrap').forEach((wrap) => {
            const card = wrap.closest('.asset-card');
            if (!card || !card.classList.contains('asset-card-image')) return;
            if (viewMode === 'masonry') {
                wrap.style.aspectRatio = '';
            } else {
                const w = parseInt(card.dataset.imgWidth, 10) || 16;
                const h = parseInt(card.dataset.imgHeight, 10) || 9;
                wrap.style.aspectRatio = `${w} / ${h}`;
            }
        });
    }

    function initGridResizeObserver() {
        if (gridResizeObserver) gridResizeObserver.disconnect();
        gridResizeObserver = new ResizeObserver(() => {
            if (viewMode === 'masonry') scheduleMasonryLayout();
        });
        gridResizeObserver.observe(gridEl);
    }

    function formatSize(bytes) {
        if (!bytes || bytes <= 0) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function formatBuildTime(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return iso;
        }
    }

    function formatAssetDate(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
            });
        } catch {
            return '';
        }
    }

    function fileEmoji(ext) {
        if (ext === '.apk') return '📱';
        if (ext === '.json' || ext === '.csv') return '📊';
        if (ext === '.css') return '🎨';
        if (ext === '.js') return '⚡';
        if (ext === '.md') return '📝';
        return '📄';
    }

    function fileExtLabel(ext) {
        const labels = {
            '.json': 'JSON',
            '.csv': 'CSV',
            '.apk': 'APK',
            '.txt': 'TXT',
            '.xml': 'XML',
        };
        if (labels[ext]) return labels[ext];
        const bare = (ext || '').replace(/^\./, '');
        return bare ? bare.toUpperCase() : 'FILE';
    }

    function filePreviewLabel(asset) {
        if (asset.category === 'data') return fileExtLabel(asset.ext);
        const byCategory = { css: 'CSS', js: 'JS', md: 'MD' };
        if (byCategory[asset.category]) return byCategory[asset.category];
        return fileExtLabel(asset.ext);
    }

    async function copyText(text, btn) {
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        if (btn) {
            btn.classList.add('copied');
            setTimeout(() => btn.classList.remove('copied'), 1500);
        }
    }

    function renderStats() {
        if (!manifest) return;
        const s = manifest.stats || {};
        const parts = [
            `<span class="stat-chip"><strong>${s.total || 0}</strong> assets</span>`,
            `<span class="stat-chip">${s.images || 0} images</span>`,
            `<span class="stat-chip">${s.data || 0} data</span>`,
        ];
        if (manifest.generated_at) {
            const built = `Built ${formatBuildTime(manifest.generated_at)}`;
            const title = manifest.commit ? `${built} · ${manifest.commit}` : built;
            parts.push(
                `<span class="stat-chip stat-chip-muted" title="${escapeHtml(title)}">${escapeHtml(built)}</span>`
            );
        }
        statsBar.innerHTML = parts.join('');

        if (manifest.base_url && domainLink) {
            domainLink.innerHTML = `<a href="${escapeHtml(manifest.base_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(manifest.base_url.replace(/^https?:\/\//, ''))}</a>`;
        }
    }

    function setViewMode(mode) {
        if (!VIEW_MODES.includes(mode)) mode = 'masonry';
        const prev = viewMode;
        viewMode = mode;
        try {
            localStorage.setItem(VIEW_STORAGE_KEY, viewMode);
        } catch {
            /* ignore */
        }
        gridEl.classList.remove('view-compact', 'view-masonry');
        if (viewMode === 'compact') gridEl.classList.add('view-compact');
        if (viewMode === 'masonry') gridEl.classList.add('view-masonry');

        if (prev === 'masonry' && viewMode !== 'masonry') {
            clearMasonryPositions();
        }
        if (viewMode === 'masonry') {
            scheduleMasonryLayout();
        } else {
            clearMasonryPositions();
        }

        if (viewToggle) {
            viewToggle.querySelectorAll('.view-btn').forEach((btn) => {
                const active = btn.dataset.view === viewMode;
                btn.classList.toggle('active', active);
                btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
        }
        refreshThumbAspectRatios();
        initThumbObserver();
        refreshThumbObservation();
    }

    function compareAssets(a, b) {
        const tsA = Number(a.modified_ts) || 0;
        const tsB = Number(b.modified_ts) || 0;
        if (sortMode === 'date-desc') {
            return tsB - tsA || a.path.localeCompare(b.path);
        }
        if (sortMode === 'date-asc') {
            return tsA - tsB || a.path.localeCompare(b.path);
        }
        return a.path.localeCompare(b.path);
    }

    function collectAssets() {
        const list = [];
        (manifest.categories || []).forEach((cat) => {
            (cat.assets || []).forEach((asset) => {
                asset.category = cat.id;
                list.push(asset);
            });
        });
        list.sort(compareAssets);
        return list;
    }

    function setSortMode(mode) {
        if (!['name', 'date-desc', 'date-asc'].includes(mode)) mode = 'name';
        sortMode = mode;
        try {
            localStorage.setItem(SORT_STORAGE_KEY, sortMode);
        } catch {
            /* ignore */
        }
        if (sortSelect) sortSelect.value = sortMode;
    }

    function initSortSelect() {
        try {
            const saved = localStorage.getItem(SORT_STORAGE_KEY);
            if (saved && ['name', 'date-desc', 'date-asc'].includes(saved)) {
                sortMode = saved;
            }
        } catch {
            /* ignore */
        }
        setSortMode(sortMode);
        if (!sortSelect) return;
        sortSelect.addEventListener('change', () => {
            setSortMode(sortSelect.value);
            renderGrid();
            scrollToResults();
        });
    }

    function initViewToggle() {
        try {
            const saved = localStorage.getItem(VIEW_STORAGE_KEY);
            if (saved && VIEW_MODES.includes(saved)) {
                viewMode = saved;
            }
        } catch {
            /* ignore */
        }
        setViewMode(viewMode);
        if (!viewToggle) return;
        viewToggle.querySelectorAll('.view-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (btn.dataset.view !== viewMode) {
                    setViewMode(btn.dataset.view);
                }
            });
        });
    }

    function renderTabs() {
        if (!manifest) return;
        const cats = manifest.categories || [];
        let html = `<button type="button" class="tab-btn active" data-category="all" role="tab" aria-selected="true">All <span class="count">${manifest.stats?.total || 0}</span></button>`;
        cats.forEach((cat) => {
            const count = cat.assets?.length || 0;
            html += `<button type="button" class="tab-btn" data-category="${escapeHtml(cat.id)}" role="tab" aria-selected="false">${escapeHtml(cat.title)} <span class="count">${count}</span></button>`;
        });
        categoryTabs.innerHTML = html;
        categoryTabs.querySelectorAll('.tab-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                categoryTabs.querySelectorAll('.tab-btn').forEach((b) => {
                    b.classList.remove('active');
                    b.setAttribute('aria-selected', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-selected', 'true');
                activeCategory = btn.dataset.category;
                applyFilters(true);
            });
        });
    }

    function buildActionsHtml(asset, isImage, extraClass) {
        const cls = extraClass ? `card-actions ${extraClass}` : 'card-actions';
        const mdLink = `[${asset.name}](${asset.url})`;
        const mdImg = `![${asset.name}](${asset.url})`;
        let html = `<div class="${cls}" data-md-link="${escapeHtml(mdLink)}" data-md-img="${escapeHtml(mdImg)}">`;
        html += `<button type="button" class="icon-btn" data-copy="url" title="Copy URL" aria-label="Copy URL">${ICON_LINK}</button>`;
        html += `<button type="button" class="icon-btn" data-copy="md" title="Copy markdown link" aria-label="Copy markdown link">${ICON_MD}</button>`;
        if (isImage) {
            html += `<button type="button" class="icon-btn" data-copy="img" title="Copy markdown image" aria-label="Copy markdown image">${ICON_IMG}</button>`;
        }
        html += `<a class="icon-btn" href="${escapeHtml(asset.url)}" target="_blank" rel="noopener noreferrer" title="Open in new tab" aria-label="Open in new tab">${ICON_OPEN}</a>`;
        html += `</div>`;
        return { html, mdLink, mdImg };
    }

    function buildCard(asset) {
        const isImage = asset.is_image;
        const displayPath = '/' + asset.path;
        const sizeLabel = formatSize(asset.size_bytes);
        const catLabel = CATEGORY_LABELS[asset.category] || asset.category;
        const cardClass = isImage ? 'asset-card asset-card-image' : 'asset-card asset-card-file';

        const dimAttrs =
            asset.width && asset.height
                ? ` data-img-width="${asset.width}" data-img-height="${asset.height}"`
                : '';
        let html = `<article class="${cardClass}" data-path="${escapeHtml(asset.path.toLowerCase())}" data-category="${escapeHtml(asset.category)}" data-search="${escapeHtml(asset.search_text || '')}"${dimAttrs}>`;

        const overlayActions = buildActionsHtml(asset, isImage, 'card-actions--overlay');

        if (isImage) {
            html += `<div class="card-media">`;
            html += `<button type="button" class="thumb-wrap" data-preview="${escapeHtml(asset.url)}" aria-label="Preview ${escapeHtml(asset.name)}">`;
            html += `<img class="thumb" alt="${escapeHtml(asset.name)}" loading="lazy" decoding="async">`;
            html += `</button>`;
            html += overlayActions.html;
            html += `</div>`;
        } else {
            html += `<div class="card-media card-media--file">`;
            html += `<div class="file-preview" data-ext="${escapeHtml(asset.ext)}" data-cat="${escapeHtml(asset.category)}">`;
            html += `<span class="file-preview-ext">${escapeHtml(filePreviewLabel(asset))}</span>`;
            html += `<span class="file-preview-icon" aria-hidden="true">${fileEmoji(asset.ext)}</span>`;
            html += `</div>`;
            html += overlayActions.html;
            html += `</div>`;
        }

        html += `<div class="card-body">`;
        html += `<div class="card-header-row">`;
        html += `<div class="card-name" title="${escapeHtml(asset.name + ' — ' + displayPath)}">${escapeHtml(asset.name)}</div>`;
        html += `<span class="category-badge" data-cat="${escapeHtml(asset.category)}">${escapeHtml(catLabel)}</span>`;
        html += `</div>`;

        const metaParts = [];
        if (asset.modified_at) metaParts.push(formatAssetDate(asset.modified_at));
        if (asset.folder && asset.folder !== '(root)') metaParts.push(asset.folder);
        if (sizeLabel) metaParts.push(sizeLabel);
        if (metaParts.length) {
            html += `<div class="card-meta">${escapeHtml(metaParts.join(' · '))}</div>`;
        }

        html += `<code class="card-path" title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}</code>`;

        if (asset.alternates && asset.alternates.length > 0) {
            const alt = asset.alternates[0];
            html += `<span class="alt-chip"><a href="${escapeHtml(alt.url)}" target="_blank" rel="noopener noreferrer">Also as ${escapeHtml(alt.ext)}</a></span>`;
        }

        html += `</div></article>`;

        const el = document.createElement('div');
        el.innerHTML = html;
        const card = el.firstElementChild;

        card.querySelectorAll('.card-actions').forEach((actionsEl) => {
            actionsEl.querySelectorAll('[data-copy]').forEach((btn) => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const kind = btn.dataset.copy;
                    let text = asset.url;
                    if (kind === 'md') text = overlayActions.mdLink;
                    if (kind === 'img') text = overlayActions.mdImg;
                    copyText(text, btn);
                });
            });
        });

        const thumb = card.querySelector('.thumb');
        if (thumb) observeThumb(thumb, asset);

        const previewBtn = card.querySelector('[data-preview]');
        if (previewBtn) {
            previewBtn.addEventListener('click', () => {
                const urls = previewCandidateUrls(asset);
                openLightbox(
                    urls[0] || asset.url,
                    asset.name,
                    displayPath,
                    urls.slice(1),
                    asset.thumb_url
                );
            });
        }

        return card;
    }

    function scrollToResults() {
        const sticky = document.querySelector('.toolbar-sticky');
        if (sticky) {
            const top = sticky.getBoundingClientRect().bottom + window.scrollY - 8;
            window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        }
    }

    function applyFilters(scroll) {
        if (!manifest) return;
        const cards = gridEl.querySelectorAll('.asset-card');
        let visible = 0;
        cards.forEach((card) => {
            const cat = card.dataset.category || '';
            const search = card.dataset.search || '';
            let show = true;
            if (activeCategory !== 'all' && cat !== activeCategory) show = false;
            if (searchQuery && !search.includes(searchQuery)) show = false;
            card.classList.toggle('hidden', !show);
            if (show) visible++;
        });

        const hasResults = visible > 0;
        emptyState.classList.toggle('hidden', hasResults);
        gridEl.classList.toggle('hidden', !hasResults);

        let statusText = hasResults
            ? `Showing ${visible} of ${manifest.stats?.total || visible} assets`
            : 'No assets match your filters.';
        if (searchQuery) statusText += ` · “${searchQuery}”`;
        if (activeCategory !== 'all') {
            const label = CATEGORY_LABELS[activeCategory] || activeCategory;
            statusText += ` · ${label} only`;
        }
        if (sortMode !== 'name' && SORT_LABELS[sortMode]) {
            statusText += ` · ${SORT_LABELS[sortMode]}`;
        }
        statusEl.textContent = statusText;
        statusEl.classList.toggle('error', !hasResults);

        if (viewMode === 'masonry') scheduleMasonryLayout();
        refreshThumbObservation();
        if (scroll) scrollToResults();
    }

    function renderGrid() {
        if (!manifest) return;
        resetThumbObserver();
        initThumbObserver();
        gridEl.innerHTML = '';
        const fragment = document.createDocumentFragment();

        collectAssets().forEach((asset) => {
            fragment.appendChild(buildCard(asset));
        });

        gridEl.appendChild(fragment);
        applyFilters(false);
        refreshThumbObservation();
        if (viewMode === 'masonry') scheduleMasonryLayout();
    }

    function openLightbox(url, name, path, moreUrls, thumbUrl) {
        const candidates = [url, ...(moreUrls || [])]
            .filter(Boolean)
            .map(toMediaUrl);
        const fullUrl = candidates[0] || toMediaUrl(url);
        lightboxUrl = url;
        lightboxImg.alt = name || '';
        lightboxCaption.textContent = path ? name + ' — ' + path : name;
        lightboxOpen.href = fullUrl;
        lightbox.classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        let attempt = 0;
        const tryNext = () => {
            attempt += 1;
            if (attempt < candidates.length) {
                lightboxImg.src = candidates[attempt];
                lightboxOpen.href = candidates[attempt];
            }
        };

        lightboxImg.onerror = tryNext;
        lightboxImg.onload = () => {
            if (lightboxImg.src === fullUrl) {
                lightboxImg.onerror = null;
            }
        };

        const previewThumb = thumbUrl && thumbUrl !== url ? toMediaUrl(thumbUrl) : null;
        if (previewThumb) {
            lightboxImg.src = previewThumb;
            const fullImg = new Image();
            fullImg.onload = () => {
                lightboxImg.src = fullUrl;
                lightboxImg.onerror = tryNext;
            };
            fullImg.onerror = () => {
                lightboxImg.src = fullUrl;
            };
            fullImg.src = fullUrl;
        } else if (candidates.length) {
            lightboxImg.src = fullUrl;
        }
    }

    function closeLightbox() {
        lightbox.classList.add('hidden');
        lightboxImg.src = '';
        lightboxUrl = '';
        document.body.style.overflow = '';
    }

    lightbox.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) closeLightbox();
    });
    lightboxCopy.addEventListener('click', () => copyText(lightboxUrl, lightboxCopy));

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === '/' && document.activeElement !== searchInput) {
            e.preventDefault();
            searchInput.focus();
        }
    });

    searchInput.addEventListener('input', () => {
        const val = searchInput.value;
        searchClear.classList.toggle('hidden', !val);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = val.trim().toLowerCase();
            applyFilters(true);
        }, 150);
    });

    searchClear.addEventListener('click', () => {
        searchInput.value = '';
        searchQuery = '';
        searchClear.classList.add('hidden');
        searchInput.focus();
        applyFilters(true);
    });

    window.addEventListener('scroll', () => {
        scrollTopBtn.classList.toggle('hidden', window.scrollY < 400);
    });

    scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    async function init() {
        statusEl.textContent = 'Loading catalog…';
        gridEl.classList.add('hidden');
        try {
            const res = await fetch('./assets.json');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            manifest = await res.json();
            renderStats();
            renderTabs();
            initSortSelect();
            initViewToggle();
            initThumbObserver();
            initGridResizeObserver();
            renderGrid();
            gridEl.classList.remove('hidden');
        } catch (err) {
            statusEl.textContent = 'Failed to load assets.json. Run build and generate_manifest.py first.';
            statusEl.classList.add('error');
            console.error(err);
        }
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn && window.AssetGate) {
        logoutBtn.addEventListener('click', () => {
            window.AssetGate.logout();
            location.reload();
        });
    }

    if (window.AssetGate) {
        window.AssetGate.requireAuth(init);
    } else {
        init();
    }
})();
