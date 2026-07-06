// auth.js — Utilidades de autenticación compartidas
// Detecta automáticamente si estás en local o en Render
const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000/api'
    : `${window.location.origin}/api`;

function getToken()  { return localStorage.getItem('dc_token'); }
function getUser()   { const u = localStorage.getItem('dc_user'); return u ? JSON.parse(u) : null; }
function normalizeRole(rol) { return rol === 'admin' ? 'supervisor' : rol; }
function homeForRole(rol) {
    rol = normalizeRole(rol);
    if (rol === 'supervisor') return 'supervisor.html';
    if (rol === 'operador') return 'operador.html';
    return 'login.html';
}

function setAuth(token, user) {
    user.rol = normalizeRole(user.rol);
    localStorage.setItem('dc_token', token);
    localStorage.setItem('dc_user', JSON.stringify(user));
}

function clearAuth() {
    localStorage.removeItem('dc_token');
    localStorage.removeItem('dc_user');
}

function authHeaders(extra) {
    return Object.assign({ 'Authorization': 'Bearer ' + getToken() }, extra || {});
}

async function checkAuth(rolRequerido) {
    const token = getToken();
    const user  = getUser();
    if (!token || !user) { window.location.href = 'login.html'; return null; }
    user.rol = normalizeRole(user.rol);
    if (!['supervisor', 'operador'].includes(user.rol)) {
        clearAuth();
        window.location.href = 'login.html';
        return null;
    }
    localStorage.setItem('dc_user', JSON.stringify(user));
    if (rolRequerido && user.rol !== rolRequerido) {
        window.location.href = homeForRole(user.rol);
        return null;
    }
    return user;
}

async function logout() {
    try {
        await fetch(`${API}/api/logout`, { method: 'POST', headers: authHeaders() });
    } catch (_) {}
    clearAuth();
    window.location.href = 'login.html';
}

function fmtFecha(s) {
    if (!s) return '—';
    try {
        return new Date(s).toLocaleString('es-PE', {
            day:'2-digit', month:'2-digit', year:'numeric',
            hour:'2-digit', minute:'2-digit'
        });
    } catch(_) { return s; }
}

function fmtFechaCorta(s) {
    if (!s) return '—';
    try {
        return new Date(s).toLocaleDateString('es-PE', {
            day:'2-digit', month:'2-digit', year:'numeric'
        });
    } catch(_) { return s; }
}

function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── TOAST NOTIFICATIONS ────────────────────────────────────────────
function toast(msg, tipo = 'success', duracion = 6000) {
    let container = document.getElementById('_toast_wrap');
    if (!container) {
        container = document.createElement('div');
        container.id = '_toast_wrap';
        container.style.cssText = [
            'position:fixed', 'top:1.25rem', 'right:1.25rem', 'z-index:9999',
            'display:flex', 'flex-direction:column', 'gap:.5rem',
            'pointer-events:none', 'min-width:280px'
        ].join(';');
        document.body.appendChild(container);
    }
    const paleta = {
        success: { bg: '#DCFCE7', bd: '#86EFAC', color: '#166534', icon: '✓' },
        error:   { bg: '#FEE2E2', bd: '#F87171', color: '#991B1B', icon: '✕' },
        warning: { bg: '#FEF3C7', bd: '#FCD34D', color: '#92400e', icon: '⚠' },
        info:    { bg: '#EFF6FF', bd: '#93C5FD', color: '#1e40af', icon: 'ℹ' },
    };
    const p = paleta[tipo] || paleta.info;
    const el = document.createElement('div');
    el.style.cssText = [
        `background:${p.bg}`, `border:1.5px solid ${p.bd}`, `color:${p.color}`,
        'padding:.8rem 1.1rem', 'border-radius:10px', 'font-size:.9rem',
        "font-family:'DM Sans',sans-serif", 'display:flex', 'align-items:flex-start',
        'gap:.6rem', 'box-shadow:0 4px 24px rgba(0,0,0,.18)', 'max-width:360px',
        'opacity:0', 'transform:translateX(30px)',
        'transition:opacity .3s ease, transform .3s ease',
        'pointer-events:auto', 'line-height:1.45', 'font-weight:500',
    ].join(';');
    el.innerHTML = `<span style="font-weight:800;font-size:1.1rem;flex-shrink:0;margin-top:1px">${p.icon}</span><span>${msg}</span>`;
    container.appendChild(el);
    // setTimeout en lugar de rAF — garantiza que el DOM pintó antes de animar
    setTimeout(() => {
        el.style.opacity = '1';
        el.style.transform = 'translateX(0)';
    }, 30);
    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateX(30px)';
        setTimeout(() => el.remove(), 350);
    }, duracion);
}
