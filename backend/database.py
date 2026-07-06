"""
database.py — Gestión de BD SQLite para el Sistema de Defensa Civil
12 tablas: solicitud, usuarios, sesiones, email_tokens, log_actividad,
           notificaciones, zonas_riesgo, recursos_emergencia, equipos,
           reportes_generados, categorias_incidente, configuracion_sistema
"""
import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_USERS = [
    {
        'username': 'admin',
        'password': 'DefCivil2026!',
        'nombre': 'Administrador Defensa Civil',
        'rol': 'supervisor',
        'email': 'admin@defensacivil.pe',
    },
    {
        'username': 'operador1',
        'password': 'Campo2026!',
        'nombre': 'Operador de Campo 1',
        'rol': 'operador',
        'email': 'operador1@defensacivil.pe',
    },
]

DEFAULT_LOGIN_ALIASES = {
    user['email']: user['username']
    for user in DEFAULT_USERS
    if user.get('email')
}


def get_db_path():
    return os.path.join(BASE_DIR, 'solicitudes.db')


def _conn():
    c = sqlite3.connect(get_db_path())
    c.row_factory = sqlite3.Row
    return c


def iniciar_bd():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # ── 1. solicitud ──────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS solicitud (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha          TEXT,
            dni            TEXT,
            nombre_familia TEXT,
            rutas_casa     TEXT,
            ruta_dni       TEXT,
            texto_original TEXT,
            observaciones  TEXT,
            nombre_manual  TEXT,
            operador_id    INTEGER,
            direccion      TEXT,
            num_afectados  INTEGER DEFAULT 0,
            ia_datos_dni   TEXT,
            ia_analisis_vivienda TEXT,
            nivel_dano     TEXT,
            descripcion_ia TEXT,
            zona_id        INTEGER,
            categoria_id   INTEGER,
            estado         TEXT DEFAULT 'pendiente'
        )
    ''')

    # ── 2. usuarios ───────────────────────────────────────────────
    # Migración: renombrar esquema viejo si no tiene 'username'
    c.execute("PRAGMA table_info(usuarios)")
    cols_usuarios = {row[1] for row in c.fetchall()}
    if cols_usuarios and 'username' not in cols_usuarios:
        c.execute('ALTER TABLE usuarios RENAME TO usuarios_bak')
        c.execute('DROP TABLE IF EXISTS sesiones')

    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT UNIQUE NOT NULL,
            password_hash       TEXT NOT NULL,
            nombre              TEXT NOT NULL,
            rol                 TEXT NOT NULL CHECK(rol IN ('operador','supervisor','admin')),
            activo              INTEGER DEFAULT 1,
            email               TEXT UNIQUE,
            email_verificado    INTEGER DEFAULT 0,
            telefono            TEXT,
            creado              TEXT,
            ultimo_acceso       TEXT
        )
    ''')

    # ── 3. sesiones ───────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS sesiones (
            token    TEXT PRIMARY KEY,
            user_id  INTEGER NOT NULL,
            creado   TEXT NOT NULL,
            expira   TEXT NOT NULL,
            ip       TEXT,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    ''')

    # ── 4. email_tokens ───────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_tokens (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            email    TEXT NOT NULL,
            token    TEXT UNIQUE NOT NULL,
            tipo     TEXT NOT NULL CHECK(tipo IN ('verificacion','reset_password')),
            creado   TEXT NOT NULL,
            expira   TEXT NOT NULL,
            usado    INTEGER DEFAULT 0
        )
    ''')

    # ── 5. log_actividad ──────────────────────────────────────────
    # Migrar esquema viejo (usuario_id -> user_id) si necesario
    c.execute("PRAGMA table_info(log_actividad)")
    log_cols = {row[1] for row in c.fetchall()}
    if log_cols and 'user_id' not in log_cols:
        # Renombrar tabla vieja y recrear con nuevo esquema
        c.execute('ALTER TABLE log_actividad RENAME TO log_actividad_bak')
    c.execute('''
        CREATE TABLE IF NOT EXISTS log_actividad (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            accion   TEXT NOT NULL,
            detalle  TEXT,
            ip       TEXT,
            fecha    TEXT NOT NULL
        )
    ''')

    # ── 6. notificaciones ─────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            titulo   TEXT NOT NULL,
            mensaje  TEXT NOT NULL,
            tipo     TEXT DEFAULT 'info' CHECK(tipo IN ('info','alerta','exito','error')),
            leida    INTEGER DEFAULT 0,
            creado   TEXT NOT NULL
        )
    ''')

    # ── 7. zonas_riesgo ───────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS zonas_riesgo (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT NOT NULL,
            descripcion  TEXT,
            nivel_riesgo TEXT DEFAULT 'medio' CHECK(nivel_riesgo IN ('bajo','medio','alto','critico')),
            coordenadas  TEXT,
            color        TEXT DEFAULT '#f59e0b',
            activa       INTEGER DEFAULT 1,
            creado       TEXT
        )
    ''')

    # ── 8. recursos_emergencia ────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS recursos_emergencia (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            categoria   TEXT DEFAULT 'general',
            cantidad    INTEGER DEFAULT 0,
            disponible  INTEGER DEFAULT 0,
            unidad      TEXT DEFAULT 'unidad',
            ubicacion   TEXT,
            observacion TEXT,
            actualizado TEXT
        )
    ''')

    # ── 9. equipos ────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre   TEXT NOT NULL,
            tipo     TEXT DEFAULT 'rescate',
            lider    TEXT,
            miembros INTEGER DEFAULT 0,
            estado   TEXT DEFAULT 'disponible' CHECK(estado IN ('disponible','en_servicio','inactivo')),
            telefono TEXT,
            creado   TEXT
        )
    ''')

    # ── 10. reportes_generados ────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS reportes_generados (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitud_id INTEGER,
            generado_por INTEGER,
            fecha        TEXT NOT NULL,
            ip           TEXT
        )
    ''')

    # ── 11. categorias_incidente ──────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias_incidente (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            descripcion TEXT,
            color       TEXT DEFAULT '#0d47a1',
            icono       TEXT DEFAULT 'alerta',
            activa      INTEGER DEFAULT 1
        )
    ''')

    # ── 12. configuracion_sistema ─────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS configuracion_sistema (
            clave       TEXT PRIMARY KEY,
            valor       TEXT,
            descripcion TEXT,
            actualizado TEXT
        )
    ''')

    # Migraciones seguras de columnas existentes en solicitud
    for col_def in [
        'observaciones TEXT', 'nombre_manual TEXT', 'rutas_casa TEXT',
        'operador_id INTEGER', 'direccion TEXT', 'num_afectados INTEGER DEFAULT 0',
        'ia_datos_dni TEXT', 'ia_analisis_vivienda TEXT',
        'nivel_dano TEXT', 'descripcion_ia TEXT',
        'zona_id INTEGER', 'categoria_id INTEGER',
        "estado TEXT DEFAULT 'pendiente'",
    ]:
        try:
            c.execute(f"ALTER TABLE solicitud ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass

    # Migraciones seguras en usuarios
    for col_def in [
        'email TEXT', 'email_verificado INTEGER DEFAULT 0',
        'telefono TEXT', 'ultimo_acceso TEXT',
    ]:
        try:
            c.execute(f"ALTER TABLE usuarios ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass

    # Migración: ip en sesiones
    try:
        c.execute("ALTER TABLE sesiones ADD COLUMN ip TEXT")
    except sqlite3.OperationalError:
        pass

    _seed_defaults(c)
    conn.commit()
    conn.close()


def _seed_defaults(c):
    from auth import hash_password

    # Usuarios por defecto
    for user in DEFAULT_USERS:
        username = user['username']
        password = user['password']
        nombre = user['nombre']
        rol = user['rol']
        email = user['email']

        if email:
            c.execute(
                'UPDATE usuarios SET email = NULL WHERE lower(email) = ? AND username <> ?',
                (email.lower(), username)
            )

        c.execute('SELECT id FROM usuarios WHERE username = ?', (username,))
        row = c.fetchone()
        if not row:
            pw_hash = hash_password(password)
            c.execute(
                '''INSERT INTO usuarios (username, password_hash, nombre, rol, email, email_verificado, activo, creado)
                   VALUES (?,?,?,?,?,1,1,?)''',
                (username, pw_hash, nombre, rol, email, datetime.now().isoformat())
            )
        else:
            c.execute(
                '''UPDATE usuarios
                   SET email = ?, rol = ?, activo = 1, email_verificado = 1
                   WHERE id = ?''',
                (email, rol, row[0])
            )

    # Categorías de incidente por defecto
    categorias = [
        ('Derrumbe / Colapso', 'Estructura colapsada total o parcialmente', '#dc2626', 'colapso'),
        ('Inundación', 'Vivienda afectada por inundación', '#2563eb', 'agua'),
        ('Deslizamiento', 'Deslizamiento de tierra o huayco', '#92400e', 'tierra'),
        ('Incendio', 'Daños por incendio', '#f97316', 'fuego'),
        ('Sismo', 'Daños causados por sismo', '#7c3aed', 'sismo'),
        ('Otros', 'Otros tipos de incidentes', '#6b7280', 'general'),
    ]
    for nombre, desc, color, icono in categorias:
        c.execute('SELECT id FROM categorias_incidente WHERE nombre = ?', (nombre,))
        if not c.fetchone():
            c.execute(
                'INSERT INTO categorias_incidente (nombre, descripcion, color, icono) VALUES (?,?,?,?)',
                (nombre, desc, color, icono)
            )

    # Zonas de riesgo por defecto
    zonas = [
        ('Zona Norte', 'Sector norte del distrito', 'alto', '#ef4444'),
        ('Zona Centro', 'Casco urbano central', 'medio', '#f59e0b'),
        ('Zona Sur', 'Sector sur del distrito', 'medio', '#f59e0b'),
        ('Zona Ribereña', 'Zona cercana al río', 'critico', '#7f1d1d'),
        ('Zona Alta', 'Sector de ladera/cerro', 'alto', '#ef4444'),
    ]
    for nombre, desc, nivel, color in zonas:
        c.execute('SELECT id FROM zonas_riesgo WHERE nombre = ?', (nombre,))
        if not c.fetchone():
            c.execute(
                'INSERT INTO zonas_riesgo (nombre, descripcion, nivel_riesgo, color, creado) VALUES (?,?,?,?,?)',
                (nombre, desc, nivel, color, datetime.now().isoformat())
            )

    # Recursos por defecto
    recursos = [
        ('Carpas de emergencia', 'albergue', 20, 15, 'unidad', 'Almacén central'),
        ('Colchones', 'albergue', 50, 40, 'unidad', 'Almacén central'),
        ('Kits de alimentos', 'alimentación', 100, 80, 'kit', 'Almacén central'),
        ('Agua potable', 'agua', 5000, 4000, 'litro', 'Cisterna'),
        ('Botiquines de primeros auxilios', 'salud', 30, 25, 'unidad', 'Almacén médico'),
    ]
    for nombre, cat, cant, disp, unidad, ubic in recursos:
        c.execute('SELECT id FROM recursos_emergencia WHERE nombre = ?', (nombre,))
        if not c.fetchone():
            c.execute(
                '''INSERT INTO recursos_emergencia (nombre, categoria, cantidad, disponible, unidad, ubicacion, actualizado)
                   VALUES (?,?,?,?,?,?,?)''',
                (nombre, cat, cant, disp, unidad, ubic, datetime.now().isoformat())
            )

    # Equipos por defecto
    equipos = [
        ('Equipo Alpha', 'rescate', 'Coord. Ramírez', 5, 'disponible', '987-654-321'),
        ('Equipo Beta', 'evaluación', 'Coord. López', 4, 'disponible', '987-123-456'),
    ]
    for nombre, tipo, lider, miembros, estado, tel in equipos:
        c.execute('SELECT id FROM equipos WHERE nombre = ?', (nombre,))
        if not c.fetchone():
            c.execute(
                'INSERT INTO equipos (nombre, tipo, lider, miembros, estado, telefono, creado) VALUES (?,?,?,?,?,?,?)',
                (nombre, tipo, lider, miembros, estado, tel, datetime.now().isoformat())
            )

    # Configuración del sistema
    config_defaults = [
        ('sistema_nombre', 'Sistema Defensa Civil Bellavista', 'Nombre del sistema'),
        ('max_fotos_solicitud', '4', 'Máximo de fotos por solicitud'),
        ('notif_nuevas_solicitudes', '1', 'Notificar nuevas solicitudes al supervisor'),
        ('registro_publico', '0', 'Permitir auto-registro de usuarios'),
    ]
    for clave, valor, desc in config_defaults:
        c.execute('SELECT clave FROM configuracion_sistema WHERE clave = ?', (clave,))
        if not c.fetchone():
            c.execute(
                'INSERT INTO configuracion_sistema (clave, valor, descripcion, actualizado) VALUES (?,?,?,?)',
                (clave, valor, desc, datetime.now().isoformat())
            )


# ── SOLICITUDES ────────────────────────────────────────────────────

def guardar_solicitud(dni, nombre, rutas_casa, ruta_dni,
                      texto_ocr, observaciones='', nombre_manual='',
                      operador_id=None, direccion='', num_afectados=0,
                      ia_datos_dni=None, ia_analisis_vivienda=None,
                      nivel_dano='', descripcion_ia='',
                      zona_id=None, categoria_id=None):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    rutas_json = json.dumps(rutas_casa if isinstance(rutas_casa, list) else [rutas_casa])
    c.execute('''
        INSERT INTO solicitud
            (fecha, dni, nombre_familia, rutas_casa, ruta_dni,
             texto_original, observaciones, nombre_manual,
             operador_id, direccion, num_afectados,
             ia_datos_dni, ia_analisis_vivienda, nivel_dano, descripcion_ia,
             zona_id, categoria_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        datetime.now().isoformat(),
        dni,
        nombre_manual if nombre_manual else nombre,
        rutas_json,
        ruta_dni,
        texto_ocr,
        observaciones,
        nombre_manual,
        operador_id,
        direccion,
        num_afectados,
        json.dumps(ia_datos_dni) if ia_datos_dni else None,
        json.dumps(ia_analisis_vivienda) if ia_analisis_vivienda else None,
        nivel_dano,
        descripcion_ia,
        zona_id,
        categoria_id,
    ))
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def obtener_solicitud(id_):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.fecha, s.dni, s.nombre_familia, s.rutas_casa, s.ruta_dni,
               s.texto_original, s.observaciones, s.nombre_manual,
               s.operador_id, s.direccion, s.num_afectados,
               COALESCE(u.nombre, 'Operador de campo') AS operador_nombre,
               s.ia_datos_dni, s.ia_analisis_vivienda, s.nivel_dano, s.descripcion_ia,
               s.estado, z.nombre AS zona_nombre, cat.nombre AS categoria_nombre
        FROM solicitud s
        LEFT JOIN usuarios u   ON s.operador_id = u.id
        LEFT JOIN zonas_riesgo z ON s.zona_id = z.id
        LEFT JOIN categorias_incidente cat ON s.categoria_id = cat.id
        WHERE s.id = ?
    ''', (id_,))
    fila = c.fetchone()
    conn.close()
    if not fila:
        return None

    rutas_raw = fila[4] if fila[4] else '[]'
    try:
        rutas_lista = json.loads(rutas_raw)
        if isinstance(rutas_lista, str):
            rutas_lista = [rutas_lista]
    except Exception:
        rutas_lista = [rutas_raw] if rutas_raw else []

    def _parse_ia(raw):
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    return {
        'id': fila[0], 'fecha': fila[1], 'dni': fila[2],
        'nombre_familia': fila[3], 'rutas_casa': rutas_lista,
        'ruta_casa': rutas_lista[0] if rutas_lista else '',
        'ruta_dni': fila[5], 'texto_original': fila[6],
        'observaciones': fila[7] or '', 'nombre_manual': fila[8] or '',
        'operador_id': fila[9], 'direccion': fila[10] or '',
        'num_afectados': fila[11] or 0, 'operador_nombre': fila[12],
        'ia_datos_dni': _parse_ia(fila[13]),
        'ia_analisis_vivienda': _parse_ia(fila[14]),
        'nivel_dano': fila[15] or '', 'descripcion_ia': fila[16] or '',
        'estado': fila[17] or 'pendiente',
        'zona_nombre': fila[18] or '', 'categoria_nombre': fila[19] or '',
    }


def listar_solicitudes(limite=200):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.fecha, s.dni, s.nombre_familia, s.observaciones,
               s.nombre_manual, s.direccion, s.num_afectados,
               COALESCE(u.nombre, 'Operador') AS operador_nombre,
               s.nivel_dano, s.estado,
               z.nombre AS zona, cat.nombre AS categoria
        FROM solicitud s
        LEFT JOIN usuarios u   ON s.operador_id = u.id
        LEFT JOIN zonas_riesgo z ON s.zona_id = z.id
        LEFT JOIN categorias_incidente cat ON s.categoria_id = cat.id
        ORDER BY s.id DESC LIMIT ?
    ''', (limite,))
    filas = c.fetchall()
    conn.close()
    return [
        {
            'id': f[0], 'fecha': f[1], 'dni': f[2],
            'nombre_familia': f[5] if f[5] else f[3],
            'observaciones': f[4] or '', 'direccion': f[6] or '',
            'num_afectados': f[7] or 0, 'operador': f[8],
            'nivel_dano': f[9] or '', 'estado': f[10] or 'pendiente',
            'zona': f[11] or '', 'categoria': f[12] or '',
        }
        for f in filas
    ]


def actualizar_estado_solicitud(id_, estado):
    conn = sqlite3.connect(get_db_path())
    conn.execute('UPDATE solicitud SET estado=? WHERE id=?', (estado, id_))
    conn.commit()
    conn.close()


# ── USUARIOS ───────────────────────────────────────────────────────

def obtener_usuario(username):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        'SELECT id, username, password_hash, nombre, rol, activo, email, email_verificado FROM usuarios WHERE username = ?',
        (username,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'password_hash': row[2],
        'nombre': row[3], 'rol': row[4], 'activo': row[5],
        'email': row[6], 'email_verificado': row[7],
    }


def obtener_usuario_por_email(email):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        'SELECT id, username, password_hash, nombre, rol, activo, email, email_verificado FROM usuarios WHERE email = ?',
        (email,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'password_hash': row[2],
        'nombre': row[3], 'rol': row[4], 'activo': row[5],
        'email': row[6], 'email_verificado': row[7],
    }


def obtener_usuario_por_login(login):
    login = (login or '').strip().lower()
    if not login:
        return None

    usuario = obtener_usuario_por_email(login)
    if usuario:
        return usuario

    username = DEFAULT_LOGIN_ALIASES.get(login)
    if username:
        return obtener_usuario(username)

    if '@' not in login:
        return obtener_usuario(login)

    return None


def obtener_usuario_por_id(user_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        'SELECT id, username, nombre, rol, activo, email, email_verificado, telefono, creado, ultimo_acceso FROM usuarios WHERE id = ?',
        (user_id,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'nombre': row[2],
        'rol': row[3], 'activo': row[4], 'email': row[5],
        'email_verificado': row[6], 'telefono': row[7],
        'creado': row[8], 'ultimo_acceso': row[9],
    }


def crear_usuario(username, password_hash, nombre, rol, email=None, activo=1, email_verificado=0):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        '''INSERT INTO usuarios (username, password_hash, nombre, rol, email, activo, email_verificado, creado)
           VALUES (?,?,?,?,?,?,?,?)''',
        (username, password_hash, nombre, rol, email, activo, email_verificado, datetime.now().isoformat())
    )
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def listar_usuarios():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        SELECT id, username, nombre, rol, activo, email, email_verificado,
               telefono, creado, ultimo_acceso
        FROM usuarios ORDER BY id
    ''')
    rows = c.fetchall()
    conn.close()
    return [
        {
            'id': r[0], 'username': r[1], 'nombre': r[2], 'rol': r[3],
            'activo': r[4], 'email': r[5], 'email_verificado': r[6],
            'telefono': r[7], 'creado': r[8], 'ultimo_acceso': r[9],
        }
        for r in rows
    ]


def actualizar_usuario(user_id, **kwargs):
    allowed = {'nombre', 'rol', 'activo', 'email', 'telefono', 'password_hash',
               'email_verificado', 'ultimo_acceso'}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f'{k}=?')
            vals.append(v)
    if not sets:
        return
    vals.append(user_id)
    conn = sqlite3.connect(get_db_path())
    conn.execute(f'UPDATE usuarios SET {",".join(sets)} WHERE id=?', vals)
    conn.commit()
    conn.close()


def eliminar_usuario(user_id):
    conn = sqlite3.connect(get_db_path())
    conn.execute('DELETE FROM sesiones    WHERE user_id=?', (user_id,))
    conn.execute('DELETE FROM email_tokens WHERE user_id=?', (user_id,))
    conn.execute('DELETE FROM usuarios    WHERE id=?',      (user_id,))
    conn.commit()
    conn.close()


# ── ZONAS DE RIESGO ───────────────────────────────────────────────

def listar_zonas():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT id,nombre,descripcion,nivel_riesgo,color,activa,creado FROM zonas_riesgo ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','nombre','descripcion','nivel_riesgo','color','activa','creado'], r)) for r in rows]


def crear_zona(nombre, descripcion='', nivel_riesgo='medio', color='#f59e0b'):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('INSERT INTO zonas_riesgo (nombre,descripcion,nivel_riesgo,color,creado) VALUES (?,?,?,?,?)',
              (nombre, descripcion, nivel_riesgo, color, datetime.now().isoformat()))
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def actualizar_zona(zona_id, **kwargs):
    allowed = {'nombre', 'descripcion', 'nivel_riesgo', 'color', 'activa'}
    sets = [f'{k}=?' for k in kwargs if k in allowed]
    vals = [v for k, v in kwargs.items() if k in allowed]
    if not sets:
        return
    vals.append(zona_id)
    conn = sqlite3.connect(get_db_path())
    conn.execute(f'UPDATE zonas_riesgo SET {",".join(sets)} WHERE id=?', vals)
    conn.commit()
    conn.close()


def eliminar_zona(zona_id):
    conn = sqlite3.connect(get_db_path())
    conn.execute('DELETE FROM zonas_riesgo WHERE id=?', (zona_id,))
    conn.commit()
    conn.close()


# ── RECURSOS DE EMERGENCIA ────────────────────────────────────────

def listar_recursos():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT id,nombre,categoria,cantidad,disponible,unidad,ubicacion,observacion,actualizado FROM recursos_emergencia ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','nombre','categoria','cantidad','disponible','unidad','ubicacion','observacion','actualizado'], r)) for r in rows]


def crear_recurso(nombre, categoria='general', cantidad=0, disponible=0,
                  unidad='unidad', ubicacion='', observacion=''):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''INSERT INTO recursos_emergencia (nombre,categoria,cantidad,disponible,unidad,ubicacion,observacion,actualizado)
                 VALUES (?,?,?,?,?,?,?,?)''',
              (nombre, categoria, cantidad, disponible, unidad, ubicacion, observacion, datetime.now().isoformat()))
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def actualizar_recurso(rec_id, **kwargs):
    allowed = {'nombre', 'categoria', 'cantidad', 'disponible', 'unidad', 'ubicacion', 'observacion'}
    sets = [f'{k}=?' for k in kwargs if k in allowed]
    vals = [v for k, v in kwargs.items() if k in allowed]
    if not sets:
        return
    vals.extend([datetime.now().isoformat(), rec_id])
    conn = sqlite3.connect(get_db_path())
    conn.execute(f'UPDATE recursos_emergencia SET {",".join(sets)},actualizado=? WHERE id=?', vals)
    conn.commit()
    conn.close()


def eliminar_recurso(rec_id):
    conn = sqlite3.connect(get_db_path())
    conn.execute('DELETE FROM recursos_emergencia WHERE id=?', (rec_id,))
    conn.commit()
    conn.close()


# ── EQUIPOS ───────────────────────────────────────────────────────

def listar_equipos():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('SELECT id,nombre,tipo,lider,miembros,estado,telefono,creado FROM equipos ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','nombre','tipo','lider','miembros','estado','telefono','creado'], r)) for r in rows]


def crear_equipo(nombre, tipo='rescate', lider='', miembros=0, telefono=''):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('INSERT INTO equipos (nombre,tipo,lider,miembros,estado,telefono,creado) VALUES (?,?,?,?,?,?,?)',
              (nombre, tipo, lider, miembros, 'disponible', telefono, datetime.now().isoformat()))
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def actualizar_equipo(eq_id, **kwargs):
    allowed = {'nombre', 'tipo', 'lider', 'miembros', 'estado', 'telefono'}
    sets = [f'{k}=?' for k in kwargs if k in allowed]
    vals = [v for k, v in kwargs.items() if k in allowed]
    if not sets:
        return
    vals.append(eq_id)
    conn = sqlite3.connect(get_db_path())
    conn.execute(f'UPDATE equipos SET {",".join(sets)} WHERE id=?', vals)
    conn.commit()
    conn.close()


def eliminar_equipo(eq_id):
    conn = sqlite3.connect(get_db_path())
    conn.execute('DELETE FROM equipos WHERE id=?', (eq_id,))
    conn.commit()
    conn.close()


# ── NOTIFICACIONES ────────────────────────────────────────────────

def crear_notificacion(titulo, mensaje, tipo='info', user_id=None):
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        'INSERT INTO notificaciones (user_id,titulo,mensaje,tipo,creado) VALUES (?,?,?,?,?)',
        (user_id, titulo, mensaje, tipo, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def listar_notificaciones(user_id=None, no_leidas_solo=False):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    query = 'SELECT id,titulo,mensaje,tipo,leida,creado FROM notificaciones WHERE 1=1'
    params = []
    if user_id is not None:
        query += ' AND (user_id=? OR user_id IS NULL)'
        params.append(user_id)
    if no_leidas_solo:
        query += ' AND leida=0'
    query += ' ORDER BY id DESC LIMIT 50'
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','titulo','mensaje','tipo','leida','creado'], r)) for r in rows]


def marcar_notificacion_leida(notif_id):
    conn = sqlite3.connect(get_db_path())
    conn.execute('UPDATE notificaciones SET leida=1 WHERE id=?', (notif_id,))
    conn.commit()
    conn.close()


# ── LOG DE ACTIVIDAD ──────────────────────────────────────────────

def registrar_log(accion, detalle='', user_id=None, ip=None):
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        'INSERT INTO log_actividad (user_id,accion,detalle,ip,fecha) VALUES (?,?,?,?,?)',
        (user_id, accion, detalle, ip, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def listar_logs(limite=100):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        SELECT l.id, l.accion, l.detalle, l.ip, l.fecha,
               COALESCE(u.nombre, 'Sistema') AS usuario
        FROM log_actividad l
        LEFT JOIN usuarios u ON l.user_id = u.id
        ORDER BY l.id DESC LIMIT ?
    ''', (limite,))
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','accion','detalle','ip','fecha','usuario'], r)) for r in rows]


# ── REPORTES ──────────────────────────────────────────────────────

def registrar_reporte(solicitud_id, generado_por, ip=None):
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        'INSERT INTO reportes_generados (solicitud_id,generado_por,fecha,ip) VALUES (?,?,?,?)',
        (solicitud_id, generado_por, datetime.now().isoformat(), ip)
    )
    conn.commit()
    conn.close()


# ── DASHBOARD ─────────────────────────────────────────────────────

def stats_dashboard():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM solicitud')
    total_sol = c.fetchone()[0]

    hoy = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM solicitud WHERE fecha LIKE ?", (f'{hoy}%',))
    hoy_sol = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM solicitud WHERE dni IS NOT NULL AND dni != 'No detectado'")
    con_dni = c.fetchone()[0]

    c.execute('SELECT COALESCE(SUM(num_afectados),0) FROM solicitud')
    total_afectados = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM usuarios WHERE activo=1')
    total_usuarios = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM solicitud WHERE estado='pendiente'")
    pendientes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM solicitud WHERE estado='atendido'")
    atendidos = c.fetchone()[0]

    # Solicitudes por día (últimos 7 días)
    c.execute('''
        SELECT DATE(fecha) AS dia, COUNT(*) AS total
        FROM solicitud
        WHERE fecha >= DATE('now','-6 days')
        GROUP BY dia ORDER BY dia
    ''')
    por_dia = [{'dia': r[0], 'total': r[1]} for r in c.fetchall()]

    # Por nivel de daño
    c.execute('''
        SELECT COALESCE(NULLIF(nivel_dano,''),'Sin datos') AS nivel, COUNT(*) AS total
        FROM solicitud
        GROUP BY nivel ORDER BY total DESC
    ''')
    por_nivel = [{'nivel': r[0], 'total': r[1]} for r in c.fetchall()]

    # Por zona
    c.execute('''
        SELECT COALESCE(z.nombre,'Sin zona') AS zona, COUNT(*) AS total
        FROM solicitud s
        LEFT JOIN zonas_riesgo z ON s.zona_id = z.id
        GROUP BY zona ORDER BY total DESC LIMIT 5
    ''')
    por_zona = [{'zona': r[0], 'total': r[1]} for r in c.fetchall()]

    # Últimas solicitudes
    c.execute('''
        SELECT s.id, s.fecha, s.nombre_familia, s.nivel_dano,
               COALESCE(u.nombre,'Operador') AS operador
        FROM solicitud s
        LEFT JOIN usuarios u ON s.operador_id = u.id
        ORDER BY s.id DESC LIMIT 5
    ''')
    ultimas = [dict(zip(['id','fecha','nombre_familia','nivel_dano','operador'], r))
               for r in c.fetchall()]

    # Equipos activos
    c.execute("SELECT COUNT(*) FROM equipos WHERE estado='disponible'")
    equipos_disponibles = c.fetchone()[0]

    # Notificaciones no leídas
    c.execute('SELECT COUNT(*) FROM notificaciones WHERE leida=0')
    notif_pendientes = c.fetchone()[0]

    conn.close()

    return {
        'total_solicitudes': total_sol,
        'solicitudes_hoy': hoy_sol,
        'con_dni': con_dni,
        'total_afectados': total_afectados,
        'total_usuarios': total_usuarios,
        'pendientes': pendientes,
        'atendidos': atendidos,
        'por_dia': por_dia,
        'por_nivel': por_nivel,
        'por_zona': por_zona,
        'ultimas_solicitudes': ultimas,
        'equipos_disponibles': equipos_disponibles,
        'notif_pendientes': notif_pendientes,
    }
