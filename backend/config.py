"""
config.py — Carga variables de configuración desde config.env
Soporta Google Gemini (gratuito) y Anthropic Claude (pago).
"""
import os

_BASE = os.path.dirname(os.path.abspath(__file__))


def cargar_config():
    path = os.path.join(_BASE, 'config.env')
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                k, v = k.strip(), v.strip()
                if v and v != 'TU_CLAVE_AQUI':
                    os.environ.setdefault(k, v)


cargar_config()


def ia_configurada() -> bool:
    """Retorna True si hay al menos una clave de IA válida configurada."""
    anthropic = os.environ.get('ANTHROPIC_API_KEY', '')
    groq      = os.environ.get('GROQ_API_KEY', '')
    gemini    = os.environ.get('GEMINI_API_KEY', '')
    return bool(
        (anthropic and anthropic.startswith('sk-')) or
        (groq      and groq.startswith('gsk_')) or
        (gemini    and gemini != 'TU_CLAVE_AQUI')
    )


def proveedor_ia() -> str:
    """Retorna qué proveedor de IA está activo: 'anthropic', 'groq', 'gemini' o ''."""
    if os.environ.get('ANTHROPIC_API_KEY', '').startswith('sk-'):
        return 'anthropic'
    groq = os.environ.get('GROQ_API_KEY', '')
    if groq and groq.startswith('gsk_'):
        return 'groq'
    gemini = os.environ.get('GEMINI_API_KEY', '')
    if gemini and gemini != 'TU_CLAVE_AQUI':
        return 'gemini'
    return ''

def email_configurada():

    return bool(
        os.environ.get("BREVO_API_KEY")
    )