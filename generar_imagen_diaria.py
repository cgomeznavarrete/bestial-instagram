#!/usr/bin/env python3
"""
Agente generador de imágenes diarias para Instagram - Salsas Bestial
Estrategia: genera el FONDO con IA y compone encima la botella REAL (original).
Esto garantiza que el frasco siempre sea 100% auténtico.

Uso:
    python generar_imagen_diaria.py              # genera la imagen de hoy
    python generar_imagen_diaria.py --forzar     # regenera aunque ya exista la de hoy
    python generar_imagen_diaria.py --listar     # muestra imágenes generadas

Requiere:
    ANTHROPIC_API_KEY  - Claude (planificación del prompt)
    GOOGLE_API_KEY     - Gemini (generación del fondo)
    pip install anthropic google-genai rembg pillow
"""

import anthropic
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Cargar .env automáticamente (sin dependencias externas)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            if not os.environ.get(_k.strip()):
                os.environ[_k.strip()] = _v.strip()

from PIL import Image, ImageFilter, ImageEnhance
import io

# ─── Configuración ────────────────────────────────────────────────────────────

CARPETA_INSTAGRAM = Path(__file__).parent / "Imagenes Instgram"
IMAGENES_REFERENCIA = [
    CARPETA_INSTAGRAM / "Salsa Bestial.JPEG",
    CARPETA_INSTAGRAM / "Salsa Bestial2.JPEG",
]
# Imagen de referencia de la tapa (siempre se envía junto al frasco)
IMAGEN_TAPA = CARPETA_INSTAGRAM / "Tapa.jpg"
HISTORIAL_JSON = CARPETA_INSTAGRAM / "historial_generaciones.json"

BRAND = "Salsas Bestial"
TAMANO_FINAL = 1080  # píxeles (cuadrado Instagram)

# ─── Contextos ────────────────────────────────────────────────────────────────

CONTEXTOS = [
    {
        "id": "asado_familiar",
        "nombre": "Asado familiar",
        "fondo_prompt": "Rustic wooden cutting board on a backyard BBQ table. Around the board: juicy grilled beef ribs with char marks, a choripan sandwich, grilled chicken on a steel grill grate with glowing coals and wisps of white smoke. Warm golden-hour afternoon sunlight. Blurred background: green backyard, family gathering around the BBQ. Professional food photography, no bottles, no labels, no products.",
        "ambiente": "tarde dorada, jardín, humo de parrilla",
        "hashtags": ["#asado", "#parrillada", "#asadocolombiano", "#familytime", "#bbqtime", "#carnealaparrilla"],
    },
    {
        "id": "parrilla_premium",
        "nombre": "Parrilla premium",
        "fondo_prompt": "Dark dramatic close-up of a professional steel BBQ grill with glowing orange coals, a thick juicy T-bone steak sizzling on the grate with char marks and steam. Dramatic fire light from below, moody dark background, ember sparks. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "luz dramática de brasas, fondo oscuro",
        "hashtags": ["#parrilla", "#steaklovers", "#asadorpremium", "#grillmaster", "#carnedeRes", "#parrillero"],
    },
    {
        "id": "mesa_madera_rustica",
        "nombre": "Mesa de madera rústica",
        "fondo_prompt": "Rustic reclaimed wood table top, natural morning light from a window. Around the center space: fresh red chili peppers, garlic cloves, herbs (cilantro, parsley), a wooden spoon, open tacos on a wooden board, lime halves. Warm natural tones. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "luz natural de mañana, mesa rústica",
        "hashtags": ["#mesarustica", "#comidareal", "#instafood", "#homecooked", "#foodstyling", "#comidalatina"],
    },
    {
        "id": "evento_deportivo",
        "nombre": "Evento deportivo",
        "fondo_prompt": "Living room watch party setup. On a wooden coffee table: a bowl of nachos with melted cheese, buffalo chicken wings on a plate, a spread of game day snacks. Blurred background: large TV screen showing a soccer/football match, friends cheering. Warm indoor lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "sala de estar, partido en TV, amigos",
        "hashtags": ["#watchparty", "#futbol", "#gamefood", "#snacktime", "#friendsandfood", "#deportes"],
    },
    {
        "id": "cocina_moderna",
        "nombre": "Cocina moderna",
        "fondo_prompt": "Modern kitchen marble countertop, bright clean lighting. Around the center: a freshly made gourmet pizza with toppings (pepperoni, fresh basil, mozzarella), scattered fresh ingredients, a wooden pizza cutter. Clean white and grey tones with warm accent light. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "cocina limpia, luz brillante, mármol",
        "hashtags": ["#cocinamoderna", "#pizzalovers", "#gourmet", "#foodphotography", "#cheflife", "#receta"],
    },
    {
        "id": "picnic_campo",
        "nombre": "Picnic al aire libre",
        "fondo_prompt": "Outdoor picnic setup on green grass, golden afternoon sunlight. A woven picnic blanket with gourmet sandwiches, a wooden cheese board with crackers and grapes, fresh vegetables, a wicker basket. Blurred background: trees and sunlit meadow. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "campo verde, luz de tarde, manta de picnic",
        "hashtags": ["#picnic", "#airlibre", "#naturaleza", "#outdoorfood", "#campestre", "#finde"],
    },
    {
        "id": "terraza_noche",
        "nombre": "Terraza nocturna",
        "fondo_prompt": "Rooftop terrace at night, warm string lights overhead. On a dark wood table: a plate of tapas and pinchos, mini burgers, skewers of grilled meat, small bowls of dipping sauces. Blurred background: city skyline at night with lights. Warm bokeh lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "terraza, noche, luces de ciudad",
        "hashtags": ["#terrazanocturna", "#viernes", "#nightout", "#sobremesa", "#tapas", "#ciudadnocturna"],
    },
    {
        "id": "playa_verano",
        "nombre": "Playa y verano",
        "fondo_prompt": "Beach picnic table, golden hour sunlight. On a weathered wooden table: grilled shrimp skewers, fish tacos on corn tortillas, lime wedges, fresh mango salsa in a bowl. Blurred background: tropical beach, palm trees, ocean waves. Warm summer colors. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "playa, verano, luz dorada",
        "hashtags": ["#playa", "#verano", "#vacaciones", "#seafood", "#playacolombia", "#tropicalfood"],
    },
    {
        "id": "cumpleanos_fiesta",
        "nombre": "Fiesta y celebración",
        "fondo_prompt": "Festive party table, colorful decoration. On the table: buffalo chicken wings, mini sliders, a bowl of nachos, party appetizers on small plates. Blurred background: colorful balloons, confetti, celebration mood, string lights. Warm festive lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "fiesta, globos, luces de celebración",
        "hashtags": ["#cumpleanos", "#fiesta", "#partyfood", "#celebracion", "#appetizers", "#birthdayparty"],
    },
    {
        "id": "desayuno_brunch",
        "nombre": "Desayuno / Brunch",
        "fondo_prompt": "Bright cozy brunch table, white linen tablecloth, morning light from a window. On the table: scrambled eggs on toast, a shakshuka pan with poached eggs, fresh herbs on top, sliced avocado, coffee cup. Soft warm morning tones. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "mañana luminosa, desayuno, lino blanco",
        "hashtags": ["#brunch", "#desayuno", "#brunchtime", "#morningvibes", "#weekendbrunch", "#huevos"],
    },
    {
        "id": "street_food",
        "nombre": "Street food / Mercado",
        "fondo_prompt": "Vibrant street food market stall, colorful and energetic atmosphere. On a wooden counter: freshly made tacos al pastor with cilantro and onion, a steaming corn on the cob (elote), fresh lime wedges. Blurred background: busy market with colorful stalls and lights. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "mercado, colores vivos, ambiente urbano",
        "hashtags": ["#streetfood", "#mercado", "#comidacallejera", "#tacos", "#antojitos", "#foodmarket"],
    },
    {
        "id": "cocina_campo",
        "nombre": "Cocina de campo / Rancho",
        "fondo_prompt": "Rustic ranch kitchen, warm wood fire light. On a rough hewn wooden table: a cast iron skillet with a whole roasted chicken, fresh rosemary, roasted garlic, crusty bread on a wooden board. Warm amber firelight, stone wall background. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "fogón de leña, cocina rústica, hierro fundido",
        "hashtags": ["#cocinacampo", "#rancho", "#fogon", "#comidarustica", "#cocinacriolla", "#campo"],
    },
    {
        "id": "post_entrenamiento",
        "nombre": "Post entrenamiento / Healthy",
        "fondo_prompt": "Clean healthy meal prep table, bright modern kitchen. On the table: grilled chicken breast sliced, a protein bowl with rice and vegetables, fresh salad, sliced avocado, lemon wedges. Clean white and green tones, natural daylight. No bottles, no labels, no products. Food photography, healthy lifestyle.",
        "ambiente": "cocina moderna, comida saludable, luz natural",
        "hashtags": ["#postworkout", "#saludable", "#healthyfood", "#mealprep", "#fitness", "#comidasana"],
    },
    {
        "id": "mesa_restaurante",
        "nombre": "Mesa de restaurante",
        "fondo_prompt": "Elegant restaurant table, candlelight ambiance. On the dark wood table: a gourmet smash burger with lettuce and tomato on a wooden board, a side of crispy fries in a metal basket, a small ramekin of dipping sauce. Warm candlelight, blurred restaurant background. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "restaurante, velas, ambiente elegante",
        "hashtags": ["#restaurante", "#finedining", "#burgerlovers", "#cenaconestilo", "#gourmet", "#restaurantecol"],
    },
]


# ─── Historial ─────────────────────────────────────────────────────────────────

def cargar_historial() -> dict:
    if HISTORIAL_JSON.exists():
        with open(HISTORIAL_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generaciones": [], "contextos_usados": []}


def guardar_historial(historial: dict):
    with open(HISTORIAL_JSON, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def elegir_contexto(historial: dict) -> dict:
    usados = historial.get("contextos_usados", [])
    frecuencias = {c["id"]: 0 for c in CONTEXTOS}
    for uso in usados:
        if uso in frecuencias:
            frecuencias[uso] += 1
    return sorted(CONTEXTOS, key=lambda c: frecuencias[c["id"]])[0]


# ─── Paso 1: Generar caption con Claude ───────────────────────────────────────

def generar_caption_claude(contexto: dict, fecha_str: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    print(f"Planificando caption para: {contexto['nombre']}...")

    system = f"""Eres el content creator oficial de {BRAND}.

TONO Y ESTILO (obligatorio):
- Comercial y con proposito: cada post debe despertar el deseo de comprar/pedir la salsa.
- Directo y apasionado. Habla de TU al cliente.
- El producto es Salsa Tatemada artesanal hecha con habaneros rostizados al fuego — sabor ahumado y profundo.
- Resalta como la salsa TRANSFORMA cualquier comida y es indispensable en la mesa.
- Cierra siempre con un llamado a la accion claro: pedir, probar, conseguirla.
- Sin emojis en exceso. Maximo 2-3 por post, usados con intencion.
- Lenguaje natural y cercano, NUNCA corporativo ni genericamente motivacional.

EJEMPLO DE LO QUE BUSCAMOS:
"Hay comidas que saben bien... y comidas que saben BESTIAL.
La diferencia esta en la salsa.
Nuestra Salsa Tatemada es hecha artesanalmente con habaneros rostizados al fuego. Ese sabor ahumado y profundo que transforma cualquier comida y lleva cada bocado a otro nivel.
Pruebala una vez y tu mesa nunca volvera a estar sin ella.
Haz tu pedido ahora:"

EJEMPLO DE LO QUE NO DEBES HACER (estilo incorrecto):
- "El mercado huele a gloria y tu antojo ya esta gritando — sin una Bestial encima le falta alma" (demasiado informal, sin CTA comercial)
- Frases solo de hype sin mencionar el producto o invitar a pedirlo."""

    hashtags_contexto = " ".join(contexto.get("hashtags", []))
    hashtags_marca = "#salsasbestial #salsatatemada #picante #bestial"

    prompt = f"""Crea el contenido para un post de Instagram de {BRAND}.
Contexto de la imagen: {contexto['nombre']} — {contexto['ambiente']}
Fecha: {fecha_str}

El caption (para el FEED) debe:
1. Abrir con una frase que conecte el contexto con la necesidad de la salsa.
2. Describir el producto (Salsa Tatemada, habaneros al fuego, sabor ahumado) de forma apetitosa.
3. Cerrar con llamado a la accion para hacer el pedido.
4. Tener entre 4 y 6 lineas. Sin listas. Sin bullets.

La caption_story (para STORIES de Instagram) debe:
- Ser una version ultra-corta del caption: maximo 2 lineas.
- Tono directo e impactante. Terminar con CTA fuerte (ej: "Pedila ahora 🔥").
- No mas de 2 emojis.

Hashtags del contexto (usar todos): {hashtags_contexto}
Hashtags de marca (agregar siempre): {hashtags_marca}
Total de hashtags en el array: entre 9 y 11.

Devuelve solo este JSON (sin markdown):
{{
  "caption": "texto completo del post con saltos de linea",
  "caption_story": "version corta para story, max 2 lineas",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6", "#tag7", "#tag8", "#tag9", "#tag10"]
}}"""

    respuesta = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )

    texto = respuesta.content[0].text.strip().strip("```json").strip("```").strip()
    return json.loads(texto)


# ─── Utilidad: cargar imagen de referencia en base64 ──────────────────────────

def _cargar_imagen_b64(ruta: Path) -> dict:
    """Carga una imagen y devuelve el dict inline_data para Gemini."""
    ext = ruta.suffix.lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media_type = media_types.get(ext, "image/jpeg")
    with open(ruta, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"inline_data": {"mime_type": media_type, "data": data}}


def _partes_referencia(indice_botella: int) -> list:
    """
    Devuelve siempre las 3 partes de referencia del producto:
      1. Salsa Bestial.JPEG o Salsa Bestial2.JPEG (alternando)
      2. La otra imagen del frasco
      3. Tapa.jpg — imprescindible para reproducir el logo de la tapa
    """
    refs_existentes = [r for r in IMAGENES_REFERENCIA if r.exists()]
    if not refs_existentes:
        print("ERROR: No se encontraron imagenes de referencia del frasco.")
        sys.exit(1)

    # Alternar entre las dos fotos del frasco
    ref_principal = refs_existentes[indice_botella % len(refs_existentes)]
    ref_secundaria = refs_existentes[(indice_botella + 1) % len(refs_existentes)]

    partes = [_cargar_imagen_b64(ref_principal)]
    if ref_secundaria != ref_principal:
        partes.append(_cargar_imagen_b64(ref_secundaria))

    # Siempre incluir la tapa
    if IMAGEN_TAPA.exists():
        partes.append(_cargar_imagen_b64(IMAGEN_TAPA))
        print(f"Referencias: {ref_principal.name} + {ref_secundaria.name} + {IMAGEN_TAPA.name}")
    else:
        print(f"ADVERTENCIA: {IMAGEN_TAPA.name} no encontrada — el logo de la tapa puede fallar")
        print(f"Referencias: {ref_principal.name} + {ref_secundaria.name}")

    return partes


# ─── Paso 2a: Imagen estilo MESA (comida, sin personas) ───────────────────────

def generar_imagen_mesa(contexto: dict, indice_botella: int) -> Image.Image:
    from google import genai
    from google.genai import types as gtypes

    client_gemini = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    partes_ref = _partes_referencia(indice_botella)

    prompt_completo = f"""You are a professional food photographer shooting a real campaign for "Salsa Bestial" hot sauce.
I am providing {len(partes_ref)} reference photos of the REAL product: views of the jar from the front/side AND a top-down view of the lid.
Reproduce the jar EXACTLY as it appears in these photos — no changes to shape, label, colors, logo, typography, or lid branding.
NO people in this image — food and product only.

JAR — COPY FROM REFERENCES EXACTLY:
Use every reference photo to faithfully reproduce ALL parts of the jar:
- Front/side photos: jar shape, glass, label colors, gorilla logo on label, BESTIAL lettering, sauce visible through glass
- Lid photo: the branded lid with logo printed on top must match exactly — reproduce it faithfully when the lid is visible
Do NOT redraw, reinterpret or redesign any part of the product.

JAR SIZE & PROPORTIONS — STRICTLY ENFORCED:
The jar is 230ml compote-style — the size of a small jam jar (roughly 8cm tall × 7cm wide).
MANDATORY size rules — violating any of these is an error:
- The jar must be SMALLER than a standard drinking glass or cup
- The jar must be at least 3× smaller in apparent size than a dinner plate or cutting board
- Place it naturally to the side or corner of the scene, like a condiment left on the table
- Position the jar so its label faces the camera and is clearly readable
- Never centered, never dominating the frame
- If in doubt, make the jar smaller — it is a small product

LIGHTING INTEGRATION — CRITICAL:
The jar must be lit by the EXACT same light source as every other element in the scene.
- Match the scene's light direction, color temperature and intensity on the jar
- The glass must show reflections of surrounding elements
- Cast a realistic shadow from the jar onto the surface below it
- This MUST look like ONE coherent photograph — not a product pasted onto a background

SCENE:
Context: {contexto['nombre']} — {contexto['fondo_prompt']}
Natural food-photography angle (slightly elevated, 30-45 degrees). Realistic depth of field.
Square format (1:1), 1080x1080px. No text overlays, no watermarks."""

    print(f"Generando imagen MESA con Gemini ({contexto['nombre']})...")

    parts = partes_ref + [{"text": prompt_completo}]
    response = client_gemini.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[{"parts": parts}],
        config=gtypes.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    imagen_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            imagen_bytes = part.inline_data.data
            break

    if imagen_bytes is None:
        raise ValueError("Gemini no devolvio una imagen (mesa)")

    print("Imagen MESA generada.")
    img = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
    return img.resize((TAMANO_FINAL, TAMANO_FINAL), Image.LANCZOS)


# ─── Paso 2b: Imagen estilo PERSONAS (lifestyle con gente) ────────────────────

def generar_imagen_personas(contexto: dict, indice_botella: int) -> Image.Image:
    from google import genai
    from google.genai import types as gtypes

    client_gemini = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    partes_ref = _partes_referencia(indice_botella)

    prompt_completo = f"""You are a professional lifestyle and advertising photographer shooting a real campaign for "Salsa Bestial" hot sauce.
I am providing {len(partes_ref)} reference photos of the REAL product: views of the jar from the front/side AND a top-down view of the lid.
Reproduce the jar EXACTLY as it appears in these photos — no changes to shape, label, colors, logo, typography, or lid branding.

PEOPLE — CRITICAL:
Include 2-3 real people (friends or family, Latin American appearance, ages 25-40) naturally sharing a meal together.
People are the HERO of this image — their expressions, laughter, or conversation are the focus.
The scene must feel authentic and candid, not posed like a stock photo.
People should be interacting naturally: passing food, talking, laughing, or adding sauce to their plate.

JAR — COPY FROM REFERENCES EXACTLY:
- Front/side photos: jar shape, glass, label colors, gorilla logo, BESTIAL lettering
- Lid photo: branded lid with logo on top — reproduce faithfully when visible
Do NOT redraw, reinterpret or redesign any part of the product.

JAR SIZE & PROPORTIONS — STRICTLY ENFORCED:
The jar is 230ml compote-style — the size of a small jam jar (roughly 8cm tall × 7cm wide).
MANDATORY size rules — violating any of these is an error:
- The jar must be SMALLER than a standard drinking glass or cup
- The jar must be SMALLER than a dinner plate (at least 3× smaller in apparent size)
- A person's hand holding the jar must look natural — like holding a jam jar, not a large bottle
- Place the jar to the side of the scene as a condiment, never dominating the frame
If in doubt, make the jar smaller — it is a small product.

SCENE & REALISM:
Context: {contexto['nombre']} — {contexto['ambiente']}
Warm, inviting atmosphere. Natural depth of field — people sharp, background softly blurred.
Consistent, realistic lighting matching the scene. The image must feel like a real candid photo.
Square format (1:1), 1080x1080px. No text overlays, no watermarks."""

    print(f"Generando imagen PERSONAS con Gemini ({contexto['nombre']})...")

    parts = partes_ref + [{"text": prompt_completo}]
    response = client_gemini.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[{"parts": parts}],
        config=gtypes.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    imagen_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            imagen_bytes = part.inline_data.data
            break

    if imagen_bytes is None:
        raise ValueError("Gemini no devolvio una imagen (personas)")

    print("Imagen PERSONAS generada.")
    img = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
    return img.resize((TAMANO_FINAL, TAMANO_FINAL), Image.LANCZOS)


# ─── Guardar resultado y metadata ─────────────────────────────────────────────

def guardar_resultado(imagen: Image.Image, nombre_archivo: str, contexto: dict,
                      caption_data: dict, fecha_str: str) -> Path:
    ruta_imagen = CARPETA_INSTAGRAM / nombre_archivo
    imagen.convert("RGB").save(ruta_imagen, "PNG", optimize=True)
    print(f"Imagen guardada: {ruta_imagen.name}")

    nombre_md = nombre_archivo.replace(".png", ".md")
    ruta_md = CARPETA_INSTAGRAM / nombre_md
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(f"# Imagen Instagram - {fecha_str}\n\n")
        f.write(f"**Contexto:** {contexto['nombre']}\n")
        f.write(f"**Contexto ID:** {contexto['id']}\n\n")
        f.write(f"## Caption\n\n{caption_data.get('caption', '')}\n\n")
        caption_story = caption_data.get("caption_story", "")
        if caption_story:
            f.write(f"## Caption Story\n\n{caption_story}\n\n")
        hashtags = " ".join(caption_data.get("hashtags", []))
        f.write(f"## Hashtags\n\n{hashtags}\n")
    print(f"Metadata guardada: {ruta_md.name}")
    return ruta_imagen


# ─── Flujo principal ───────────────────────────────────────────────────────────

def generar_imagen_hoy(forzar: bool = False, fecha_override: str = None):
    fecha_hoy = datetime.strptime(fecha_override, "%Y%m%d") if fecha_override else datetime.now()
    fecha_str = fecha_hoy.strftime("%d/%m/%Y")
    fecha_id = fecha_hoy.strftime('%Y%m%d')
    nombre_mesa     = f"bestial_{fecha_id}_mesa.png"
    nombre_personas = f"bestial_{fecha_id}_personas.png"
    ruta_mesa     = CARPETA_INSTAGRAM / nombre_mesa
    ruta_personas = CARPETA_INSTAGRAM / nombre_personas

    if ruta_mesa.exists() and ruta_personas.exists() and not forzar:
        print(f"Ya existen las imagenes de hoy: {nombre_mesa} y {nombre_personas}")
        print("Usa --forzar para regenerar.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY")
        sys.exit(1)
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Falta GOOGLE_API_KEY")
        sys.exit(1)
    refs_existentes = [r for r in IMAGENES_REFERENCIA if r.exists()]
    if not refs_existentes:
        print("No se encontro ninguna imagen de referencia en la carpeta.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  AGENTE IMAGENES INSTAGRAM - {BRAND}")
    print(f"  Fecha: {fecha_str}")
    print(f"  Generando 2 imagenes: MESA + PERSONAS")
    print(f"{'='*60}\n")

    historial = cargar_historial()
    contexto = elegir_contexto(historial)
    print(f"Contexto del dia: {contexto['nombre']}\n")

    indice_botella = len(historial.get("generaciones", [])) % max(len(IMAGENES_REFERENCIA), 1)

    # 1. Caption con Claude (compartido para ambas imagenes)
    caption_data = generar_caption_claude(contexto, fecha_str)

    # 2a. Imagen MESA
    if not ruta_mesa.exists() or forzar:
        imagen_mesa = generar_imagen_mesa(contexto, indice_botella)
        guardar_resultado(imagen_mesa, nombre_mesa, contexto, caption_data, fecha_str)
        historial["generaciones"].append({
            "fecha": fecha_str,
            "archivo": nombre_mesa,
            "tipo": "mesa",
            "contexto_id": contexto["id"],
            "contexto_nombre": contexto["nombre"],
        })

    # 2b. Imagen PERSONAS
    if not ruta_personas.exists() or forzar:
        imagen_personas = generar_imagen_personas(contexto, indice_botella)
        guardar_resultado(imagen_personas, nombre_personas, contexto, caption_data, fecha_str)
        historial["generaciones"].append({
            "fecha": fecha_str,
            "archivo": nombre_personas,
            "tipo": "personas",
            "contexto_id": contexto["id"],
            "contexto_nombre": contexto["nombre"],
        })

    historial["contextos_usados"].append(contexto["id"])
    guardar_historial(historial)

    print(f"\nImagenes del dia listas!")
    print(f"  Mesa:     {nombre_mesa}")
    print(f"  Personas: {nombre_personas}")
    print(f"  Caption e hashtags en: bestial_{fecha_id}_mesa.md\n")


def listar_imagenes():
    historial = cargar_historial()
    generaciones = historial.get("generaciones", [])
    if not generaciones:
        print("No hay imagenes generadas todavia.")
        return
    print(f"\nImagenes generadas ({len(generaciones)}):\n")
    for gen in generaciones:
        ruta = CARPETA_INSTAGRAM / gen["archivo"]
        estado = "OK" if ruta.exists() else "NO ENCONTRADA"
        print(f"  [{estado}] {gen['fecha']} - {gen['contexto_nombre']} -> {gen['archivo']}")
    print()


if __name__ == "__main__":
    args = sys.argv[1:]
    fecha_arg = None
    if "--fecha" in args:
        idx = args.index("--fecha")
        fecha_arg = args[idx + 1] if idx + 1 < len(args) else None
    if "--listar" in args:
        listar_imagenes()
    elif "--forzar" in args:
        generar_imagen_hoy(forzar=True, fecha_override=fecha_arg)
    else:
        generar_imagen_hoy(forzar=False, fecha_override=fecha_arg)
