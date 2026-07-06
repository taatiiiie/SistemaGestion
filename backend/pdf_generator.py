"""
pdf_generator.py — Defensa Civil, Municipalidad Distrital de Bellavista 2026
PDF detallado: fotos de vivienda, foto DNI, datos completos del caso.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, HRFlowable,
)
from datetime import datetime
import os

ROJO        = colors.HexColor('#8B0000')
AZUL        = colors.HexColor('#0d47a1')
DORADO      = colors.HexColor('#D4A017')
GRIS_OSCURO = colors.HexColor('#1A1A2E')
GRIS_MEDIO  = colors.HexColor('#6B7280')
GRIS_SUAVE  = colors.HexColor('#F0EDE8')
GRIS_BORDE  = colors.HexColor('#D1D5DB')
AZUL_SUAVE  = colors.HexColor('#EFF6FF')
VERDE       = colors.HexColor('#166534')
VERDE_BG    = colors.HexColor('#DCFCE7')
BLANCO      = colors.white


# ── PIE DE PÁGINA ──────────────────────────────────────────────────────────────
def _pie_pagina(canvas_obj, doc):
    canvas_obj.saveState()
    ancho, _ = A4
    canvas_obj.setStrokeColor(GRIS_BORDE)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(2*cm, 1.8*cm, ancho - 2*cm, 1.8*cm)
    canvas_obj.setFont('Helvetica', 7.5)
    canvas_obj.setFillColor(GRIS_MEDIO)
    canvas_obj.drawString(2*cm, 1.2*cm,
        'Municipalidad Distrital de Bellavista — Area de Defensa Civil | Documento oficial')
    canvas_obj.drawRightString(ancho - 2*cm, 1.2*cm,
        'Pagina {} | Sistema de Gestion con IA 2026'.format(doc.page))
    canvas_obj.restoreState()


# ── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────────
def crear_pdf(solicitud, ruta_salida):
    doc = SimpleDocTemplate(
        ruta_salida, pagesize=A4,
        topMargin=2.4*cm, bottomMargin=2.4*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )
    AU    = A4[0] - 4*cm    # ancho útil
    story = []

    # ── ENCABEZADO ──
    story.append(_encabezado(solicitud['id'], AU))
    story.append(Spacer(1, 0.25*cm))
    story.append(_banda('SOLICITUD DE ATENCION — REGISTRO DE VIVIENDA AFECTADA', AU, ROJO))
    story.append(Spacer(1, 0.4*cm))

    # Extraer datos IA
    ia_dni  = solicitud.get('ia_datos_dni', {}) or {}
    ia_casa = solicitud.get('ia_analisis_vivienda', {}) or {}

    # ── 1. DATOS GENERALES ──
    story.append(_sec('1. DATOS GENERALES DE LA SOLICITUD', AU))
    fecha_reg  = _fmt_fecha(solicitud.get('fecha', ''))
    fecha_emit = datetime.now().strftime('%d/%m/%Y  %H:%M hrs')
    metodo     = 'Sistema IA Claude Vision + OCR' if ia_dni else 'Sistema OCR Tesseract'
    story.append(_tabla_2col([
        ('N° de Solicitud', '#{:04d}'.format(solicitud['id']),
         'Fecha de Registro', fecha_reg),
        ('Estado del Caso', 'Registrado — Pendiente de visita técnica',
         'Fecha de Emision', fecha_emit),
        ('Metodo de Captura', metodo,
         'Operador Registrador', _esc(solicitud.get('operador_nombre', 'Operador de campo'))),
    ], AU))
    story.append(Spacer(1, 0.35*cm))

    # ── 2. DATOS DEL TITULAR (enriquecidos con IA) ──
    story.append(_sec('2. DATOS DEL TITULAR Y FAMILIA', AU))
    dni_val       = _esc(solicitud.get('dni', 'No detectado') or 'No detectado')
    nombre_val    = _esc(solicitud.get('nombre_familia', 'No identificado') or 'No identificado')
    nombre_manual = _esc(solicitud.get('nombre_manual', '') or '')
    num_afectados = str(solicitud.get('num_afectados', 0) or 0)
    direccion     = _esc(solicitud.get('direccion', '') or 'No registrada')

    filas_titular = [
        ('DNI del Titular', dni_val,
         'Nombre / Familia', nombre_val),
        ('Direccion de la vivienda', direccion,
         'Personas afectadas', num_afectados + ' persona(s)'),
    ]

    # Si la IA extrajo datos adicionales del DNI, los agrego
    if ia_dni:
        ap_pat = ia_dni.get('apellido_paterno') or ''
        ap_mat = ia_dni.get('apellido_materno') or ''
        nombres = ia_dni.get('nombres') or ''
        f_nac   = ia_dni.get('fecha_nacimiento') or ''
        lugar   = ia_dni.get('lugar_nacimiento') or ''
        sexo    = ia_dni.get('sexo') or ''
        conf    = ia_dni.get('confianza', 0)

        if ap_pat or ap_mat:
            filas_titular.append((
                'Apellido Paterno', _esc(ap_pat) or '—',
                'Apellido Materno', _esc(ap_mat) or '—',
            ))
        if nombres:
            filas_titular.append((
                'Nombres de Pila', _esc(nombres),
                'Fecha de Nacimiento', _esc(f_nac) or '—',
            ))
        if lugar or sexo:
            filas_titular.append((
                'Lugar de Nacimiento', _esc(lugar) or '—',
                'Sexo', _esc(sexo) or '—',
            ))
        if conf:
            filas_titular.append((
                'Confianza IA en lectura DNI', '{:.0%}'.format(conf),
                'Fuente', 'Claude Vision AI',
            ))

    story.append(_tabla_2col(filas_titular, AU, highlight=True, grande_idx={1, 3}))

    if nombre_manual:
        story.append(Spacer(1, 0.12*cm))
        story.append(_nota_inline('Nombre registrado manualmente: ', nombre_manual, AU))

    story.append(Spacer(1, 0.35*cm))

    # ── 3. EVALUACIÓN DE DAÑOS POR IA ──
    if ia_casa:
        story.append(_sec('3. EVALUACION DE DAÑOS — INTELIGENCIA ARTIFICIAL (Claude AI)', AU))
        story.append(Spacer(1, 0.15*cm))
        story += _bloque_dano_ia(ia_casa, AU)
        story.append(Spacer(1, 0.35*cm))

    # ── 4. OBSERVACIONES ──
    sec_obs = '4.' if ia_casa else '3.'
    story.append(_sec(f'{sec_obs} OBSERVACIONES DE CAMPO', AU))
    obs_texto = solicitud.get('observaciones', '') or ''
    # Si hay descripción de IA y no hay observaciones manuales, usar la de IA
    if not obs_texto.strip() and ia_casa.get('descripcion_tecnica'):
        obs_texto = '[Generado por IA] ' + ia_casa['descripcion_tecnica']
    if not obs_texto.strip():
        obs_texto = 'Sin observaciones adicionales registradas.'
    story.append(_caja_texto(_esc(obs_texto), AU))
    story.append(Spacer(1, 0.35*cm))

    # ── 5/4. FOTOS DE LA VIVIENDA ──
    sec_fotos = '5.' if ia_casa else '4.'
    story.append(_sec(f'{sec_fotos} EVIDENCIA FOTOGRAFICA — VIVIENDA AFECTADA', AU))
    story.append(Spacer(1, 0.15*cm))

    rutas_casa = solicitud.get('rutas_casa', [])
    if isinstance(rutas_casa, str):
        rutas_casa = [rutas_casa]
    rutas_casa = [r for r in rutas_casa if r and os.path.isfile(r)]

    if rutas_casa:
        story += _grid_fotos(rutas_casa, AU, 'Foto de vivienda')
    else:
        story.append(_placeholder_txt('Sin fotografias de vivienda registradas.', AU))

    story.append(Spacer(1, 0.35*cm))

    # ── 6/5. FOTO DNI ──
    sec_dni = '6.' if ia_casa else '5.'
    story.append(_sec(f'{sec_dni} EVIDENCIA FOTOGRAFICA — DOCUMENTO DE IDENTIDAD (DNI)', AU))
    story.append(Spacer(1, 0.15*cm))

    ruta_dni = solicitud.get('ruta_dni', '')
    img_dni  = _cargar_img(ruta_dni, AU * 0.6, 6*cm, 'dni')
    story.append(img_dni)
    story.append(Spacer(1, 0.12*cm))
    story.append(Paragraph(
        'Foto del DNI / documentos de identidad del titular y convivientes',
        ParagraphStyle('ley', fontName='Helvetica', fontSize=8,
                       textColor=GRIS_MEDIO, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.35*cm))

    # ── 7/6. TEXTO OCR ──
    texto_ocr = solicitud.get('texto_original', '') or ''
    if texto_ocr.strip():
        sec_ocr = '7.' if ia_casa else '6.'
        story.append(_sec(f'{sec_ocr} TEXTO EXTRAIDO POR SISTEMA IA (OCR)', AU))
        story.append(Spacer(1, 0.1*cm))
        preview = _esc(texto_ocr[:700] + ('...' if len(texto_ocr) > 700 else ''))
        t = Table(
            [[Paragraph(preview,
                        ParagraphStyle('ocr', fontName='Courier', fontSize=7.5,
                                       textColor=GRIS_OSCURO, leading=11))]],
            colWidths=[AU]
        )
        t.setStyle(TableStyle([
            ('BOX',           (0,0),(-1,-1), 0.5, GRIS_BORDE),
            ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#F8F7F4')),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.35*cm))

    # ── 7. FIRMAS ──
    story.append(Spacer(1, 0.6*cm))
    story.append(_banda('FIRMAS Y CONFORMIDAD', AU, AZUL))
    story.append(Spacer(1, 0.5*cm))

    es_firma = ParagraphStyle('firma', fontName='Helvetica', fontSize=9,
                               textColor=GRIS_OSCURO, alignment=TA_CENTER,
                               leading=14, spaceBefore=24)
    t_firma = Table([[
        Paragraph(
            '____________________________<br/>'
            '<b>Responsable de Defensa Civil</b><br/>'
            '<font size="8">Firma y Sello Oficial</font>', es_firma),
        Paragraph(
            '____________________________<br/>'
            '<b>Operador de Campo</b><br/>'
            '<font size="8">' + _esc(solicitud.get('operador_nombre', '')) + '</font>', es_firma),
        Paragraph(
            '____________________________<br/>'
            '<b>Titular / Afectado</b><br/>'
            '<font size="8">DNI: ' + _esc(solicitud.get('dni', '—')) + '</font>', es_firma),
    ]], colWidths=[AU/3, AU/3, AU/3])
    t_firma.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'BOTTOM'),
    ]))
    story.append(t_firma)

    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    print(f'[PDF] Generado correctamente: {ruta_salida}')


# ── HELPERS ────────────────────────────────────────────────────────────────────

def _bloque_dano_ia(ia_casa: dict, AU: float) -> list:
    """Genera las secciones del PDF con el análisis de daños de la IA."""
    elementos = []

    nivel      = ia_casa.get('nivel_dano', '—')
    habitab    = ia_casa.get('habitabilidad', '—')
    descripcion = ia_casa.get('descripcion_tecnica', '')
    tipos      = ia_casa.get('tipos_dano', [])
    zonas      = ia_casa.get('zonas_afectadas', [])
    acciones   = ia_casa.get('acciones_urgentes', [])
    confianza  = ia_casa.get('confianza', 0)
    apuntalar  = ia_casa.get('requiere_apuntalamiento', False)
    evacuar    = ia_casa.get('requiere_evacuacion', False)

    # Colores por nivel
    _COLORES = {
        'LEVE':      (colors.HexColor('#DCFCE7'), colors.HexColor('#166534')),
        'MODERADO':  (colors.HexColor('#FEF9C3'), colors.HexColor('#854D0E')),
        'GRAVE':     (colors.HexColor('#FED7AA'), colors.HexColor('#9A3412')),
        'MUY_GRAVE': (colors.HexColor('#FEE2E2'), colors.HexColor('#7F1D1D')),
    }
    col_bg, col_fg = _COLORES.get(nivel, (GRIS_SUAVE, GRIS_OSCURO))

    _HABITAB_LABEL = {
        'HABITABLE':           'Habitable',
        'CON_RESTRICCIONES':   'Habitable con Restricciones',
        'NO_HABITABLE':        'NO HABITABLE — Desalojar',
    }
    habitab_label = _HABITAB_LABEL.get(habitab, habitab)

    # ── Badge de nivel de daño ──
    badge = Table(
        [[Paragraph(
            f'<b>NIVEL DE DANO: {nivel}</b>',
            ParagraphStyle('badge', fontName='Helvetica-Bold', fontSize=13,
                           textColor=col_fg, alignment=TA_CENTER, leading=18)
        )]],
        colWidths=[AU * 0.45]
    )
    badge.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), col_bg),
        ('BOX',           (0,0),(-1,-1), 2, col_fg),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('RIGHTPADDING',  (0,0),(-1,-1), 12),
    ]))

    hab_col_bg = colors.HexColor('#FEE2E2') if 'NO_HABITABLE' in habitab else (
        colors.HexColor('#FEF9C3') if 'CON_' in habitab else colors.HexColor('#DCFCE7'))
    hab_col_fg = colors.HexColor('#7F1D1D') if 'NO_HABITABLE' in habitab else (
        colors.HexColor('#854D0E') if 'CON_' in habitab else colors.HexColor('#166534'))

    badge_hab = Table(
        [[Paragraph(
            f'<b>HABITABILIDAD: {habitab_label}</b>',
            ParagraphStyle('badge2', fontName='Helvetica-Bold', fontSize=9,
                           textColor=hab_col_fg, alignment=TA_CENTER, leading=13)
        )]],
        colWidths=[AU * 0.52]
    )
    badge_hab.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), hab_col_bg),
        ('BOX',           (0,0),(-1,-1), 1.5, hab_col_fg),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
    ]))

    # Fila de badges
    t_badges = Table([[badge, Spacer(0.3*cm, 1), badge_hab]],
                     colWidths=[AU*0.45, 0.3*cm, AU*0.52])
    t_badges.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))
    elementos.append(t_badges)
    elementos.append(Spacer(1, 0.25*cm))

    # ── Descripción técnica ──
    if descripcion:
        elementos.append(_caja_texto(_esc(descripcion), AU))
        elementos.append(Spacer(1, 0.2*cm))

    # ── Tabla de detalles ──
    detalles = []
    if tipos:
        detalles.append(('Tipos de daño detectados',    ', '.join(tipos),
                         'Confianza del analisis IA',   '{:.0%}'.format(confianza)))
    if zonas:
        detalles.append(('Zonas afectadas',             ', '.join(zonas),
                         'Requiere apuntalamiento',     'SI' if apuntalar else 'NO'))
    if acciones:
        ac_txt = ' / '.join(acciones)
        detalles.append(('Acciones urgentes requeridas', ac_txt,
                         'Requiere evacuacion',          'SI — URGENTE' if evacuar else 'NO'))

    if detalles:
        elementos.append(_tabla_2col(detalles, AU))

    return elementos


def _esc(t):
    return str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def _fmt_fecha(s):
    if not s:
        return datetime.now().strftime('%d/%m/%Y  %H:%M hrs')
    try:
        return datetime.fromisoformat(s).strftime('%d/%m/%Y  %H:%M hrs')
    except (ValueError, TypeError):
        return str(s)

def _sec(texto, AU):
    t = Table(
        [[Paragraph(texto, ParagraphStyle('sec', fontName='Helvetica-Bold',
                                          fontSize=9, textColor=ROJO, leading=12))]],
        colWidths=[AU]
    )
    t.setStyle(TableStyle([
        ('LINEBELOW',     (0,0),(-1,-1), 1.5, DORADO),
        ('TOPPADDING',    (0,0),(-1,-1), 2),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
    ]))
    return t

def _banda(texto, AU, color=ROJO):
    t = Table(
        [[Paragraph(texto, ParagraphStyle('br', fontName='Helvetica-Bold',
                                          fontSize=11, textColor=BLANCO,
                                          alignment=TA_CENTER, leading=16))]],
        colWidths=[AU]
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), color),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('RIGHTPADDING',  (0,0),(-1,-1), 12),
    ]))
    return t

def _encabezado(id_sol, AU):
    t = Table([[
        Paragraph('<b>MUNICIPALIDAD DISTRITAL<br/>DE BELLAVISTA</b>',
                  ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=11,
                                 textColor=ROJO, leading=14)),
        Paragraph('<b>AREA DE DEFENSA CIVIL</b><br/>'
                  '<font size="9">Sistema de Gestion de Solicitudes con IA</font>',
                  ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11,
                                 alignment=TA_CENTER, leading=14)),
        Paragraph('<font size="8">Informe N.</font><br/>'
                  '<font size="18"><b>#{:04d}</b></font>'.format(id_sol),
                  ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=8,
                                 alignment=TA_RIGHT, leading=14)),
    ]], colWidths=[AU*0.38, AU*0.38, AU*0.24])
    t.setStyle(TableStyle([
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (-1,0),(-1,-1), 0),
        ('LINEBELOW',     (0,0),(-1,0), 2.5, ROJO),
    ]))
    return t

def _lbl(t):
    return Paragraph('<b>{}</b>'.format(t),
                     ParagraphStyle('lb', fontName='Helvetica-Bold', fontSize=7.5,
                                    textColor=GRIS_MEDIO, leading=11))

def _val(t, grande=False):
    fs = 11 if grande else 9
    fn = 'Helvetica-Bold' if grande else 'Helvetica'
    return Paragraph('<b>{}</b>'.format(t) if grande else str(t),
                     ParagraphStyle('vl', fontName=fn, fontSize=fs,
                                    textColor=GRIS_OSCURO, leading=fs+3))

def _tabla_2col(filas, AU, highlight=False, grande_idx=None):
    grande_idx = grande_idx or set()
    data = []
    col  = 0
    for f in filas:
        row = [_lbl(f[0]), _val(f[1], col in grande_idx),
               _lbl(f[2]), _val(f[3], (col+1) in grande_idx)]
        data.append(row)
        col += 2
    t = Table(data, colWidths=[AU*0.22, AU*0.28, AU*0.22, AU*0.28])
    base = [
        ('BOX',           (0,0),(-1,-1), 0.5, GRIS_BORDE),
        ('INNERGRID',     (0,0),(-1,-1), 0.3, GRIS_BORDE),
        ('TOPPADDING',    (0,0),(-1,-1), 7),
        ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
    ]
    if highlight:
        base.append(('BACKGROUND', (0,0),(-1,-1), GRIS_SUAVE))
    else:
        base.append(('ROWBACKGROUNDS', (0,0),(-1,-1), [colors.white, colors.HexColor('#FAFAF8')]))
    t.setStyle(TableStyle(base))
    return t

def _nota_inline(label, valor, AU):
    t = Table(
        [[Paragraph(
            "<font size='8' color='#6B7280'>{}</font>"
            "<font size='8'><b>{}</b></font>".format(label, valor),
            ParagraphStyle('nota', fontName='Helvetica', fontSize=8,
                           leading=11, textColor=GRIS_MEDIO)
        )]],
        colWidths=[AU]
    )
    t.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))
    return t

def _caja_texto(texto, AU):
    t = Table(
        [[Paragraph(texto, ParagraphStyle('obs', fontName='Helvetica', fontSize=10,
                                          textColor=GRIS_OSCURO, leading=15))]],
        colWidths=[AU]
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), GRIS_SUAVE),
        ('BOX',           (0,0),(-1,-1), 0.5, GRIS_BORDE),
        ('TOPPADDING',    (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
        ('LEFTPADDING',   (0,0),(-1,-1), 14),
        ('RIGHTPADDING',  (0,0),(-1,-1), 14),
    ]))
    return t

def _placeholder_txt(texto, AU):
    t = Table(
        [[Paragraph(texto, ParagraphStyle('ph', fontName='Helvetica', fontSize=9,
                                          textColor=GRIS_MEDIO, alignment=TA_CENTER))]],
        colWidths=[AU], rowHeights=[2*cm]
    )
    t.setStyle(TableStyle([
        ('BOX',        (0,0),(-1,-1), 0.5, GRIS_BORDE),
        ('BACKGROUND', (0,0),(-1,-1), GRIS_SUAVE),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
    ]))
    return t

def _cargar_img(ruta, ancho, alto, tipo):
    """
    Carga una imagen para el PDF. Usa rutas absolutas.
    Si no existe o es inválida, devuelve un placeholder de texto.
    """
    if ruta:
        ruta = os.path.abspath(ruta)   # garantizar ruta absoluta
    if ruta and os.path.isfile(ruta):
        try:
            from PIL import Image as PI
            # Verificar que PIL puede abrir la imagen sin errores
            with PI.open(ruta) as img:
                img.load()    # cargar completamente
            return RLImage(ruta, width=ancho, height=alto, kind='bound')
        except Exception as e:
            print(f'[PDF] Error cargando imagen {ruta}: {e}')
    label = 'Foto de vivienda no disponible' if tipo != 'dni' else 'Foto DNI no disponible'
    return _placeholder_txt(label, ancho)

def _grid_fotos(rutas, AU, etiqueta):
    """Distribuye hasta 4 fotos en una cuadrícula 2x2."""
    elementos = []
    gap   = 0.4*cm
    img_w = (AU - gap) / 2
    img_h = 5.8*cm
    es_ley = ParagraphStyle('ley', fontName='Helvetica', fontSize=8,
                            textColor=GRIS_MEDIO, alignment=TA_CENTER)

    pares = [rutas[i:i+2] for i in range(0, len(rutas), 2)]
    for idx_fila, par in enumerate(pares):
        celdas_img = []
        celdas_ley = []
        cws        = []

        for i, ruta in enumerate(par):
            img = _cargar_img(ruta, img_w, img_h, 'casa')
            celdas_img.append(img)
            num = idx_fila * 2 + i + 1
            celdas_ley.append(Paragraph('{} {}'.format(etiqueta, num), es_ley))
            cws.append(img_w)
            if i == 0 and len(par) > 1:
                celdas_img.append(Spacer(gap, 1))
                celdas_ley.append(Spacer(gap, 1))
                cws.append(gap)

        t_imgs = Table([celdas_img], colWidths=cws)
        t_imgs.setStyle(TableStyle([
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
            ('TOPPADDING',   (0,0),(-1,-1), 0),
            ('BOTTOMPADDING',(0,0),(-1,-1), 0),
        ]))
        t_leys = Table([celdas_ley], colWidths=cws)
        t_leys.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
            ('TOPPADDING',   (0,0),(-1,-1), 2),
            ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ]))
        elementos.append(t_imgs)
        elementos.append(t_leys)
        if idx_fila < len(pares) - 1:
            elementos.append(Spacer(1, 0.3*cm))

    return elementos
