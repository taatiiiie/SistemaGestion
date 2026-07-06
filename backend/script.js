// ============================================
//  DEFENSA CIVIL — OPERADOR DE CAMPO
//  script.js — Autenticado, multi-foto + auth
// ============================================

const MAX_SLOTS = 4;
let slotsCargados = [false, false, false, false];

// ── INICIALIZACIÓN ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    const user = await checkAuth('operador');
    if (!user) return;

    // Mostrar nombre en topbar
    const el = document.getElementById('topbarNombre');
    if (el) el.textContent = user.nombre;

    // Drag & drop para DNI
    const zona = document.getElementById('zonaDni');
    if (zona) {
        zona.addEventListener('dragover', e => { e.preventDefault(); zona.style.borderColor = 'var(--rojo)'; });
        zona.addEventListener('dragleave', () => { zona.style.borderColor = ''; });
        zona.addEventListener('drop', e => {
            e.preventDefault();
            zona.style.borderColor = '';
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                const dt = new DataTransfer();
                dt.items.add(file);
                document.getElementById('fotoDni').files = dt.files;
                previsualizarDni(document.getElementById('fotoDni'));
            }
        });
    }

    cargarHistorial();
    verificarEstadoIA();
});

// ── SLOTS DE FOTOS DE VIVIENDA ────────────────────────────────────
function triggerSlot(n) {
    const slot = document.getElementById('slot' + n);
    if (!slot || slot.classList.contains('locked')) return;
    document.getElementById('inputCasa' + n).click();
}

function slotCargado(n, input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
        const prev = document.getElementById('prev' + n);
        prev.innerHTML = `<img src="${e.target.result}" alt="Casa ${n+1}">
                          <div class="slot-check">✓</div>
                          <button class="slot-remove" onclick="quitarSlot(${n}, event)">×</button>`;
        prev.style.display = 'block';
        document.getElementById('slot' + n).classList.add('cargado');
        slotsCargados[n] = true;
        if (n + 1 < MAX_SLOTS)
            document.getElementById('slot' + (n+1)).classList.remove('locked');
        actualizarContadorFotos();
    };
    reader.readAsDataURL(file);
}

function quitarSlot(n, event) {
    event.stopPropagation();
    document.getElementById('inputCasa' + n).value = '';
    const prev = document.getElementById('prev' + n);
    prev.innerHTML = '';
    prev.style.display = 'none';
    document.getElementById('slot' + n).classList.remove('cargado');
    slotsCargados[n] = false;
    for (let i = n + 1; i < MAX_SLOTS; i++) {
        if (!slotsCargados[i])
            document.getElementById('slot' + i).classList.add('locked');
    }
    actualizarContadorFotos();
}

function actualizarContadorFotos() {
    const cnt = slotsCargados.filter(Boolean).length;
    document.getElementById('contadorFotos').textContent = cnt;
}

// ── PREVIEW DNI ───────────────────────────────────────────────────
function previsualizarDni(input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
        const prev = document.getElementById('previewDni');
        prev.innerHTML = `<img src="${e.target.result}" alt="DNI"><div class="slot-check">✓</div>`;
        prev.style.display = 'block';
        document.getElementById('zonaDni').classList.add('loaded');
    };
    reader.readAsDataURL(file);
}

// ── PROCESAR ──────────────────────────────────────────────────────
document.getElementById('btnProcesar').addEventListener('click', async function() {
    const fotoDni      = document.getElementById('fotoDni').files[0];
    const nombreManual = document.getElementById('nombreManual').value.trim();
    const obs          = document.getElementById('observaciones').value.trim();
    const direccion    = document.getElementById('direccion').value.trim();
    const numAfectados = parseInt(document.getElementById('numAfectados').value || '0') || 0;

    const fotosCasa = [];
    for (let i = 0; i < MAX_SLOTS; i++) {
        const f = document.getElementById('inputCasa' + i).files[0];
        if (f) fotosCasa.push(f);
    }

    if (fotosCasa.length === 0) { mostrarAlerta('Sube al menos una foto de la vivienda.', 'warning'); return; }
    if (!fotoDni)               { mostrarAlerta('Sube la foto del DNI.', 'warning'); return; }

    setStep(2);
    document.getElementById('step1').style.display = 'none';
    document.getElementById('processingCard').style.display = 'block';

    const formData = new FormData();
    fotosCasa.forEach(f => formData.append('fotos_casa', f));
    formData.append('foto_dni', fotoDni);
    if (nombreManual) formData.append('nombre_manual', 'Familia ' + nombreManual);
    if (obs)          formData.append('observaciones', obs);
    if (direccion)    formData.append('direccion', direccion);
    formData.append('num_afectados', numAfectados);

    try {
        // CORREGIDO: Cambiado `${API}` por `${API_URL}`
        const res  = await fetch(`${API_URL}/procesar`, {
            method: 'POST',
            headers: authHeaders(),   // Solo Authorization, sin Content-Type (FormData lo pone solo)
            body: formData,
        });
        const data = await res.json();
        await delay(600);
        document.getElementById('processingCard').style.display = 'none';

        if (res.status === 401) { clearAuth(); window.location.href = 'login.html'; return; }

        if (res.ok) {
            document.getElementById('idSolicitud').textContent  = data.id;
            document.getElementById('dniSpan').textContent      = data.dni || 'No detectado';
            document.getElementById('nombreSpan').textContent   = data.nombre_familia || 'No identificado';
            document.getElementById('fotosSpan').textContent    = data.fotos_subidas + ' foto(s) registrada(s)';
            document.getElementById('dirSpan').textContent      = direccion || '—';
            document.getElementById('afectadosSpan').textContent = numAfectados + ' persona(s)';
            document.getElementById('obsSpan').textContent      = obs || '—';
            document.getElementById('resultFecha').textContent  = new Date().toLocaleString('es-PE', {
                day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });

            // ── Mostrar análisis IA ──
            mostrarResultadoIA(data);

            document.getElementById('resultCard').style.display = 'block';
            setStep(3);

            document.getElementById('btnPDF').onclick = async () => {
                const btn = document.getElementById('btnPDF');
                btn.disabled = true;
                try {
                    // CORREGIDO: Cambiado `${API}` por `${API_URL}`
                    const pdfRes = await fetch(`${API_URL}/descargar_pdf/${data.id}`, {
                        headers: authHeaders()
                    });
                    if (!pdfRes.ok) { throw new Error(); }
                    const blob = await pdfRes.blob();
                    const url  = URL.createObjectURL(blob);
                    const a    = document.createElement('a');
                    a.href = url;
                    a.download = `DefensaCivil_Solicitud_${String(data.id).padStart(4,'0')}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                } catch (_) {
                    mostrarAlerta('Error al generar el PDF.', 'error');
                } finally {
                    btn.disabled = false;
                }
            };

            cargarHistorial();
        } else {
            resetearFormulario();
            mostrarAlerta('Error: ' + (data.error || 'Desconocido'), 'error');
        }
    } catch (err) {
        resetearFormulario();
        mostrarAlerta('No se pudo conectar al servidor.', 'error');
        console.error(err);
    }
});

// ── NUEVA SOLICITUD ───────────────────────────────────────────────
document.getElementById('btnNueva').addEventListener('click', resetearFormulario);

function resetearFormulario() {
    for (let i = 0; i < MAX_SLOTS; i++) {
        document.getElementById('inputCasa' + i).value = '';
        document.getElementById('prev' + i).innerHTML  = '';
        document.getElementById('prev' + i).style.display = 'none';
        document.getElementById('slot' + i).classList.remove('cargado');
        if (i > 0) document.getElementById('slot' + i).classList.add('locked');
        slotsCargados[i] = false;
    }
    actualizarContadorFotos();
    document.getElementById('fotoDni').value = '';
    document.getElementById('previewDni').innerHTML = '';
    document.getElementById('previewDni').style.display = 'none';
    document.getElementById('zonaDni').classList.remove('loaded');
    document.getElementById('nombreManual').value  = '';
    document.getElementById('observaciones').value = '';
    document.getElementById('direccion').value     = '';
    document.getElementById('numAfectados').value  = '';
    document.getElementById('step1').style.display = 'block';
    document.getElementById('processingCard').style.display = 'none';
    document.getElementById('resultCard').style.display     = 'none';
    setStep(1);
}

// ── PASOS ─────────────────────────────────────────────────────────
function setStep(n) {
    [1, 2, 3].forEach(i => {
        const el = document.getElementById('step' + i + '-indicator');
        if (!el) return;
        el.classList.remove('active', 'done');
        if (i < n) el.classList.add('done');
        if (i === n) el.classList.add('active');
    });
}

// ── HISTORIAL ─────────────────────────────────────────────────────
async function cargarHistorial() {
    try {
        // CORREGIDO: Cambiado `${API}` por `${API_URL}`
        const res  = await fetch(`${API_URL}/solicitudes`, { headers: authHeaders() });
        if (res.status === 401) { clearAuth(); window.location.href = 'login.html'; return; }
        const data = await res.json();
        const list = document.getElementById('historialList');

        const totalEl = document.getElementById('totalCount');
        if (totalEl) totalEl.textContent = data.length;

        const hoy    = new Date().toDateString();
        const hayHoy = data.filter(s => s.fecha && new Date(s.fecha).toDateString() === hoy).length;
        const hoyEl  = document.getElementById('hoyCount');
        if (hoyEl) hoyEl.textContent = hayHoy;

        if (!data || data.length === 0) {
            list.innerHTML = `<div class="historial-empty">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <p>Sin registros aún.</p></div>`;
            return;
        }

        list.innerHTML = data.slice(0, 30).map(s => `
            <div class="historial-item">
                <div class="hist-num">#${String(s.id).padStart(4,'0')}</div>
                <div class="hist-info">
                    <div class="hist-nombre">${s.nombre_familia || 'Sin nombre'}</div>
                    <div class="hist-dni">DNI: ${s.dni || 'No detectado'}</div>
                    ${s.direccion ? `<div class="hist-fecha" style="font-size:.72rem;color:var(--texto-light);">${s.direccion.substring(0,40)}</div>` : ''}
                    <div class="hist-fecha">${fmtFecha(s.fecha)}</div>
                </div>
                <button class="hist-pdf" onclick="descargarPDFSidebar(${s.id}, this)" title="Descargar PDF">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    PDF
                </button>
            </div>`).join('');
    } catch(_) {}
}

async function descargarPDFSidebar(id, btn) {
    btn.style.opacity = '.5';
    try {
        // CORREGIDO: Cambiado `${API}` por `${API_URL}`
        const res = await fetch(`${API_URL}/descargar_pdf/${id}`, { headers: authHeaders() });
        if (!res.ok) throw new Error();
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href = url;
        a.download = `DefensaCivil_Solicitud_${String(id).padStart(4,'0')}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch(_) {
        mostrarAlerta('Error al descargar PDF', 'error');
    } finally {
        btn.style.opacity = '1';
    }
}

// ── ANÁLISIS IA: mostrar resultados ─────────────────────────────
function mostrarResultadoIA(data) {
    const iaPanel = document.getElementById('iaPanel');
    if (!iaPanel) return;

    const iaDni    = data.ia_dni     || {};
    const iaViv    = data.ia_vivienda || {};
    const iaActiva = data.ia_activa;

    if (!iaActiva) {
        iaPanel.innerHTML = `
          <div class="ia-aviso">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            IA no configurada. Configura tu clave en <strong>backend/config.env</strong> para activar el análisis avanzado con Claude AI.
          </div>`;
        iaPanel.style.display = 'block';
        return;
    }

    let html = '<div class="ia-resultado">';
    html += '<div class="ia-titulo"><span class="ia-badge-activa">Claude AI</span> Análisis completado</div>';

    // Datos del DNI por IA
    if (iaDni && iaDni.dni) {
        const conf = iaDni.confianza ? Math.round(iaDni.confianza * 100) + '%' : '—';
        html += `<div class="ia-seccion">
          <div class="ia-sec-titulo">Datos extraídos del DNI</div>
          <div class="ia-grid-datos">
            <div class="ia-dato"><span class="ia-lbl">DNI</span><span class="ia-val dni-num">${iaDni.dni || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Apellido Paterno</span><span class="ia-val">${iaDni.apellido_paterno || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Apellido Materno</span><span class="ia-val">${iaDni.apellido_materno || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Nombres</span><span class="ia-val">${iaDni.nombres || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Fecha de Nacimiento</span><span class="ia-val">${iaDni.fecha_nacimiento || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Lugar de Nacimiento</span><span class="ia-val">${iaDni.lugar_nacimiento || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Sexo</span><span class="ia-val">${iaDni.sexo || '—'}</span></div>
            <div class="ia-dato"><span class="ia-lbl">Confianza IA</span><span class="ia-val ia-conf">${conf}</span></div>
          </div>
        </div>`;
    }

    // Análisis de daños
    if (iaViv && iaViv.nivel_dano) {
        const _COLORES = {
            'LEVE':      '#DCFCE7:#166534',
            'MODERADO':  '#FEF9C3:#854D0E',
            'GRAVE':     '#FED7AA:#9A3412',
            'MUY_GRAVE': '#FEE2E2:#7F1D1D',
        };
        const cols = (_COLORES[iaViv.nivel_dano] || '#F0EDE8:#1A1A2E').split(':');
        const habitab = {
            'HABITABLE':         '✓ Habitable',
            'CON_RESTRICCIONES': '⚠ Con restricciones',
            'NO_HABITABLE':      '✗ NO HABITABLE',
        }[iaViv.habitabilidad] || iaViv.habitabilidad;
        const tipos  = (iaViv.tipos_dano || []).join(', ') || '—';
        const zonas  = (iaViv.zonas_afectadas || []).join(', ') || '—';
        const accs   = (iaViv.acciones_urgentes || []);

        html += `<div class="ia-seccion">
          <div class="ia-sec-titulo">Análisis de daños en vivienda</div>
          <div class="ia-nivel-badge" style="background:${cols[0]};color:${cols[1]};border:2px solid ${cols[1]};">
            NIVEL DE DAÑO: ${iaViv.nivel_dano}
          </div>
          <div class="ia-habitab ${iaViv.habitabilidad === 'NO_HABITABLE' ? 'no-hab' : ''}">${habitab}</div>
          ${iaViv.descripcion_tecnica ? `<div class="ia-descripcion">${iaViv.descripcion_tecnica}</div>` : ''}
          <div class="ia-grid-datos">
            <div class="ia-dato wide"><span class="ia-lbl">Tipos de daño</span><span class="ia-val">${tipos}</span></div>
            <div class="ia-dato wide"><span class="ia-lbl">Zonas afectadas</span><span class="ia-val">${zonas}</span></div>
          </div>
          ${accs.length ? `<div class="ia-acciones-wrap">
            <div class="ia-lbl" style="margin-bottom:6px;">Acciones urgentes:</div>
            ${accs.map(a => `<div class="ia-accion">→ ${a}</div>`).join('')}
          </div>` : ''}
        </div>`;
    }

    html += '</div>';
    iaPanel.innerHTML = html;
    iaPanel.style.display = 'block';
}

// ── VERIFICAR ESTADO IA AL CARGAR ─────────────────────────────────
async function verificarEstadoIA() {
    try {
        // CORREGIDO: Cambiado `${API}` por `${API_URL}`
        const res  = await fetch(`${API_URL}/ia_status`, { headers: authHeaders() });
        const data = await res.json();
        const badge = document.getElementById('iaBadgeTopbar');
        if (badge) {
            if (data.ia_configurada) {
                badge.textContent = 'Claude AI Activo';
                badge.className   = 'ia-badge-topbar activa';
            } else {
                badge.textContent = 'IA no configurada';
                badge.className   = 'ia-badge-topbar';
            }
        }
    } catch(_) {}
}

// ── UTILIDADES ────────────────────────────────────────────────────
function mostrarAlerta(msg, tipo) {
    const c = tipo === 'warning'
        ? ['#FEF9C3','#FCD34D','#92400E']
        : ['#FEE2E2','#F87171','#991B1B'];
    const div = document.createElement('div');
    div.style.cssText = `position:fixed;top:80px;right:1.5rem;z-index:9999;background:${c[0]};border:1.5px solid ${c[1]};color:${c[2]};padding:14px 18px;border-radius:12px;font-size:.9rem;max-width:360px;font-family:'DM Sans',sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.12)`;
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(() => { div.style.opacity='0'; div.style.transition='opacity .3s'; setTimeout(()=>div.remove(),300); }, 4000);
}

const delay = ms => new Promise(r => setTimeout(r, ms));