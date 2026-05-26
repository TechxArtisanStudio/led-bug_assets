(function () {
    'use strict';

    const STORAGE_KEY = 'ledbug_assets_unlocked';
    const SESSION_KEY = 'ledbug_assets_session';
    const PASSWORD_HASH =
        '4e0336dd9c284e3921a9ef79816de80bd5eda6b7364955ab48cebe7c767bf84a';
    const REMEMBER_MS = 30 * 24 * 60 * 60 * 1000;
    const UNLOCK_TOKEN = '1';

    async function sha256Hex(text) {
        const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
        return Array.from(new Uint8Array(buf))
            .map((b) => b.toString(16).padStart(2, '0'))
            .join('');
    }

    async function verifyPassword(input) {
        const hash = await sha256Hex(input);
        return hash === PASSWORD_HASH;
    }

    function readLocalUnlock() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return false;
            const data = JSON.parse(raw);
            if (data.token !== UNLOCK_TOKEN || !data.expiresAt) return false;
            if (Date.now() > data.expiresAt) {
                localStorage.removeItem(STORAGE_KEY);
                return false;
            }
            return true;
        } catch {
            return false;
        }
    }

    function readSessionUnlock() {
        return sessionStorage.getItem(SESSION_KEY) === UNLOCK_TOKEN;
    }

    function isUnlocked() {
        return readLocalUnlock() || readSessionUnlock();
    }

    function setUnlocked(remember) {
        sessionStorage.setItem(SESSION_KEY, UNLOCK_TOKEN);
        if (remember) {
            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({
                    token: UNLOCK_TOKEN,
                    expiresAt: Date.now() + REMEMBER_MS,
                })
            );
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }

    function logout() {
        localStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(SESSION_KEY);
    }

    function requireAuth(onUnlock) {
        const gateEl = document.getElementById('gate');
        const appEl = document.getElementById('app-root');
        const form = document.getElementById('gate-form');
        const input = document.getElementById('gate-password');
        const errorEl = document.getElementById('gate-error');
        const rememberEl = document.getElementById('gate-remember');

        if (!gateEl || !appEl || !form) {
            onUnlock();
            return;
        }

        function showGate() {
            gateEl.classList.remove('hidden');
            appEl.classList.add('hidden');
            appEl.setAttribute('aria-hidden', 'true');
            input.value = '';
            errorEl.textContent = '';
            input.focus();
        }

        function hideGate() {
            gateEl.classList.add('hidden');
            appEl.classList.remove('hidden');
            appEl.removeAttribute('aria-hidden');
        }

        if (isUnlocked()) {
            hideGate();
            onUnlock();
            return;
        }

        showGate();

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorEl.textContent = '';
            const ok = await verifyPassword(input.value);
            if (!ok) {
                errorEl.textContent = 'Incorrect password';
                input.focus();
                return;
            }
            setUnlocked(rememberEl.checked);
            hideGate();
            onUnlock();
        });
    }

    window.AssetGate = {
        isUnlocked,
        setUnlocked,
        logout,
        requireAuth,
        verifyPassword,
    };
})();
