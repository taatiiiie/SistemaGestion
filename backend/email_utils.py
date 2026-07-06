import os
import requests

def email_configurado():
    """Valida la presencia de las variables de entorno inyectadas desde Render."""
    return bool(os.environ.get("BREVO_API_KEY")) and bool(os.environ.get("BREVO_FROM_EMAIL"))

def enviar_reset_password(email, nombre, token):
    """Envía un correo electrónico estructurado en HTML para el restablecimiento de contraseñas."""
    api_key = os.environ.get("BREVO_API_KEY")
    from_email = os.environ.get("BREVO_FROM_EMAIL")
    from_name = os.environ.get("BREVO_FROM_NAME", "Defensa Civil Bellavista")
    
    if not api_key or not from_email:
        print("[SMTP ADVERTENCIA]: BREVO_API_KEY o BREVO_FROM_EMAIL no configurados en Render.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    # URL dinámica basada en el host del servidor de Render
    # Modificar "tu-app-render.onrender.com" por tu subdominio real si es necesario
    url_recuperacion = f"https://tu-app-render.onrender.com/reset-password.html?token={token}"

    data = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": email, "name": nombre}],
        "subject": "Restablecer tu contraseña — Defensa Civil Bellavista",
        "htmlContent": f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 30px; color: #1f2937;">
                <h2 style="color: #1e3a8a; margin-bottom: 20px;">Restablecimiento de Contraseña</h2>
                <p>Estimado(a) <strong>{nombre}</strong>,</p>
                <p>Hemos recibido una solicitud para cambiar la contraseña vinculada a tu cuenta de acceso al Sistema de Gestión de Emergencias de Defensa Civil.</p>
                <p>Para completar este proceso de forma segura, por favor haz clic en el botón inferior:</p>
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{url_recuperacion}" style="background-color: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Restablecer mi Contraseña</a>
                </div>
                <p style="font-size: 13px; color: #4b5563;">Si el enlace no responde, puedes copiar la siguiente dirección directamente en la barra de tu navegador web:</p>
                <p style="font-size: 12px; color: #2563eb; word-break: break-all; background-color: #f3f4f6; padding: 10px; border-radius: 4px;">{url_recuperacion}</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                <p style="font-size: 11px; color: #9ca3af; text-align: center;">Si tú no iniciaste esta solicitud, ignora este mensaje. El token vencerá en el tiempo límite estipulado.</p>
            </div>
        """
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code in [200, 201, 202]:
            print(f"[SMTP ÉXITO]: Correo de recuperación enviado correctamente a: {email}")
            return True
        else:
            print(f"[SMTP API ERROR]: Brevo respondió con código {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[SMTP EXCEPCIÓN CRÍTICA]: Error en canal de comunicación HTTP con Brevo: {e}")
        return False

def enviar_verificacion(email, nombre, token):
    """Envía el código de verificación inicial para activar la cuenta."""
    api_key = os.environ.get("BREVO_API_KEY")
    from_email = os.environ.get("BREVO_FROM_EMAIL")
    from_name = os.environ.get("BREVO_FROM_NAME", "Defensa Civil Bellavista")
    
    if not api_key or not from_email:
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": api_key, "content-type": "application/json"}
    
    data = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": email, "name": nombre}],
        "subject": "Código de Verificación — Sistema de Defensa Civil",
        "htmlContent": f"<h3>Hola, {nombre}</h3><p>Tu código de activación de cuenta es: <strong>{token}</strong></p>"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception:
        return False

def enviar_bienvenida(email, nombre, username):
    """Envía un correo de confirmación una vez verificado el usuario."""
    api_key = os.environ.get("BREVO_API_KEY")
    from_email = os.environ.get("BREVO_FROM_EMAIL")
    from_name = os.environ.get("BREVO_FROM_NAME", "Defensa Civil Bellavista")
    
    if not api_key or not from_email:
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": api_key, "content-type": "application/json"}
    
    data = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": email, "name": nombre}],
        "subject": "¡Bienvenido al Sistema de Defensa Civil!",
        "htmlContent": f"<h3>Registro Exitoso</h3><p>Hola {nombre}, tu usuario '{username}' ha sido activado correctamente.</p>"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception:
        return False