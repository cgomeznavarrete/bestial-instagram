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
    },
    {
        "id": "parrilla_premium",
        "nombre": "Parrilla premium",
        "fondo_prompt": "Dark dramatic close-up of a professional steel BBQ grill with glowing orange coals, a thick juicy T-bone steak sizzling on the grate with char marks and steam. Dramatic fire light from below, moody dark background, ember sparks. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "luz dramática de brasas, fondo oscuro",
    },
    {
        "id": "mesa_madera_rustica",
        "nombre": "Mesa de madera rústica",
        "fondo_prompt": "Rustic reclaimed wood table top, natural morning light from a window. Around the center space: fresh red chili peppers, garlic cloves, herbs (cilantro, parsley), a wooden spoon, open tacos on a wooden board, lime halves. Warm natural tones. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "luz natural de mañana, mesa rústica",
    },
    {
        "id": "evento_deportivo",
        "nombre": "Evento deportivo",
        "fondo_prompt": "Living room watch party setup. On a wooden coffee table: a bowl of nachos with melted cheese, buffalo chicken wings on a plate, a spread of game day snacks. Blurred background: large TV screen showing a soccer/football match, friends cheering. Warm indoor lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "sala de estar, partido en TV, amigos",
    },
    {
        "id": "cocina_moderna",
        "nombre": "Cocina moderna",
        "fondo_prompt": "Modern kitchen marble countertop, bright clean lighting. Around the center: a freshly made gourmet pizza with toppings (pepperoni, fresh basil, mozzarella), scattered fresh ingredients, a wooden pizza cutter. Clean white and grey tones with warm accent light. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "cocina limpia, luz brillante, mármol",
    },
    {
        "id": "picnic_campo",
        "nombre": "Picnic al aire libre",
        "fondo_prompt": "Outdoor picnic setup on green grass, golden afternoon sunlight. A woven picnic blanket with gourmet sandwiches, a wooden cheese board with crackers and grapes, fresh vegetables, a wicker basket. Blurred background: trees and sunlit meadow. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "campo verde, luz de tarde, manta de picnic",
    },
    {
        "id": "terraza_noche",
        "nombre": "Terraza nocturna",
        "fondo_prompt": "Rooftop terrace at night, warm string lights overhead. On a dark wood table: a plate of tapas and pinchos, mini burgers, skewers of grilled meat, small bowls of dipping sauces. Blurred background: city skyline at night with lights. Warm bokeh lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "terraza, noche, luces de ciudad",
    },
    {
        "id": "playa_verano",
        "nombre": "Playa y verano",
        "fondo_prompt": "Beach picnic table, golden hour sunlight. On a weathered wooden table: grilled shrimp skewers, fish tacos on corn tortillas, lime wedges, fresh mango salsa in a bowl. Blurred background: tropical beach, palm trees, ocean waves. Warm summer colors. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "playa, verano, luz dorada",
    },
    {
        "id": "cumpleanos_fiesta",
        "nombre": "Fiesta y celebración",
        "fondo_prompt": "Festive party table, colorful decoration. On the table: buffalo chicken wings, mini sliders, a bowl of nachos, party appetizers on small plates. Blurred background: colorful balloons, confetti, celebration mood, string lights. Warm festive lighting. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "fiesta, globos, luces de celebración",
    },
    {
        "id": "desayuno_brunch",
        "nombre": "Desayuno / Brunch",
        "fondo_prompt": "Bright cozy brunch table, white linen tablecloth, morning light from a window. On the table: scrambled eggs on toast, a shakshuka pan with poached eggs, fresh herbs on top, sliced avocado, coffee cup. Soft warm morning tones. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "mañana luminosa, desayuno, lino blanco",
    },
    {
        "id": "street_food",
        "nombre": "Street food / Mercado",
        "fondo_prompt": "Vibrant street food market stall, colorful and energetic atmosphere. On a wooden counter: freshly made tacos al pastor with cilantro and onion, a steaming corn on the cob (elote), fresh lime wedges. Blurred background: busy market with colorful stalls and lights. No bottles, no labels, no products. Lifestyle food photography.",
        "ambiente": "mercado, colores vivos, ambiente urbano",
    },
    {
        "id": "cocina_campo",
        "nombre": "Cocina de campo / Rancho",
        "fondo_prompt": "Rustic ranch kitchen, warm wood fire light. On a rough hewn wooden table: a cast iron skillet with a whole roasted chicken, fresh rosemary, roasted garlic, crusty bread on a wooden board. Warm amber firelight, stone wall background. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "fogón de leña, cocina rústica, hierro fundido",
    },
    {
        "id": "post_entrenamiento",
        "nombre": "Post entrenamiento / Healthy",
        "fondo_prompt": "Clean healthy meal prep table, bright modern kitchen. On the table: grilled chicken breast sliced, a protein bowl with rice and vegetables, fresh salad, sliced avocado, lemon wedges. Clean white and green tones, natural daylight. No bottles, no labels, no products. Food photography, healthy lifestyle.",
        "ambiente": "cocina moderna, comida saludable, luz natural",
    },
    {
        "id": "mesa_restaurante",
        "nombre": "Mesa de restaurante",
        "fondo_prompt": "Elegant restaurant table, candlelight ambiance. On the dark wood table: a gourmet smash burger with lettuce and tomato on a wooden board, a side of crispy fries in a metal basket, a small ramekin of dipping sauce. Warm candlelight, blurred restaurant background. No bottles, no labels, no products. Professional food photography.",
        "ambiente": "restaurante, velas, ambiente elegante",
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

    prompt = f"""Crea el contenido para un post de Instagram de {BRAND}.
Contexto de la imagen: {contexto['nombre']} — {contexto['ambiente']}
Fecha: {fecha_str}

El caption debe:
1. Abrir con una frase que conecte el contexto con la necesidad de la salsa.
2. Describir el producto (Salsa Tatemada, habaneros al fuego, sabor ahumado) de forma apetitosa.
3. Cerrar con llamado a la accion para hacer el pedido.
4. Tener entre 4 y 6 lineas. Sin listas. Sin bullets.

Devuelve solo este JSON (sin markdown):
{{
  "caption": "texto completo del post con saltos de linea",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6", "#tag7", "#tag8"]
}}"""

    respuesta = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )

    texto = respuesta.content[0].text.strip().strip("```json").strip("```").strip()
    return json.loads(texto)


# ─── Paso 2: Generar imagen completa con Gemini usando la botella como referencia

def generar_imagen_con_referencia(contexto: dict, indice_botella: int) -> Image.Image:
    from google import genai
    from google.genai import types as gtypes

    client_gemini = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    # Elegir referencia del día
    refs_existentes = [r for r in IMAGENES_REFERENCIA if r.exists()]
    if not refs_existentes:
        print("No se encontraron imagenes de referencia.")
        sys.exit(1)
    referencia = refs_existentes[indice_botella % len(refs_existentes)]
    print(f"Referencia del dia: {referencia.name}")

    # Leer imagen de referencia en base64
    ext = referencia.suffix.lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media_type = media_types.get(ext, "image/jpeg")
    with open(referencia, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt_completo = f"""You are a professional food photographer and advertising creative director.

I am giving you the REAL product image of "Salsa Bestial" artisanal hot sauce.
Your task: generate a complete, photorealistic Instagram marketing image for this product.

PRODUCT SIZE — CRITICAL:
The jar is a 230ml glass compote-style jar, approximately 8cm tall and 7cm wide — the size of a small jam or baby food jar.
It must appear REALISTICALLY SMALL compared to the food elements in the scene.
A dinner plate, cutting board or salad bowl should be visibly 3-4x larger than the jar.
Place the jar naturally to the side or corner of the scene, like a condiment would be placed at a table.
NEVER make the jar dominate the frame or appear larger than the main food elements.

LABEL & APPEARANCE — CRITICAL:
Reproduce the jar EXACTLY as shown in the reference image: same glass shape, same yellow label, same red BESTIAL lettering, same gorilla logo, same gold lid. Do NOT invent or modify anything.
The label must be fully readable and faithful to the reference.

SCENE & REALISM:
Context: {contexto['nombre']} — {contexto['fondo_prompt']}
The scene must look like a real photograph, not a CGI render. Use natural depth of field, realistic shadows, and consistent lighting across the jar and food elements.
Square format (1:1), 1080x1080px, professional food photography quality.
No text overlays, no watermarks.

Generate the complete realistic scene with the jar integrated naturally at correct scale."""

    print(f"Generando imagen completa con Gemini ({contexto['nombre']})...")

    response = client_gemini.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": media_type,
                            "data": img_b64,
                        }
                    },
                    {"text": prompt_completo},
                ]
            }
        ],
        config=gtypes.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    imagen_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            imagen_bytes = part.inline_data.data
            break

    if imagen_bytes is None:
        raise ValueError("Gemini no devolvio una imagen")

    print("Imagen generada.")
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
        f.write(f"**Contexto:** {contexto['nombre']}\n\n")
        f.write(f"## Caption\n\n{caption_data.get('caption', '')}\n\n")
        hashtags = " ".join(caption_data.get("hashtags", []))
        f.write(f"## Hashtags\n\n{hashtags}\n")
    print(f"Metadata guardada: {ruta_md.name}")
    return ruta_imagen


# ─── Flujo principal ───────────────────────────────────────────────────────────

def generar_imagen_hoy(forzar: bool = False, fecha_override: str = None):
    fecha_hoy = datetime.strptime(fecha_override, "%Y%m%d") if fecha_override else datetime.now()
    fecha_str = fecha_hoy.strftime("%d/%m/%Y")
    nombre_archivo = f"bestial_{fecha_hoy.strftime('%Y%m%d')}.png"
    ruta_imagen = CARPETA_INSTAGRAM / nombre_archivo

    if ruta_imagen.exists() and not forzar:
        print(f"Ya existe la imagen de hoy: {nombre_archivo}")
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
    print(f"  Estrategia: fondo IA + botella ORIGINAL superpuesta")
    print(f"{'='*60}\n")

    historial = cargar_historial()
    contexto = elegir_contexto(historial)
    print(f"Contexto del dia: {contexto['nombre']}\n")

    # 1. Caption con Claude
    caption_data = generar_caption_claude(contexto, fecha_str)

    # 2. Generar imagen completa con Gemini usando la botella real como referencia
    indice_botella = len(historial.get("generaciones", [])) % max(len(IMAGENES_REFERENCIA), 1)
    imagen_final = generar_imagen_con_referencia(contexto, indice_botella)

    # 3. Guardar
    guardar_resultado(imagen_final, nombre_archivo, contexto, caption_data, fecha_str)

    # 6. Historial
    historial["generaciones"].append({
        "fecha": fecha_str,
        "archivo": nombre_archivo,
        "contexto_id": contexto["id"],
        "contexto_nombre": contexto["nombre"],
    })
    historial["contextos_usados"].append(contexto["id"])
    guardar_historial(historial)

    print(f"\nImagen del dia lista!")
    print(f"  Archivo: {nombre_archivo}")
    print(f"  Caption e hashtags en: {nombre_archivo.replace('.png', '.md')}\n")


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
