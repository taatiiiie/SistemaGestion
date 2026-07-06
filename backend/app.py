"""
app.py — API Flask principal del Sistema de Defensa Civil
Municipalidad Distrital de Bellavista 2026
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, uuid, json, re
from functools import wraps

from backend import config
from ocr_utils    import extraer_texto_imagen, extraer_dni, extraer_nombre_familia, es_imagen_valida
from database     import (
    iniciar_bd, guardar_solicitud, obtener_solicitud, listar_solicitudes,
    obtener_usuario, obtener_usuario_por_email, obtener_usuario_por_login, obtener_usuario_por_id,
    crear_usuario, listar_usuarios, actualizar_usuario, eliminar_usuario,
    actualizar_estado_solicitud,
    listar_zonas, crear_zona, actualizar_zona, eliminar_zona,
    listar_recursos, crear_recurso, actualizar_recurso, eliminar_recurso,
    listar_equipos, crear_equipo, actualizar_equipo, eliminar_equipo,
    crear_notificacion, listar_notificaciones, marcar_notificacion_leida,
    registrar_log, listar_logs, registrar_reporte, stats_dashboard,
    get_db_path,
)
from pdf_generator import crear_pdf
from auth import (
    crear_token, validar_token, invalidar_token, check_password,
    limpiar_sesiones_expiradas, hash_password, verificar_fortaleza_password,
    rate_limit_login, reset_rate_limit,
    crear_token_email, validar_token_email, consumir_token_email,
)
from email_utils  import enviar_verificacion, enviar_reset_password, enviar_bienvenida, email_configurado
from ia_utils     import analizar_dni as ia_analizar_dni, analizar_vivienda as ia_analizar_vivienda, ia_disponible
from config       import ia_configurada

app = Flask(__name__)
app.secret_key = os.environ.get('DC_SECRET', 'dc-bellavista-2026-local-key')

CORS(app, supports_credentials=False)

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TEMP_PDF_DIR  = os.path.join(BASE_DIR, 'temp_pdfs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_PDF_DIR, exist_ok=True)

iniciar_bd()
limpiar_sesiones_expiradas()

ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
                         'image/bmp', 'image/tiff', 'image/gif'}
MAX_FILE_BYTES = 15 * 1024 * 1024

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


# ── HELPERS ──────────────────────────────────────────────────────

def _get_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return ''

def _ip():
    return request.remote_addr or request.environ.get('REMOTE_ADDR', '')

def _rol_efectivo(rol):
    return 'supervisor' if rol == 'admin' else rol

def require_auth(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = validar_token(_get_token())
            if not user:
                return jsonify({'error': 'No autenticado. Inicia sesión.'}), 401
            user['rol'] = _rol_efectivo(user['rol'])
            if roles and user['rol'] not in roles:
                return jsonify({'error': 'No tienes permiso para esta acción.'}), 403
            request.current_user = user
            return f(*args, **kwargs)
        return wrapper
    return decorator

def _json():
    return request.get_json(force=True, silent=True) or {}


# ── AUTH: LOGIN / LOGOUT ──────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def login():
    data     = _json()
    email    = str(data.get('email', '')).strip().lower()[:150]
    password = str(data.get('password', ''))[:200]

    if not email or not password:
        return jsonify({'error': 'Correo y contraseña requeridos'}), 400

    # Rate limiting por IP
    ip = _ip()
    if not rate_limit_login(ip):
        registrar_log('login_bloqueado', f'Demasiados intentos desde {ip}', ip=ip)
        return jsonify({'error': 'Demasiados intentos fallidos. Espera 5 minutos.'}), 429

    usuario = obtener_usuario_por_login(email)
    if not usuario:
        registrar_log('login_fallido', f'Email no encontrado: {email}', ip=ip)
        return jsonify({'error': 'Correo o contraseña incorrectos'}), 401
    if not check_password(password, usuario['password_hash']):
        registrar_log('login_fallido', f'Contraseña incorrecta: {email}', ip=ip)
        return jsonify({'error': 'Correo o contraseña incorrectos'}), 401
    if not usuario['activo']:
        registrar_log('login_fallido', f'Cuenta no verificada: {email}', ip=ip)
        return jsonify({'error': 'Tu cuenta aún no está verificada. Revisa tu correo y haz clic en el enlace de verificación.', 'no_verificado': True}), 401

    reset_rate_limit(ip)
    token = crear_token(usuario['id'], ip=ip)
    actualizar_usuario(usuario['id'], ultimo_acceso=__import__('datetime').datetime.now().isoformat())
    registrar_log('login', f'Login exitoso: {email}', user_id=usuario['id'], ip=ip)

    return jsonify({
        'token':  token,
        'rol':    _rol_efectivo(usuario['rol']),
        'nombre': usuario['nombre'],
        'id':     usuario['id'],
        'email':  usuario.get('email', ''),
        'email_verificado': usuario.get('email_verificado', 0),
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    token = _get_token()
    if token:
        user = validar_token(token)
        if user:
            registrar_log('logout', '', user_id=user['id'], ip=_ip())
        invalidar_token(token)
    return jsonify({'ok': True})


@app.route('/api/me', methods=['GET'])
def me():
    user = validar_token(_get_token())
    if not user:
        return jsonify({'error': 'No autenticado'}), 401
    user['rol'] = _rol_efectivo(user['rol'])
    return jsonify(user)


# ── AUTH: REGISTRO Y VERIFICACION DE EMAIL ───────────────────────

@app.route('/api/register', methods=['POST'])
def register():
    data     = _json()
    username = str(data.get('username', '')).strip()[:80]
    email    = str(data.get('email', '')).strip().lower()[:150]
    nombre   = str(data.get('nombre', '')).strip()[:120]
    password = str(data.get('password', ''))[:200]
    rol      = 'operador'  # Rol por defecto para auto-registro

    # Validaciones
    if not username or not email or not nombre or not password:
        return jsonify({'error': 'Todos los campos son requeridos'}), 400
    if len(username) < 4:
        return jsonify({'error': 'El usuario debe tener al menos 4 caracteres'}), 400
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', username):
        return jsonify({'error': 'El usuario solo puede tener letras, números, _, . y -'}), 400
    if not EMAIL_RE.match(email):
        return jsonify({'error': 'Correo electrónico inválido'}), 400

    ok, msg = verificar_fortaleza_password(password)
    if not ok:
        return jsonify({'error': msg}), 400

    # Verificar conflictos — si la cuenta existe pero no está verificada, eliminarla
    # para permitir re-registro limpio (cuentas "fantasma" del SMTP roto)
    u_por_username = obtener_usuario(username)
    if u_por_username:
        if not u_por_username['activo']:
            eliminar_usuario(u_por_username['id'])  # limpiar cuenta sin verificar
        else:
            return jsonify({'error': 'Ese nombre de usuario ya está en uso'}), 409

    u_por_email = obtener_usuario_por_email(email)
    if u_por_email:
        if not u_por_email['activo']:
            eliminar_usuario(u_por_email['id'])  # limpiar cuenta sin verificar
        else:
            return jsonify({'error': 'Ese correo ya está registrado con otra cuenta activa'}), 409

    pw_hash = hash_password(password)
    # Crear usuario inactivo hasta verificar email
    user_id = crear_usuario(username, pw_hash, nombre, rol, email=email, activo=0, email_verificado=0)

    # Generar token de verificación
    token_email = crear_token_email(email, 'verificacion', user_id)

    registrar_log('registro', f'Nuevo usuario: {username} ({email})', ip=_ip())

    # Si SMTP no está configurado en absoluto → activar directo (modo desarrollo)
    if not email_configurado():
        actualizar_usuario(user_id, activo=1, email_verificado=1)
        return jsonify({
            'ok': True,
            'mensaje': 'Cuenta creada. Puedes iniciar sesión directamente (SMTP no configurado).',
            'email_enviado': False,
        })

    # SMTP configurado → enviar código de verificación
    enviado = enviar_verificacion(email, nombre, token_email)
    if enviado:
        return jsonify({
            'ok': True,
            'mensaje': f'Cuenta creada. Te enviamos un código de 6 dígitos a {email}.',
            'email_enviado': True,
        })
    else:
        # SMTP configurado pero falló al enviar → no activar, mostrar error
        return jsonify({
            'error': f'Cuenta creada pero no se pudo enviar el correo a {email}. '
                     f'Verifica la configuración SMTP o pide al administrador que active tu cuenta.',
            'cuenta_creada': True,
        }), 500


@app.route('/api/verify-email', methods=['POST'])
def verify_email():
    data  = _json()
    token = str(data.get('token', '')).strip()

    info = validar_token_email(token, 'verificacion')
    if not info:
        # Comprobar si el token ya fue usado y la cuenta ya está activa
        import sqlite3 as _sq
        _c = _sq.connect(get_db_path())
        row = _c.execute(
            '''SELECT u.activo FROM email_tokens et
               JOIN usuarios u ON et.user_id = u.id
               WHERE et.token = ? AND et.tipo = "verificacion"''',
            (token,)
        ).fetchone()
        _c.close()
        if row and row[0] == 1:
            return jsonify({'ok': True, 'ya_verificado': True,
                            'mensaje': 'Tu cuenta ya estaba verificada. Puedes iniciar sesión.'}), 200
        return jsonify({'error': 'Este enlace ya fue usado o expiró. Inicia sesión y usa "Reenviar correo de verificación" si tu cuenta aún no está activa.'}), 400

    user_id = info['user_id']
    email   = info['email']
    consumir_token_email(token)

    actualizar_usuario(user_id, activo=1, email_verificado=1)
    registrar_log('email_verificado', f'Email verificado: {email}', user_id=user_id, ip=_ip())

    usuario = obtener_usuario_por_id(user_id)
    if usuario:
        enviar_bienvenida(email, usuario['nombre'], usuario['username'])

    return jsonify({'ok': True, 'mensaje': 'Email verificado correctamente. Ya puedes iniciar sesión.'})


@app.route('/api/resend-verification', methods=['POST'])
def resend_verification():
    data  = _json()
    email = str(data.get('email', '')).strip().lower()

    if not email or not EMAIL_RE.match(email):
        return jsonify({'error': 'Correo inválido'}), 400

    usuario = obtener_usuario_por_email(email)
    if usuario and not usuario['activo']:
        token_email = crear_token_email(email, 'verificacion', usuario['id'])
        enviado = enviar_verificacion(email, usuario['nombre'], token_email)
        registrar_log('resend_verificacion', f'Reenvío verificación: {email}', ip=_ip())
        if enviado:
            return jsonify({'ok': True, 'email': email})
        return jsonify({'error': 'No se pudo enviar el correo. Intenta de nuevo.'}), 500

    # No revelar si el correo existe y está activo
    return jsonify({'ok': True, 'email': email})


@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data  = _json()
    email = str(data.get('email', '')).strip().lower()

    if not email or not EMAIL_RE.match(email):
        return jsonify({'error': 'Correo inválido'}), 400

    usuario = obtener_usuario_por_email(email)
    # No revelar si el correo existe o no (seguridad)
    if usuario and usuario['activo']:
        token_email = crear_token_email(email, 'reset_password', usuario['id'])
        enviar_reset_password(email, usuario['nombre'], token_email)
        registrar_log('reset_solicitado', f'Reset solicitado para: {email}',
                      user_id=usuario['id'], ip=_ip())

    return jsonify({
        'ok': True,
        'mensaje': 'Si ese correo está registrado, recibirás un enlace para restablecer tu contraseña.',
    })


@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data         = _json()
    token        = str(data.get('token', '')).strip()
    new_password = str(data.get('password', ''))[:200]

    if not token or not new_password:
        return jsonify({'error': 'Token y nueva contraseña requeridos'}), 400

    ok, msg = verificar_fortaleza_password(new_password)
    if not ok:
        return jsonify({'error': msg}), 400

    info = validar_token_email(token, 'reset_password')
    if not info:
        return jsonify({'error': 'Token inválido o expirado'}), 400

    user_id = info['user_id']
    consumir_token_email(token)

    pw_hash = hash_password(new_password)
    actualizar_usuario(user_id, password_hash=pw_hash)
    # Invalidar todas las sesiones activas de ese usuario
    import sqlite3
    conn = sqlite3.connect(get_db_path())
    conn.execute('DELETE FROM sesiones WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()

    registrar_log('password_reset', f'Contraseña restablecida', user_id=user_id, ip=_ip())

    return jsonify({'ok': True, 'mensaje': 'Contraseña restablecida correctamente. Ya puedes iniciar sesión.'})


# ── GESTIÓN DE USUARIOS (supervisor) ─────────────────────────────

@app.route('/api/usuarios', methods=['GET'])
@require_auth(roles=['supervisor'])
def get_usuarios():
    return jsonify(listar_usuarios())


@app.route('/api/usuarios', methods=['POST'])
@require_auth(roles=['supervisor'])
def post_usuario():
    data     = _json()
    username = str(data.get('username', '')).strip()[:80]
    email    = str(data.get('email', '')).strip().lower()[:150] or None
    nombre   = str(data.get('nombre', '')).strip()[:120]
    rol      = str(data.get('rol', 'operador'))
    password = str(data.get('password', ''))[:200]

    if not username or not nombre or not password:
        return jsonify({'error': 'Usuario, nombre y contraseña requeridos'}), 400
    if rol not in ('operador', 'supervisor'):
        return jsonify({'error': 'Rol inválido'}), 400
    if obtener_usuario(username):
        return jsonify({'error': 'Ese usuario ya existe'}), 409
    if email:
        if not EMAIL_RE.match(email):
            return jsonify({'error': 'Correo inválido'}), 400
        if obtener_usuario_por_email(email):
            return jsonify({'error': 'Ese correo ya está registrado'}), 409

    ok, msg = verificar_fortaleza_password(password)
    if not ok:
        return jsonify({'error': msg}), 400

    pw_hash = hash_password(password)
    user_id = crear_usuario(username, pw_hash, nombre, rol, email=email, activo=1, email_verificado=1)
    registrar_log('crear_usuario', f'Creado: {username} ({rol})',
                  user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True, 'id': user_id}), 201


@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
@require_auth(roles=['supervisor'])
def put_usuario(uid):
    data = _json()
    # No permitir cambiar el propio rol
    if uid == request.current_user['id'] and 'rol' in data:
        return jsonify({'error': 'No puedes cambiar tu propio rol'}), 403

    kwargs = {}
    for campo in ('nombre', 'rol', 'activo', 'email', 'telefono'):
        if campo in data:
            kwargs[campo] = data[campo]
    if 'password' in data and data['password']:
        ok, msg = verificar_fortaleza_password(data['password'])
        if not ok:
            return jsonify({'error': msg}), 400
        kwargs['password_hash'] = hash_password(data['password'])

    actualizar_usuario(uid, **kwargs)
    registrar_log('editar_usuario', f'Editado usuario ID {uid}',
                  user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True})


@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@require_auth(roles=['supervisor'])
def delete_usuario(uid):
    if uid == request.current_user['id']:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 403
    eliminar_usuario(uid)
    registrar_log('eliminar_usuario', f'Eliminado usuario ID {uid}',
                  user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True})


# ── SOLICITUDES ───────────────────────────────────────────────────

@app.route('/api/procesar', methods=['POST'])
@require_auth(roles=['operador'])
def procesar():
    if 'foto_dni' not in request.files:
        return jsonify({'error': 'Falta la foto del DNI'}), 400

    fotos_casa_files = request.files.getlist('fotos_casa')
    if not fotos_casa_files or fotos_casa_files[0].filename == '':
        return jsonify({'error': 'Sube al menos una foto de la vivienda'}), 400

    archivo_dni   = request.files['foto_dni']
    observaciones = request.form.get('observaciones', '').strip()[:1000]
    nombre_manual = request.form.get('nombre_manual', '').strip()[:120]
    direccion     = request.form.get('direccion', '').strip()[:300]
    zona_id       = request.form.get('zona_id') or None
    categoria_id  = request.form.get('categoria_id') or None

    num_afectados = 0
    try:
        num_afectados = max(0, min(int(request.form.get('num_afectados', '0') or '0'), 9999))
    except (ValueError, TypeError):
        pass

    operador_id = request.current_user['id']
    id_unico    = uuid.uuid4().hex

    # Guardar fotos de casa
    rutas_casa = []
    for i, archivo in enumerate(fotos_casa_files[:4]):
        if not archivo or archivo.filename == '':
            continue
        ct = archivo.content_type or ''
        if ct not in ALLOWED_CONTENT_TYPES:
            return jsonify({'error': f'Tipo de archivo no permitido: {archivo.filename}'}), 400
        ext  = os.path.splitext(archivo.filename)[1].lower() or '.jpg'
        ruta = os.path.join(UPLOAD_FOLDER, f'casa_{id_unico}_{i}{ext}')
        archivo.save(ruta)
        if not es_imagen_valida(ruta):
            os.remove(ruta)
            return jsonify({'error': f'Archivo de imagen inválido: {archivo.filename}'}), 400
        rutas_casa.append(ruta)

    if not rutas_casa:
        return jsonify({'error': 'No se pudo guardar ninguna foto de vivienda'}), 400

    # Guardar foto DNI
    ct_dni = archivo_dni.content_type or ''
    if ct_dni not in ALLOWED_CONTENT_TYPES:
        return jsonify({'error': 'Tipo de archivo DNI no permitido'}), 400
    ext_dni  = os.path.splitext(archivo_dni.filename)[1].lower() or '.jpg'
    ruta_dni = os.path.join(UPLOAD_FOLDER, f'dni_{id_unico}{ext_dni}')
    archivo_dni.save(ruta_dni)
    if not es_imagen_valida(ruta_dni):
        os.remove(ruta_dni)
        return jsonify({'error': 'Archivo de imagen DNI inválido'}), 400

    # OCR
    texto_completo = extraer_texto_imagen(ruta_dni)
    dni_ocr        = extraer_dni(texto_completo)
    nombre_ocr     = extraer_nombre_familia(texto_completo)

    # IA
    ia_dni  = {}
    ia_casa = {}
    if ia_disponible():
        ia_dni  = ia_analizar_dni(ruta_dni)
        ia_casa = ia_analizar_vivienda(rutas_casa)

    dni_final    = (ia_dni.get('dni') or dni_ocr or 'No detectado')
    nombre_ia    = ia_dni.get('nombre_completo') or ia_dni.get('nombres') or nombre_ocr
    nombre_final = nombre_manual if nombre_manual else (nombre_ia or 'No identificado')
    nivel_dano   = ia_casa.get('nivel_dano', '')
    desc_ia      = ia_casa.get('descripcion_tecnica', '')

    id_solicitud = guardar_solicitud(
        dni=dni_final,
        nombre=nombre_ia or nombre_ocr or 'No identificado',
        rutas_casa=rutas_casa,
        ruta_dni=ruta_dni,
        texto_ocr=texto_completo,
        observaciones=observaciones,
        nombre_manual=nombre_manual,
        operador_id=operador_id,
        direccion=direccion,
        num_afectados=num_afectados,
        ia_datos_dni=ia_dni if ia_dni else None,
        ia_analisis_vivienda=ia_casa if ia_casa else None,
        nivel_dano=nivel_dano,
        descripcion_ia=desc_ia,
        zona_id=int(zona_id) if zona_id else None,
        categoria_id=int(categoria_id) if categoria_id else None,
    )

    registrar_log('nueva_solicitud', f'Solicitud #{id_solicitud} — DNI: {dni_final}',
                  user_id=operador_id, ip=_ip())
    crear_notificacion(
        f'Nueva solicitud #{id_solicitud}',
        f'Registrada por {request.current_user["nombre"]} — {nombre_final}',
        tipo='info',
    )

    return jsonify({
        'id':               id_solicitud,
        'dni':              dni_final,
        'nombre_familia':   nombre_final,
        'nombre_ocr':       nombre_ocr,
        'fotos_subidas':    len(rutas_casa),
        'mensaje':          'Solicitud registrada correctamente',
        'ia_activa':        bool(ia_dni or ia_casa),
        'ia_dni':           ia_dni,
        'ia_vivienda':      ia_casa,
        'nivel_dano':       nivel_dano,
    })


@app.route('/api/solicitudes', methods=['GET'])
@require_auth()
def listar():
    return jsonify(listar_solicitudes())


@app.route('/api/solicitudes/<int:id_solicitud>', methods=['GET'])
@require_auth()
def get_solicitud(id_solicitud):
    s = obtener_solicitud(id_solicitud)
    if not s:
        return jsonify({'error': 'No encontrada'}), 404
    return jsonify(s)


@app.route('/api/solicitudes/<int:id_solicitud>/estado', methods=['PUT'])
@require_auth(roles=['supervisor'])
def set_estado(id_solicitud):
    data   = _json()
    estado = str(data.get('estado', 'pendiente'))
    if estado not in ('pendiente', 'en_proceso', 'atendido', 'cerrado'):
        return jsonify({'error': 'Estado inválido'}), 400
    actualizar_estado_solicitud(id_solicitud, estado)
    registrar_log('cambio_estado', f'Solicitud #{id_solicitud} → {estado}',
                  user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True})


# ── PDF ───────────────────────────────────────────────────────────

@app.route('/api/descargar_pdf/<int:id_solicitud>', methods=['GET'])
@require_auth()
def descargar_pdf(id_solicitud):
    solicitud = obtener_solicitud(id_solicitud)
    if not solicitud:
        return jsonify({'error': 'Solicitud no encontrada'}), 404

    ruta_pdf = os.path.join(TEMP_PDF_DIR, f'solicitud_{id_solicitud}.pdf')
    try:
        crear_pdf(solicitud, ruta_pdf)
    except Exception as e:
        print(f'[PDF] Error al generar PDF #{id_solicitud}: {e}')
        return jsonify({'error': 'Error al generar el PDF'}), 500

    registrar_reporte(id_solicitud, request.current_user['id'], ip=_ip())
    registrar_log('descargar_pdf', f'PDF solicitud #{id_solicitud}',
                  user_id=request.current_user['id'], ip=_ip())

    return send_file(
        ruta_pdf,
        as_attachment=True,
        download_name=f'DefensaCivil_Solicitud_{id_solicitud:04d}.pdf',
        mimetype='application/pdf',
    )


# ── DASHBOARD ─────────────────────────────────────────────────────

@app.route('/api/dashboard', methods=['GET'])
@require_auth(roles=['supervisor'])
def dashboard():
    return jsonify(stats_dashboard())


# ── ZONAS DE RIESGO ───────────────────────────────────────────────

@app.route('/api/zonas', methods=['GET'])
@require_auth()
def get_zonas():
    return jsonify(listar_zonas())


@app.route('/api/zonas', methods=['POST'])
@require_auth(roles=['supervisor'])
def post_zona():
    data = _json()
    nombre = str(data.get('nombre', '')).strip()[:100]
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
    id_ = crear_zona(nombre, data.get('descripcion', ''),
                     data.get('nivel_riesgo', 'medio'), data.get('color', '#f59e0b'))
    registrar_log('crear_zona', nombre, user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True, 'id': id_}), 201


@app.route('/api/zonas/<int:zona_id>', methods=['PUT'])
@require_auth(roles=['supervisor'])
def put_zona(zona_id):
    data = _json()
    kwargs = {k: data[k] for k in ('nombre', 'descripcion', 'nivel_riesgo', 'color', 'activa') if k in data}
    actualizar_zona(zona_id, **kwargs)
    return jsonify({'ok': True})


@app.route('/api/zonas/<int:zona_id>', methods=['DELETE'])
@require_auth(roles=['supervisor'])
def delete_zona(zona_id):
    eliminar_zona(zona_id)
    return jsonify({'ok': True})


# ── RECURSOS DE EMERGENCIA ────────────────────────────────────────

@app.route('/api/recursos', methods=['GET'])
@require_auth()
def get_recursos():
    return jsonify(listar_recursos())


@app.route('/api/recursos', methods=['POST'])
@require_auth(roles=['supervisor'])
def post_recurso():
    data = _json()
    nombre = str(data.get('nombre', '')).strip()[:100]
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
    id_ = crear_recurso(
        nombre, data.get('categoria', 'general'),
        int(data.get('cantidad', 0)), int(data.get('disponible', 0)),
        data.get('unidad', 'unidad'), data.get('ubicacion', ''),
        data.get('observacion', '')
    )
    registrar_log('crear_recurso', nombre, user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True, 'id': id_}), 201


@app.route('/api/recursos/<int:rec_id>', methods=['PUT'])
@require_auth(roles=['supervisor'])
def put_recurso(rec_id):
    data = _json()
    kwargs = {k: data[k] for k in ('nombre', 'categoria', 'cantidad', 'disponible', 'unidad', 'ubicacion', 'observacion') if k in data}
    actualizar_recurso(rec_id, **kwargs)
    return jsonify({'ok': True})


@app.route('/api/recursos/<int:rec_id>', methods=['DELETE'])
@require_auth(roles=['supervisor'])
def delete_recurso(rec_id):
    eliminar_recurso(rec_id)
    return jsonify({'ok': True})


# ── EQUIPOS ───────────────────────────────────────────────────────

@app.route('/api/equipos', methods=['GET'])
@require_auth()
def get_equipos():
    return jsonify(listar_equipos())


@app.route('/api/equipos', methods=['POST'])
@require_auth(roles=['supervisor'])
def post_equipo():
    data = _json()
    nombre = str(data.get('nombre', '')).strip()[:100]
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
    id_ = crear_equipo(nombre, data.get('tipo', 'rescate'), data.get('lider', ''),
                       int(data.get('miembros', 0)), data.get('telefono', ''))
    registrar_log('crear_equipo', nombre, user_id=request.current_user['id'], ip=_ip())
    return jsonify({'ok': True, 'id': id_}), 201


@app.route('/api/equipos/<int:eq_id>', methods=['PUT'])
@require_auth(roles=['supervisor'])
def put_equipo(eq_id):
    data = _json()
    kwargs = {k: data[k] for k in ('nombre', 'tipo', 'lider', 'miembros', 'estado', 'telefono') if k in data}
    actualizar_equipo(eq_id, **kwargs)
    return jsonify({'ok': True})


@app.route('/api/equipos/<int:eq_id>', methods=['DELETE'])
@require_auth(roles=['supervisor'])
def delete_equipo(eq_id):
    eliminar_equipo(eq_id)
    return jsonify({'ok': True})


# ── NOTIFICACIONES ────────────────────────────────────────────────

@app.route('/api/notificaciones', methods=['GET'])
@require_auth()
def get_notificaciones():
    user = request.current_user
    data = listar_notificaciones(user_id=user['id'])
    return jsonify(data)


@app.route('/api/notificaciones/<int:nid>/leer', methods=['PUT'])
@require_auth()
def leer_notificacion(nid):
    marcar_notificacion_leida(nid)
    return jsonify({'ok': True})


# ── LOGS DE ACTIVIDAD ─────────────────────────────────────────────

@app.route('/api/logs', methods=['GET'])
@require_auth(roles=['supervisor'])
def get_logs():
    return jsonify(listar_logs(100))


# ── ESTADO DE LA IA ───────────────────────────────────────────────

@app.route('/api/ia_status', methods=['GET'])
@require_auth()
def ia_status():
    return jsonify({
        'ia_configurada': ia_configurada(),
        'ia_disponible':  ia_disponible(),
        'email_configurado': email_configurado(),
    })


# ── CATEGORÍAS ────────────────────────────────────────────────────

@app.route('/api/categorias', methods=['GET'])
@require_auth()
def get_categorias():
    import sqlite3
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT id,nombre,descripcion,color,icono,activa FROM categorias_incidente WHERE activa=1 ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(zip(['id','nombre','descripcion','color','icono','activa'], r)) for r in rows])

@app.app.route('/')
def home():
    return {"status": "Servidor funcionando correctamente", "proyecto": "SistemaGestion"}, 20

# ── INICIO ───────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 60)
    print('  DEFENSA CIVIL - SISTEMA IA v2.0')
    print('  Municipalidad Distrital de Bellavista 2026')
    print('  Servidor local: http://localhost:5000')
    print('  En red local usa: http://IP_DE_ESTA_PC:5000')
    print('  ' + '-' * 41)
    print('  Credenciales por defecto:')
    print('  Supervisor : admin@defensacivil.pe       /  DefCivil2026!')
    print('  Operador   : operador1@defensacivil.pe   /  Campo2026!')
    print('=' * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
