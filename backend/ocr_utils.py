"""
ocr_utils.py — OCR mejorado para DNI y nombres con preprocesamiento de imagen.
"""
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Firmas mágicas de formatos de imagen permitidos
_MAGIC = [
    (b'\xff\xd8\xff', 'jpg'),
    (b'\x89PNG\r\n',  'png'),
    (b'GIF87a',       'gif'),
    (b'GIF89a',       'gif'),
    (b'RIFF',         'webp'),
    (b'BM',           'bmp'),
    (b'II*\x00',      'tiff'),
    (b'MM\x00*',      'tiff'),
]


def es_imagen_valida(ruta: str) -> bool:
    try:
        with open(ruta, 'rb') as f:
            header = f.read(10)
        return any(header.startswith(magic) for magic, _ in _MAGIC)
    except Exception:
        return False


def _preprocesar(img: Image.Image) -> Image.Image:
    """Convierte a escala de grises, escala y mejora contraste."""
    img = img.convert('RGB').convert('L')
    w, h = img.size
    # Asegurar al menos 1800px de ancho para buena resolución OCR
    if w < 1800:
        escala = 1800 / w
        img = img.resize((int(w * escala), int(h * escala)), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(2.2)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def extraer_texto_imagen(ruta: str) -> str:
    """
    Ejecuta OCR en dos pasadas:
    1. Texto completo en español (para nombre y contexto)
    2. Solo dígitos (para el número de DNI)
    Retorna ambos concatenados.
    """
    try:
        img      = Image.open(ruta)
        img_proc = _preprocesar(img)

        # Pasada 1: texto general
        cfg1   = '--psm 6 --oem 3'
        texto1 = pytesseract.image_to_string(img_proc, lang='spa', config=cfg1)

        # Pasada 2: modo línea de texto, más agresivo
        cfg2   = '--psm 3 --oem 3'
        texto2 = pytesseract.image_to_string(img_proc, lang='spa', config=cfg2)

        # Pasada 3: sólo dígitos para el número de DNI
        cfg3   = '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789'
        img_h  = img_proc.crop((0, 0, img_proc.width, img_proc.height // 2))
        texto3 = pytesseract.image_to_string(img_h, lang='spa', config=cfg3)

        return texto1 + '\n' + texto2 + '\n' + texto3
    except Exception as e:
        print(f'[OCR] Error procesando imagen: {e}')
        return ''


def extraer_dni(texto: str):
    """
    Extrae número de DNI (8 dígitos) del texto OCR.
    Prueba múltiples estrategias de mayor a menor confianza.
    """
    if not texto:
        return None

    # Estrategia 1: MRZ — el DNI aparece como 8 dígitos seguidos de < o espacio
    # Ejemplo: "12345678<4PER..."
    mrz = re.search(r'\b(\d{8})[<\s]', texto)
    if mrz:
        return mrz.group(1)

    # Estrategia 2: 8 dígitos exactos en una línea (sin dígitos adyacentes)
    exactos = re.findall(r'(?<!\d)(\d{8})(?!\d)', texto)
    if exactos:
        # Preferir los que no empiezan en 0 (DNI peruano no empieza en 0)
        for n in exactos:
            if n[0] != '0':
                return n
        return exactos[0]

    # Estrategia 3: dígitos separados por puntos, guiones o espacios
    patron = r'\d[\s\.\-]?\d[\s\.\-]?\d[\s\.\-]?\d[\s\.\-]?\d[\s\.\-]?\d[\s\.\-]?\d[\s\.\-]?\d'
    matches = re.findall(patron, texto)
    for m in matches:
        limpio = re.sub(r'[\s\.\-]', '', m)
        if len(limpio) == 8:
            return limpio

    # Estrategia 4: 7-9 dígitos consecutivos (OCR puede agregar/quitar 1 dígito)
    grupos = re.findall(r'\d{7,9}', texto)
    for g in grupos:
        if len(g) == 8:
            return g
        if len(g) == 9 and g[0] != '0':
            return g[1:]   # quitar primer dígito si OCR lo inventó

    return None


def extraer_nombre_familia(texto: str) -> str:
    """
    Extrae el nombre más probable de la persona del texto OCR.
    Busca líneas con al menos 2 palabras capitalizadas y sin números.
    """
    if not texto:
        return 'No se pudo leer'

    # Palabras que indican que la línea NO es un nombre
    _EXCLUIR = {
        'dni', 'documento', 'republica', 'peru', 'peruano', 'nacional',
        'identidad', 'registro', 'civil', 'emision', 'expiracion', 'firma',
        'lugar', 'nacimiento', 'sexo', 'estado', 'ubigeo', 'cod', 'codigo',
        'datos', 'valido', 'hasta', 'fecha', 'numero', 'serie', 'tipo',
        'mrz', 'huella', 'digital', 'restricciones', 'titular',
    }

    candidatos = []
    for linea in texto.split('\n'):
        linea = linea.strip()
        palabras = linea.split()
        if (
            len(palabras) >= 2
            and not re.search(r'\d', linea)
            and 6 <= len(linea) <= 70
            and not any(p.lower() in _EXCLUIR for p in palabras)
        ):
            candidatos.append(linea)

    return candidatos[0] if candidatos else 'No se pudo leer'
