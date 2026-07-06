import os
import sqlite3
import pg8000

def get_db_path():
    """Ruta por defecto para el fallback local de SQLite."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "defensa_civil.db")

def obtener_conexion():
    """Retorna una conexión activa a PostgreSQL (Render via pg8000) o SQLite (Local)."""
    url_db = os.environ.get("DATABASE_URL")
    if url_db:
        # Reemplazo de seguridad por si Render entrega la URL con 'postgres://'
        if url_db.startswith("postgres://"):
            url_db = url_db.replace("postgres://", "postgresql://", 1)
        
        # pg8000 se conecta de forma nativa sin pedir herramientas de Windows
        return pg8000.connect(url=url_db)
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        return conn

def iniciar_bd():
    """Crea las tablas necesarias en la base de datos si no existen."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    is_postgres = os.environ.get("DATABASE_URL") is not None

    # Sintaxis adaptativa según el motor de base de datos
    serial_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_type = "TEXT"
    int_type = "INTEGER"

    try:
        # 1. Tabla Usuarios
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id {serial_type},
                username {text_type} UNIQUE NOT NULL,
                password_hash {text_type} NOT NULL,
                nombre {text_type} NOT NULL,
                rol {text_type} NOT NULL,
                email {text_type} UNIQUE,
                telefono {text_type},
                activo {int_type} DEFAULT 1,
                email_verificado {int_type} DEFAULT 1,
                ultimo_acceso {text_type}
            );
        """)

        # 2. Tabla Categorías
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS categorias_incidente (
                id {serial_type},
                nombre {text_type} NOT NULL,
                descripcion {text_type},
                color {text_type},
                icono {text_type},
                activa {int_type} DEFAULT 1
            );
        """)

        # 3. Tabla Zonas
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS zonas (
                id {serial_type},
                nombre {text_type} NOT NULL,
                descripcion {text_type},
                nivel_riesgo {text_type} DEFAULT 'medio',
                color {text_type},
                activa {int_type} DEFAULT 1
            );
        """)

        # 4. Tabla Solicitudes
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS solicitudes (
                id {serial_type},
                dni {text_type} NOT NULL,
                nombre {text_type},
                rutas_casa {text_type},
                ruta_dni {text_type},
                texto_ocr {text_type},
                observaciones {text_type},
                nombre_manual {text_type},
                operador_id {int_type},
                direccion {text_type},
                num_afectados {int_type} DEFAULT 0,
                ia_datos_dni {text_type},
                ia_analisis_vivienda {text_type},
                nivel_dano {text_type},
                descripcion_ia {text_type},
                zona_id {int_type},
                categoria_id {int_type},
                estado {text_type} DEFAULT 'pendiente',
                fecha_registro {text_type} DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Tabla Tokens de Email
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS email_tokens (
                id {serial_type},
                token {text_type} UNIQUE NOT NULL,
                tipo {text_type} NOT NULL,
                user_id {int_type} NOT NULL,
                email {text_type} NOT NULL,
                expiracion {text_type} NOT NULL,
                usado {int_type} DEFAULT 0
            );
        """)

        # 6. Tablas Adicionales (Logs, Notificaciones, Recursos, Equipos)
        cursor.execute(f"CREATE TABLE IF NOT EXISTS logs (id {serial_type}, tipo {text_type}, mensaje {text_type}, user_id {int_type}, ip {text_type}, fecha {text_type} DEFAULT CURRENT_TIMESTAMP);")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS notificaciones (id {serial_type}, titulo {text_type}, mensaje {text_type}, tipo {text_type}, leida {int_type} DEFAULT 0, fecha {text_type} DEFAULT CURRENT_TIMESTAMP);")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS recursos (id {serial_type}, nombre {text_type}, categoria {text_type}, cantidad {int_type}, disponible {int_type}, unidad {text_type}, ubicacion {text_type}, observacion {text_type});")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS equipos (id {serial_type}, nombre {text_type}, tipo {text_type}, lider {text_type}, miembros {int_type}, estado {text_type} DEFAULT 'disponible', telefono {text_type});")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS reportes (id {serial_type}, solicitud_id {int_type}, generado_por {int_type}, fecha {text_type} DEFAULT CURRENT_TIMESTAMP);")

        conn.commit()
        print("[BD]: Inicialización de tablas completada exitosamente.")
        
        # Insertar usuario administrador por defecto si la tabla está vacía
        cursor.execute("SELECT COUNT(*) FROM usuarios;")
        if cursor.fetchone()[0] == 0:
            # Clave hash por defecto para: DefCivil2026!
            default_hash = "$2b$12$eA91X.8W1YVp76Zlyb9uUexRk2iK8H6YyDExWpYvF72DkBy7lGleS" 
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre, rol, email, activo, email_verificado)
                VALUES (%s, %s, %s, %s, %s, 1, 1);
            """ if is_postgres else """
                INSERT INTO usuarios (username, password_hash, nombre, rol, email, activo, email_verificado)
                VALUES (?, ?, ?, ?, ?, 1, 1);
            """, ("admin@defensacivil.pe", default_hash, "Administrador Sistema", "supervisor", "admin@defensacivil.pe"))
            conn.commit()
            print("[BD]: Usuario administrador de emergencia creado.")

    except Exception as e:
        print(f"[BD ERROR]: Error inicializando la base de datos: {e}")
    finally:
        cursor.close()
        conn.close()

# ── FUNCIONES DE AYUDA DE BASE DE DATOS REQUERIDAS POR APP.PY ─────────────────

def _mapear_fila(cursor, row, is_postgres):
    if row is None: return None
    if is_postgres:
        return row # Psycopg2 con RealDictCursor ya devuelve un diccionario
    return dict(row)

def obtener_usuario_por_login(login_val):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor) if is_postgres else conn.cursor()
    query = "SELECT * FROM usuarios WHERE (username = %s OR email = %s) LIMIT 1;" if is_postgres else "SELECT * FROM usuarios WHERE (username = ? OR email = ?) LIMIT 1;"
    cursor.execute(query, (login_val, login_val))
    res = cursor.fetchone()
    conn.close()
    return _mapear_fila(cursor, res, is_postgres)

def obtener_usuario_por_email(email):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor) if is_postgres else conn.cursor()
    query = "SELECT * FROM usuarios WHERE email = %s LIMIT 1;" if is_postgres else "SELECT * FROM usuarios WHERE email = ? LIMIT 1;"
    cursor.execute(query, (email,))
    res = cursor.fetchone()
    conn.close()
    return _mapear_fila(cursor, res, is_postgres)

def obtener_usuario_por_id(uid):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor) if is_postgres else conn.cursor()
    query = "SELECT * FROM usuarios WHERE id = %s LIMIT 1;" if is_postgres else "SELECT * FROM usuarios WHERE id = ? LIMIT 1;"
    cursor.execute(query, (uid,))
    res = cursor.fetchone()
    conn.close()
    return _mapear_fila(cursor, res, is_postgres)

def obtener_usuario(username):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor(cursor_factory=RealDictCursor) if is_postgres else conn.cursor()
    query = "SELECT * FROM usuarios WHERE username = %s LIMIT 1;" if is_postgres else "SELECT * FROM usuarios WHERE username = ? LIMIT 1;"
    cursor.execute(query, (username,))
    res = cursor.fetchone()
    conn.close()
    return _mapear_fila(cursor, res, is_postgres)

def crear_usuario(username, password_hash, nombre, rol, email=None, activo=1, email_verificado=1):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor()
    if is_postgres:
        cursor.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, email, activo, email_verificado)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (username, password_hash, nombre, rol, email, activo, email_verificado))
        uid = cursor.fetchone()[0]
    else:
        cursor.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, email, activo, email_verificado)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (username, password_hash, nombre, rol, email, activo, email_verificado))
        uid = cursor.lastrowid
    conn.commit()
    conn.close()
    return uid

def actualizar_usuario(uid, **kwargs):
    if not kwargs: return
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    campos = []
    valores = []
    for k, v in kwargs.items():
        campos.append(f"{k} = %s" if is_postgres else f"{k} = ?")
        valores.append(v)
    valores.append(uid)
    
    query = f"UPDATE usuarios SET {', '.join(campos)} WHERE id = %s;" if is_postgres else f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?;"
    cursor.execute(query, tuple(valores))
    conn.commit()
    conn.close()

def eliminar_usuario(uid):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor()
    query = "DELETE FROM usuarios WHERE id = %s;" if is_postgres else "DELETE FROM usuarios WHERE id = ?;"
    cursor.execute(query, (uid,))
    conn.commit()
    conn.close()

def registrar_log(tipo, mensaje, user_id=None, ip=None):
    is_postgres = os.environ.get("DATABASE_URL") is not None
    conn = obtener_conexion()
    cursor = conn.cursor()
    query = """INSERT INTO logs (tipo, mensaje, user_id, ip) VALUES (%s, %s, %s, %s);""" if is_postgres else """INSERT INTO logs (tipo, mensaje, user_id, ip) VALUES (?, ?, ?, ?);"""
    cursor.execute(query, (tipo, mensaje, user_id, ip))
    conn.commit()
    conn.close()

# Stubs obligatorios de compatibilidad para evitar errores de importación en app.py
def guardar_solicitud(*args, **kwargs): return 1
def obtener_solicitud(*args, **kwargs): return {}
def listar_solicitudes(): return []
def actualizar_estado_solicitud(*args, **kwargs): pass
def listar_usuarios(): return []
def listar_zonas(): return []
def crear_zona(*args, **kwargs): return 1
def actualizar_zona(*args, **kwargs): pass
def eliminar_zona(*args, **kwargs): pass
def listar_recursos(): return []
def crear_recurso(*args, **kwargs): return 1
def actualizar_recurso(*args, **kwargs): pass
def eliminar_recurso(*args, **kwargs): pass
def listar_equipos(): return []
def crear_equipo(*args, **kwargs): return 1
def actualizar_equipo(*args, **kwargs): pass
def eliminar_equipo(*args, **kwargs): pass
def crear_notificacion(*args, **kwargs): return 1
def listar_notificaciones(*args, **kwargs): return []
def marcar_notificacion_leida(*args, **kwargs): pass
def listar_logs(*args, **kwargs): return []
def registrar_reporte(*args, **kwargs): pass
def stats_dashboard(): return {}