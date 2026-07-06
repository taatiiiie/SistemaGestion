"""
auth.py — Autenticación por token para el Sistema de Defensa Civil
"""
import sqlite3
import secrets
import bcrypt
from datetime import datetime, timedelta
import os
import time
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOKEN_HORAS = 12
TOKEN_EMAIL_HORAS_VERIFICACION = 24
TOKEN_EMAIL_HORAS_RESET = 2

# Límite de intentos de login (rate limiting en memoria)
_login_attempts = defaultdict(list)
MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 300  # 5 minutos


def _db():
    return sqlite3.connect(os.path.join(BASE_DIR, 'solicitudes.db'))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def verificar_fortaleza_password(password: str) -> tuple[bool, str]:
    """Retorna (es_valida, mensaje)"""
    if len(password) < 8:
        return False, 'La contraseña debe tener al menos 8 caracteres'
    if not any(c.isupper() for c in password):
        return False, 'La contraseña debe tener al menos una mayúscula'
    if not any(c.isdigit() for c in password):
        return False, 'La contraseña debe tener al menos un número'
    return True, ''


def rate_limit_login(identifier: str) -> bool:
    """Retorna True si se puede intentar, False si está bloqueado."""
    ahora = time.time()
    intentos = _login_attempts[identifier]
    # Limpiar intentos viejos
    intentos[:] = [t for t in intentos if ahora - t < VENTANA_SEGUNDOS]
    if len(intentos) >= MAX_INTENTOS:
        return False
    intentos.append(ahora)
    return True


def reset_rate_limit(identifier: str):
    _login_attempts.pop(identifier, None)


# ── SESIONES ──────────────────────────────────────────────────────

def crear_token(user_id: int, ip: str = None) -> str:
    token = secrets.token_hex(32)
    expira = (datetime.now() + timedelta(hours=TOKEN_HORAS)).isoformat()
    conn = _db()
    conn.execute(
        'INSERT INTO sesiones (token, user_id, creado, expira, ip) VALUES (?, ?, ?, ?, ?)',
        (token, user_id, datetime.now().isoformat(), expira, ip)
    )
    conn.commit()
    conn.close()
    return token


def validar_token(token: str):
    if not token or len(token) < 10:
        return None
    conn = _db()
    c = conn.cursor()
    c.execute('''
        SELECT u.id, u.username, u.nombre, u.rol, u.email, u.email_verificado
        FROM sesiones s
        JOIN usuarios u ON s.user_id = u.id
        WHERE s.token = ? AND s.expira > ? AND u.activo = 1
    ''', (token, datetime.now().isoformat()))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'nombre': row[2],
        'rol': row[3], 'email': row[4], 'email_verificado': row[5],
    }


def invalidar_token(token: str):
    conn = _db()
    conn.execute('DELETE FROM sesiones WHERE token = ?', (token,))
    conn.commit()
    conn.close()


def limpiar_sesiones_expiradas():
    conn = _db()
    conn.execute('DELETE FROM sesiones WHERE expira < ?', (datetime.now().isoformat(),))
    conn.commit()
    conn.close()


# ── EMAIL TOKENS ──────────────────────────────────────────────────

def crear_token_email(email: str, tipo: str, user_id: int = None) -> str:
    """tipo: 'verificacion' o 'reset_password'"""
    horas = TOKEN_EMAIL_HORAS_VERIFICACION if tipo == 'verificacion' else TOKEN_EMAIL_HORAS_RESET
    token = secrets.token_urlsafe(32)
    expira = (datetime.now() + timedelta(hours=horas)).isoformat()
    conn = _db()
    # Invalidar tokens anteriores del mismo tipo para este email
    conn.execute(
        'UPDATE email_tokens SET usado=1 WHERE email=? AND tipo=? AND usado=0',
        (email, tipo)
    )
    conn.execute(
        'INSERT INTO email_tokens (user_id, email, token, tipo, creado, expira, usado) VALUES (?,?,?,?,?,?,0)',
        (user_id, email, token, tipo, datetime.now().isoformat(), expira)
    )
    conn.commit()
    conn.close()
    return token


def validar_token_email(token: str, tipo: str):
    """Retorna {'email': ..., 'user_id': ...} si válido, None si no."""
    if not token:
        return None
    conn = _db()
    c = conn.cursor()
    c.execute(
        'SELECT email, user_id FROM email_tokens WHERE token=? AND tipo=? AND usado=0 AND expira>?',
        (token, tipo, datetime.now().isoformat())
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {'email': row[0], 'user_id': row[1]}


def consumir_token_email(token: str):
    conn = _db()
    conn.execute('UPDATE email_tokens SET usado=1 WHERE token=?', (token,))
    conn.commit()
    conn.close()
