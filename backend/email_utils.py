"""
email_utils.py — Envío de correos electrónicos para el Sistema de Defensa Civil
Prioridad: Resend API (si RESEND_API_KEY está configurado) → SMTP fallback
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ── RESEND ────────────────────────────────────────────────────────

def _resend_disponible() -> bool:
    return bool(os.environ.get('RESEND_API_KEY', ''))


def _enviar_con_resend(to_email: str, subject: str, html_body: str) -> bool:
    import resend
    resend.api_key = os.environ.get('RESEND_API_KEY', '')
    from_addr = os.environ.get('RESEND_FROM', 'onboarding@resend.dev')
    from_name = os.environ.get('SMTP_FROM_NAME', 'Defensa Civil Bellavista')
    params = {
        "from": f"{from_name} <{from_addr}>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    try:
        r = resend.Emails.send(params)
        ok = bool(getattr(r, 'id', None) or (isinstance(r, dict) and r.get('id')))
        print(f'[RESEND] {"OK" if ok else "SIN ID"} -> {to_email}: {subject}')
        return ok
    except Exception as e:
        print(f'[RESEND] ERROR -> {type(e).__name__}: {e}')
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
        print('[SMTP] ERROR AUTH - verifica SMTP_USER y SMTP_PASSWORD en config.env')
        return False
    except smtplib.SMTPException as e:
        print(f'[SMTP] ERROR SMTP -> {e}')
        return False
    except Exception as e:
        print(f'[SMTP] ERROR -> {type(e).__name__}: {e}')
        return False


# ── INTERFAZ PÚBLICA ──────────────────────────────────────────────

def email_configurado() -> bool:
    return _resend_disponible() or _smtp_disponible()


def enviar_email(to_email: str, subject: str, html_body: str) -> bool:
    # Resend primero (no expone correo personal), SMTP como fallback
    if _resend_disponible():
        ok = _enviar_con_resend(to_email, subject, html_body)
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
  .btn{{display:inline-block;padding:13px 32px;background:#0d47a1;color:#fff;
        text-decoration:none;border-radius:10px;font-size:15px;font-weight:600;margin:12px 0;}}
  .token-box{{background:#f0f4ff;border:1.5px solid #bfdbfe;border-radius:10px;
              padding:16px 20px;text-align:center;font-size:24px;font-weight:700;
              letter-spacing:6px;color:#0d47a1;margin:16px 0;}}
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
    link = f'http://127.0.0.1:5500/frontend/verify-email.html?token={token}'
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Gracias por registrarte en el <strong>Sistema de Defensa Civil Bellavista</strong>.
       Para activar tu cuenta, haz clic en el boton:</p>
    <p style="text-align:center;margin:24px 0">
      <a class="btn" href="{link}" target="_blank" rel="noopener">Confirmar mi cuenta</a>
    </p>
    <p style="text-align:center;color:#6b7280;font-size:12px;margin-top:8px">
      Si el boton no abre, copia y pega esta direccion en tu navegador:<br>
      <span style="color:#0d47a1">{link}</span>
    </p>
    <div class="warning">
      Este enlace expira en <strong>24 horas</strong>. Si no creaste una cuenta, ignora este correo.
    </div>
    """
    return enviar_email(to_email, 'Confirma tu cuenta - Defensa Civil Bellavista', _base_template('Confirma tu cuenta', contenido))


def enviar_reset_password(to_email: str, nombre: str, token: str) -> bool:
    link = f'http://127.0.0.1:5500/frontend/reset-password.html?token={token}'
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Recibimos una solicitud para restablecer la contrasena de tu cuenta en el
       <strong>Sistema de Defensa Civil Bellavista</strong>.</p>
    <p>Haz clic en el boton para crear tu nueva contrasena:</p>
    <p style="text-align:center;margin:24px 0">
      <a class="btn" href="{link}" target="_blank" rel="noopener">Restablecer contrasena</a>
    </p>
    <p style="text-align:center;color:#6b7280;font-size:12px;margin-top:8px">
      Si el boton no abre, copia y pega esta direccion en tu navegador:<br>
      <span style="color:#0d47a1">{link}</span>
    </p>
    <div class="warning">
      Este enlace expira en <strong>2 horas</strong>. Si no solicitaste este cambio,
      ignora este correo y tu contrasena permanecera sin cambios.
    </div>
    """
    return enviar_email(to_email, 'Restablecer contrasena - Defensa Civil Bellavista', _base_template('Restablecer contrasena', contenido))


def enviar_bienvenida(to_email: str, nombre: str, username: str) -> bool:
    contenido = f"""
    <p>Hola <strong>{nombre}</strong>,</p>
    <p>Tu cuenta en el <strong>Sistema de Defensa Civil Bellavista</strong> ha sido activada correctamente.</p>
    <p>Tus credenciales de acceso:</p>
    <ul style="color:#374151;font-size:15px;line-height:1.8;">
      <li>Usuario: <strong>{username}</strong></li>
      <li>Contraseña: la que registraste</li>
    </ul>
    <p style="text-align:center"><a class="btn" href="http://localhost:5500/frontend/login.html">Ir al sistema</a></p>
    <p style="color:#6b7280;font-size:13px;">
      Si tienes problemas para acceder, contacta al administrador del sistema.
    </p>
    """
    return enviar_email(to_email, 'Bienvenido al Sistema de Defensa Civil', _base_template('¡Cuenta activada!', contenido))
