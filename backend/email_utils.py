"""
email_utils.py — Envío de correos electrónicos para el Sistema de Defensa Civil
Prioridad: Brevo API → SMTP fallback
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


# ── DOMINIO DEL FRONTEND (Dinámico para Producción) ──────────────────
def _obtener_base_url():
    # Si estás en Render u otro hosting, lee la URL pública, sino usa localhost
    return os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500").rstrip('/')


# ── BREVO ────────────────────────────────────────────────────────

def _brevo_disponible() -> bool:
    return bool(os.environ.get("BREVO_API_KEY"))

def _enviar_con_brevo(to_email, subject, html_body):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.environ.get("BREVO_API_KEY")

    api = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    # CORRECCIÓN: Evita remitentes vacíos que rompen la API de Brevo
    remitente_email = os.environ.get("BREVO_SENDER_EMAIL")
    if not remitente_email:
        print("[BREVO CONFIG ERROR]: Falta configurar la variable 'BREVO_SENDER_EMAIL' en Render.")
        return False

    sender = {
        "name": os.environ.get("BREVO_SENDER_NAME", "Defensa Civil Bellavista"),
        "email": remitente_email
    }

    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender=sender,
        subject=subject,
        html_content=html_body
    )

    try:
        api.send_transac_email(email)
        print(f"[Brevo API] Correo enviado con éxito a {to_email}")
        return True
    except ApiException as e:
        print(f"[Brevo API Error]: {e}")
        return False


# ── SMTP (FALLBACK) ───────────────────────────────────────────────

def _smtp_cfg():
    return {
        'server':    os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
        'port':      int(os.environ.get('SMTP_PORT', '587')),
        'user':      os.environ.get('SMTP_USER', ''),
        'password':  os.environ.get('SMTP_PASSWORD', ''),
        'from_name': os.environ.get('SMTP_FROM_NAME', 'Defensa Civil Bellavista'),
    }

def _smtp_disponible() -> bool:
    cfg = _smtp_cfg()
    return bool(cfg['user'] and cfg['password'])

def _enviar_con_smtp(to_email: str, subject: str, html_body: str) -> bool:
    cfg = _smtp_cfg()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{cfg["from_name"]} <{cfg["user"]}>'
    msg['To'] = to_email
    msg['X-Mailer'] = 'DefensaCivil-Sistema/2026'
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg['server'], cfg['port'], timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(cfg['user'], cfg['password'])
            smtp.sendmail(cfg['user'], to_email, msg.as_string())
        print(f'[SMTP] OK -> {to_email}: {subject}')
        return True
    except smtplib.SMTPAuthenticationError:
        print('[SMTP] ERROR AUTH - verifica SMTP_USER y SMTP_PASSWORD')
        return False
    except smtplib.SMTPException as e:
        print(f'[SMTP] ERROR SMTP -> {e}')
        return False
    except Exception as e:
        print(f'[SMTP] ERROR -> {type(e).__name__}: {e}')
        return False


# ── INTERFAZ PÚBLICA ──────────────────────────────────────────────

def email_configurado() -> bool:
    return _brevo_disponible() or _smtp_disponible()

def enviar_email(to_email: str, subject: str, html_body: str) -> bool:
    if _brevo_disponible():
        ok = _enviar_con_brevo(to_email, subject, html_body)
        if ok:
            return True
    if _smtp_disponible():
        return _enviar_con_smtp(to_email, subject, html_body)
    print(f'[EMAIL] Sin configurar — email no enviado a {to_email}: {subject}')
    return False


# ── PLANTILLA BASE ────────────────────────────────────────────────

def _base_template(titulo: str, contenido: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;padding:0;background:#f4f6fa;font-family:'Segoe UI',Arial,sans-serif;}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;
         overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.10);}}
  .header{{background:linear-gradient(135deg,#0d1b6e,#0d47a1);padding:28px 32px;text-align:center;}}
  .header .logo-text{{color:#fff;font-size:22px;font-weight:700;margin:0;}}
  .header .sub{{color:rgba(255,255,255,.65);font-size:13px;margin-top:4px;}}
  .body{{padding:32px;}}
  h2{{margin:0 0 16px;color:#1a1a2e;font-size:20px;}}
  p{{margin:0 0 14px;color:#374151;font-size:15px;line-height:1.6;}}
  .btn{{display:inline-block;padding:13px 32px;background:#0d47a1;color:#fff !important;
        text-decoration:none;border-radius:10px;font-size:15px;font-weight:600;margin:12px 0;}}
  .footer{{background:#f8fafc;padding:18px 32px;text-align:center;
           font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;}}
  .warning{{background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;
            padding:12px 16px;font-size:13px;color:#92400e;margin-top:16px;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <p class="logo-text">Defensa Civil Bellavista</p>
    <p class="sub">Municipalidad Distrital de Bellavista · Sistema de Gestión</p>
  </div>
  <div class="body">
    <h2>{titulo}</h2>
    {contenido}
  </div>
  <div class="footer">
    Municipalidad Distrital de Bellavista — Área de Defensa Civil &copy; 2026<br>
    Este es un correo automático, no responder.
  </div>
</div>
</body>
</html>"""


# ── EMAILS ESPECÍFICOS ────────────────────────────────────────────

def enviar_verificacion(to_email: str, nombre: str, token: str) -> bool:
    base_url = _obtener_base_url()
    link = f'{base_url}/frontend/verify-email.html?token={token}'
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Gracias por registrarte en el <strong>Sistema de Defensa Civil Bellavista</strong>.
       Para activar tu cuenta, haz clic en el botón:</p>
    <p style="text-align:center;margin:24px 0">
      <a class="btn" href="{link}" target="_blank" rel="noopener">Confirmar mi cuenta</a>
    </p>
    <p style="text-align:center;color:#6b7280;font-size:12px;margin-top:8px">
      Si el botón no abre, copia y pega esta dirección en tu navegador:<br>
      <span style="color:#0d47a1">{link}</span>
    </p>
    <div class="warning">
      Este enlace expira en <strong>24 horas</strong>. Si no creaste una cuenta, ignora este correo.
    </div>
    """
    return enviar_email(to_email, 'Confirma tu cuenta - Defensa Civil Bellavista', _base_template('Confirma tu cuenta', contenido))


def enviar_reset_password(to_email: str, nombre: str, token: str) -> bool:
    base_url = _obtener_base_url()
    link = f'{base_url}/frontend/reset-password.html?token={token}'
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en el
       <strong>Sistema de Defensa Civil Bellavista</strong>.</p>
    <p>Haz clic en el botón para crear tu nueva contraseña:</p>
    <p style="text-align:center;margin:24px 0">
      <a class="btn" href="{link}" target="_blank" rel="noopener">Restablecer contraseña</a>
    </p>
    <p style="text-align:center;color:#6b7280;font-size:12px;margin-top:8px">
      Si el botón no abre, copia y pega esta dirección en tu navegador:<br>
      <span style="color:#0d47a1">{link}</span>
    </p>
    <div class="warning">
      Este enlace expira en <strong>2 horas</strong>. Si no solicitaste este cambio,
      ignora este correo y tu contraseña permanecerá sin cambios.
    </div>
    """
    return enviar_email(to_email, 'Restablecer contraseña - Defensa Civil Bellavista', _base_template('Restablecer contraseña', contenido))


def enviar_bienvenida(to_email: str, nombre: str, username: str) -> bool:
    base_url = _obtener_base_url()
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Tu cuenta en el <strong>Sistema de Defensa Civil Bellavista</strong> ha sido activada correctamente.</p>
    <p>Tus credenciales de acceso:</p>
    <ul style="color:#374151;font-size:15px;line-height:1.8;">
      <li>Usuario: <strong>{username}</strong></li>
      <li>Contraseña: la que registraste</li>
    </ul>
    <p style="text-align:center"><a class="btn" href="{base_url}/frontend/login.html">Ir al sistema</a></p>
    <p style="color:#6b7280;font-size:13px;">
      Si tienes problemas para acceder, contacta al administrador del sistema.
    </p>
    """
    return enviar_email(to_email, 'Bienvenido al Sistema de Defensa Civil', _base_template('¡Cuenta activada!', contenido))