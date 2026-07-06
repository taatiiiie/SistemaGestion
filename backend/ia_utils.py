"""
ia_utils.py — Integración con IA para el Sistema de Defensa Civil.
Soporta:
  - Google Gemini (GRATIS - aistudio.google.com)
  - Anthropic Claude (pago - console.anthropic.com)
Prioridad: Claude > Gemini > Tesseract OCR (fallback)
"""
import base64
import json
import os

import requests
import config   # carga las claves desde config.env

# ── PROMPTS ──────────────────────────────────────────────────────────────────

_PROMPT_DNI = """Eres un sistema experto en lectura de DNI peruanos (Documento Nacional de Identidad del Perú).
Analiza la imagen con MAXIMA ATENCION y extrae todos los datos visibles.

DATOS DEL DNI PERUANO:
- Numero de DNI: exactamente 8 digitos
- Apellidos: APELLIDO_PATERNO APELLIDO_MATERNO (en mayusculas)
- Nombres: NOMBRES DE PILA (en mayusculas)
- Fecha de nacimiento: DD/MM/YYYY
- Lugar de nacimiento
- Ubigeo: 6 digitos
- Sexo: M o F
- Fechas de emision y expiracion: DD/MM/YYYY
- Restricciones: 4 digitos (ej: 0000)

Responde UNICAMENTE con JSON valido, sin texto adicional:
{
  "dni": "8 digitos exactos o null",
  "apellido_paterno": "en mayusculas o null",
  "apellido_materno": "en mayusculas o null",
  "nombres": "en mayusculas o null",
  "nombre_completo": "APELLIDOS NOMBRES completo o null",
  "fecha_nacimiento": "DD/MM/YYYY o null",
  "lugar_nacimiento": "ciudad o departamento o null",
  "ubigeo": "6 digitos o null",
  "sexo": "M o F o null",
  "estado_civil": "S/C/D/V o null",
  "fecha_emision": "DD/MM/YYYY o null",
  "fecha_expiracion": "DD/MM/YYYY o null",
  "restricciones": "4 digitos o null",
  "confianza": 0.0,
  "notas": "observacion sobre legibilidad de la imagen"
}"""

_PROMPT_VIVIENDA = """Eres un inspector tecnico certificado de Defensa Civil de la Municipalidad Distrital de Bellavista, Peru.
Analiza las fotos de la vivienda afectada y realiza una evaluacion tecnica de danos.

Escala de nivel de dano:
- LEVE: Danos superficiales, la vivienda es segura para habitar
- MODERADO: Danos estructurales menores, habitable con restricciones
- GRAVE: Danos estructurales significativos, no habitable temporalmente
- MUY_GRAVE: Danos severos, riesgo de colapso, evacuacion inmediata

Responde UNICAMENTE con JSON valido:
{
  "nivel_dano": "LEVE o MODERADO o GRAVE o MUY_GRAVE",
  "tipos_dano": ["grietas", "humedad", "derrumbe_parcial", "inundacion", "incendio", "deslizamiento", "asentamiento", "otro"],
  "zonas_afectadas": ["techo", "paredes_exteriores", "paredes_interiores", "columnas", "vigas", "piso", "cimientos", "ventanas", "puertas"],
  "habitabilidad": "HABITABLE o CON_RESTRICCIONES o NO_HABITABLE",
  "descripcion_tecnica": "Descripcion tecnica profesional de 3-4 oraciones para el informe oficial de Defensa Civil.",
  "acciones_urgentes": ["accion prioritaria 1", "accion prioritaria 2"],
  "requiere_apuntalamiento": false,
  "requiere_evacuacion": false,
  "confianza": 0.0,
  "notas": "observaciones adicionales"
}"""


# ── HELPERS ──────────────────────────────────────────────────────────────────

def ia_disponible() -> bool:
    from config import proveedor_ia
    return proveedor_ia() != ''


def _img_b64(ruta: str) -> tuple:
    ext  = os.path.splitext(ruta)[1].lower()
    mime = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png',
            '.webp':'image/webp','.bmp':'image/jpeg','.tiff':'image/jpeg','.gif':'image/gif'
            }.get(ext, 'image/jpeg')
    with open(ruta, 'rb') as f:
        data = base64.standard_b64encode(f.read()).decode('utf-8')
    return data, mime


def _parsear_json(texto: str) -> dict:
    texto = texto.strip()
    if '```' in texto:
        for bloque in texto.split('```'):
            bloque = bloque.strip().lstrip('json').strip()
            if bloque.startswith('{'):
                texto = bloque
                break
    # Limpiar caracteres de control que puedan romper el JSON
    texto = ''.join(c for c in texto if ord(c) >= 32 or c in '\n\r\t')
    return json.loads(texto)


# ── GEMINI ───────────────────────────────────────────────────────────────────

def _gemini_analizar_dni(ruta: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    img_data, mime = _img_b64(ruta)

    resp = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=[
            types.Part.from_bytes(data=base64.b64decode(img_data), mime_type=mime),
            types.Part.from_text(text=_PROMPT_DNI),
        ],
    )
    return _parsear_json(resp.text)


def _gemini_analizar_vivienda(rutas: list) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    partes = []
    for ruta in rutas[:4]:
        try:
            img_data, mime = _img_b64(ruta)
            partes.append(types.Part.from_bytes(data=base64.b64decode(img_data), mime_type=mime))
        except Exception:
            pass
    partes.append(types.Part.from_text(text=_PROMPT_VIVIENDA))

    resp = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=partes,
    )
    return _parsear_json(resp.text)


# ── GROQ ─────────────────────────────────────────────────────────────────────

_GROQ_URL   = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'


def _groq_chat(img_data: str, mime: str, prompt: str) -> str:
    headers = {
        'Authorization': f"Bearer {os.environ['GROQ_API_KEY']}",
        'Content-Type': 'application/json',
    }
    payload = {
        'model': _GROQ_MODEL,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{img_data}'}},
                {'type': 'text', 'text': prompt},
            ],
        }],
        'max_tokens': 700,
    }
    r = requests.post(_GROQ_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def _groq_analizar_dni(ruta: str) -> dict:
    img_data, mime = _img_b64(ruta)
    return _parsear_json(_groq_chat(img_data, mime, _PROMPT_DNI))


def _groq_analizar_vivienda(rutas: list) -> dict:
    img_data, mime = _img_b64(rutas[0])
    return _parsear_json(_groq_chat(img_data, mime, _PROMPT_VIVIENDA))


# ── ANTHROPIC ────────────────────────────────────────────────────────────────

def _anthropic_analizar_dni(ruta: str) -> dict:
    import anthropic
    cliente   = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    img_data, mime = _img_b64(ruta)
    msg = cliente.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=500,
        messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': img_data}},
            {'type': 'text', 'text': _PROMPT_DNI}
        ]}]
    )
    return _parsear_json(msg.content[0].text)


def _anthropic_analizar_vivienda(rutas: list) -> dict:
    import anthropic
    cliente = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    content = []
    for ruta in rutas[:4]:
        img_data, mime = _img_b64(ruta)
        content.append({'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': img_data}})
    content.append({'type': 'text', 'text': _PROMPT_VIVIENDA})
    msg = cliente.messages.create(
        model='claude-haiku-4-5-20251001', max_tokens=600,
        messages=[{'role': 'user', 'content': content}]
    )
    return _parsear_json(msg.content[0].text)


# ── API PÚBLICA ───────────────────────────────────────────────────────────────

def analizar_dni(ruta: str) -> dict:
    """Extrae datos del DNI usando IA. Retorna {} si falla o no hay IA."""
    if not ruta or not os.path.isfile(ruta):
        return {}
    from config import proveedor_ia
    proveedor = proveedor_ia()
    if not proveedor:
        return {}
    try:
        if proveedor == 'anthropic':
            resultado = _anthropic_analizar_dni(ruta)
        elif proveedor == 'groq':
            resultado = _groq_analizar_dni(ruta)
        else:
            resultado = _gemini_analizar_dni(ruta)
        print(f'[IA-DNI/{proveedor}] DNI={resultado.get("dni")} '
              f'Nombre={resultado.get("nombre_completo")} '
              f'Confianza={resultado.get("confianza")}')
        return resultado
    except json.JSONDecodeError as e:
        print(f'[IA-DNI] Error JSON: {e}')
        return {}
    except Exception as e:
        print(f'[IA-DNI] Error: {e}')
        return {}


def analizar_vivienda(rutas: list) -> dict:
    """Analiza daños en la vivienda. Retorna {} si falla o no hay IA."""
    rutas_ok = [r for r in (rutas or []) if r and os.path.isfile(r)]
    if not rutas_ok:
        return {}
    from config import proveedor_ia
    proveedor = proveedor_ia()
    if not proveedor:
        return {}
    try:
        if proveedor == 'anthropic':
            resultado = _anthropic_analizar_vivienda(rutas_ok)
        elif proveedor == 'groq':
            resultado = _groq_analizar_vivienda(rutas_ok)
        else:
            resultado = _gemini_analizar_vivienda(rutas_ok)
        print(f'[IA-Vivienda/{proveedor}] Nivel={resultado.get("nivel_dano")} '
              f'Habitabilidad={resultado.get("habitabilidad")} '
              f'Confianza={resultado.get("confianza")}')
        return resultado
    except json.JSONDecodeError as e:
        print(f'[IA-Vivienda] Error JSON: {e}')
        return {}
    except Exception as e:
        print(f'[IA-Vivienda] Error: {e}')
        return {}
