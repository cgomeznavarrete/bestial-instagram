#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
"""
Agente publicador de Instagram - Salsas Bestial
════════════════════════════════════════════════
Publica automáticamente en horarios de máxima audiencia:
  • 2 posts en el FEED por semana  → Martes 12:00 PM y Viernes 12:00 PM
  • 4 STORIES por semana           → Lunes, Miércoles, Jueves, Sábado 10:00 AM

Fuente de imágenes: carpeta "Imagenes Instgram/" (generadas por generar_imagen_diaria.py)
Las imágenes se sirven directo desde GitHub (raw.githubusercontent.com) — sin costo.
Selecciona automáticamente la mejor imagen no publicada.

Requiere en .env:
  INSTAGRAM_ACCESS_TOKEN          - Token de larga duración (Instagram Graph API)
  INSTAGRAM_BUSINESS_ACCOUNT_ID   - ID numérico de la cuenta Business
  GITHUB_REPO                     - Ej: cgomeznavarrete/bestial-instagram

Instalar dependencias adicionales (si faltan):
  pip install requests schedule pillow
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import schedule
from PIL import Image

# ─── Cargar .env ──────────────────────────────────────────────────────────────

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            if not os.environ.get(_k.strip()):
                os.environ[_k.strip()] = _v.strip()

# ─── Configuración ────────────────────────────────────────────────────────────

CARPETA_INSTAGRAM = Path(__file__).parent / "Imagenes Instgram"
LOG_PUBLICACIONES  = CARPETA_INSTAGRAM / "publicaciones_log.json"
INSTAGRAM_API_URL  = "https://graph.instagram.com/v21.0"
GITHUB_RAW_BASE    = "https://raw.githubusercontent.com"

# ─── Horarios óptimos para México / LATAM ─────────────────────────────────────
#
#  Posts feed:
#    Martes  12:00 PM  — inicio de semana laboral + hora almuerzo (alto engagement)
#    Viernes 12:00 PM  — expectativa de fin de semana, gente planea parrillada / salida
#
#  Stories:
#    Lunes     10:00 AM  — arranque de semana, revisión de feed matutino
#    Miércoles 10:00 AM  — mitad de semana, buen alcance
#    Jueves    10:00 AM  — pre-viernes, audiencia activa
#    Sábado    10:00 AM  — fin de semana, parrilladas y reuniones en mente

# ─── Log de publicaciones ─────────────────────────────────────────────────────

def cargar_log() -> dict:
    if LOG_PUBLICACIONES.exists():
        with open(LOG_PUBLICACIONES, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": [], "stories": [], "publicados": []}


def guardar_log(log: dict):
    with open(LOG_PUBLICACIONES, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def registrar_publicacion(archivo: str, tipo: str, ig_media_id: str):
    log = cargar_log()
    clave = f"{tipo}:{archivo}"
    log.setdefault("publicados", [])
    if clave not in log["publicados"]:
        log["publicados"].append(clave)
    clave_lista = "posts" if tipo == "post" else "stories"
    log.setdefault(clave_lista, []).append({
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "archivo": archivo,
        "tipo": tipo,
        "ig_media_id": ig_media_id,
    })
    guardar_log(log)


# ─── Leer imágenes disponibles ────────────────────────────────────────────────

def _parsear_md(md_content: str) -> tuple[str, str]:
    """Extrae caption y hashtags de un archivo .md generado."""
    caption_lines = []
    hashtags = ""
    in_caption = False
    in_hashtags = False

    for line in md_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## Caption"):
            in_caption, in_hashtags = True, False
            continue
        if stripped.startswith("## Hashtags"):
            in_caption, in_hashtags = False, True
            continue
        if stripped.startswith("## ") or stripped.startswith("# "):
            in_caption, in_hashtags = False, False
        if in_caption and stripped:
            caption_lines.append(stripped)
        if in_hashtags and stripped:
            hashtags = stripped

    return "\n\n".join(caption_lines), hashtags


def obtener_imagenes_disponibles() -> list[dict]:
    """
    Retorna lista de imágenes con metadata, más reciente primero.
    Solo incluye imágenes con su archivo .md correspondiente.
    """
    imagenes = []
    for png in sorted(CARPETA_INSTAGRAM.glob("bestial_*.png"), reverse=True):
        md_file = png.with_suffix(".md")
        if not md_file.exists():
            continue
        caption, hashtags = _parsear_md(md_file.read_text(encoding="utf-8"))
        texto = caption
        if hashtags:
            texto += "\n\n" + hashtags
        imagenes.append({
            "archivo": png.name,
            "ruta": str(png),
            "caption": caption,
            "hashtags": hashtags,
            "texto_completo": texto,
        })
    return imagenes


def seleccionar_imagen(tipo: str) -> dict | None:
    """
    Selecciona la imagen más reciente no publicada del tipo dado.
    Si todas fueron usadas, rota a la más antigua (contenido siempre fresco primero).
    """
    log = cargar_log()
    publicados = set(log.get("publicados", []))
    imagenes = obtener_imagenes_disponibles()

    for img in imagenes:
        if f"{tipo}:{img['archivo']}" not in publicados:
            return img

    # Rotación: todas publicadas → usar la más antigua
    return imagenes[-1] if imagenes else None


# ─── URL pública vía GitHub (sin costo) ──────────────────────────────────────

def url_github(nombre_archivo: str) -> str:
    """
    Construye la URL raw de GitHub para la imagen.
    Las imágenes ya están en el repo — no se necesita ningún servicio externo.
    """
    repo = os.environ.get("GITHUB_REPO")
    if not repo:
        raise ValueError("Falta GITHUB_REPO en .env  (ej: cgomeznavarrete/bestial-instagram)")

    # Codificar el espacio en el nombre de la carpeta
    carpeta = "Imagenes%20Instgram"
    url = f"{GITHUB_RAW_BASE}/{repo}/main/{carpeta}/{nombre_archivo}"
    print(f"  URL imagen: {url}")
    return url


def url_github_story(nombre_archivo: str) -> str:
    """URL para la versión story (9:16) que se sube al repo antes de publicar."""
    repo = os.environ.get("GITHUB_REPO")
    if not repo:
        raise ValueError("Falta GITHUB_REPO en .env")
    carpeta = "Imagenes%20Instgram"
    nombre_story = nombre_archivo.replace(".png", "_story.png")
    return f"{GITHUB_RAW_BASE}/{repo}/main/{carpeta}/{nombre_story}"


# ─── Adaptar imagen para story (9:16) ────────────────────────────────────────

def _adaptar_story(ruta_original: str) -> str:
    """
    Convierte imagen cuadrada 1080x1080 a formato story 1080x1920.
    Guarda el resultado en la misma carpeta con sufijo _story.png
    para que GitHub Actions lo suba al repo y sea accesible por URL.
    """
    img = Image.open(ruta_original).convert("RGB")
    fondo = Image.new("RGB", (1080, 1920), (10, 10, 10))
    w, h = img.size
    offset_y = (1920 - h) // 2
    fondo.paste(img, (0, offset_y))

    ruta_story = ruta_original.replace(".png", "_story.png")
    fondo.save(ruta_story, "PNG", optimize=True)
    print(f"  Imagen story guardada: {Path(ruta_story).name}")
    return ruta_story


# ─── Instagram Graph API ─────────────────────────────────────────────────────

def _credenciales() -> tuple[str, str]:
    token      = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not token or not account_id:
        raise ValueError(
            "Faltan credenciales en .env:\n"
            "  INSTAGRAM_ACCESS_TOKEN\n"
            "  INSTAGRAM_BUSINESS_ACCOUNT_ID"
        )
    return token, account_id


def _esperar_contenedor(account_id: str, container_id: str, token: str, intentos: int = 10):
    """Espera a que el contenedor de media esté en estado FINISHED."""
    for i in range(intentos):
        resp = requests.get(
            f"{INSTAGRAM_API_URL}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        resp.raise_for_status()
        estado = resp.json().get("status_code", "")
        print(f"  Estado contenedor ({i+1}/{intentos}): {estado}")
        if estado == "FINISHED":
            return
        if estado == "ERROR":
            raise ValueError(f"Error en contenedor {container_id}")
        time.sleep(6)
    raise TimeoutError(f"Contenedor {container_id} no terminó de procesar")


def publicar_post(imagen: dict) -> str:
    """Publica imagen en el feed de Instagram. Retorna el media ID."""
    token, account_id = _credenciales()

    print(f"\n  Archivo : {imagen['archivo']}")
    print(f"  Caption : {imagen['caption'][:80]}...")

    # 1. URL pública desde GitHub (sin costo)
    url = url_github(imagen["archivo"])

    # 2. Crear contenedor de media
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media",
        params={
            "image_url": url,
            "caption": imagen["texto_completo"],
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    print(f"  Contenedor: {container_id}")

    # 3. Esperar que esté listo
    _esperar_contenedor(account_id, container_id, token)

    # 4. Publicar
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"  ✅ POST publicado — Media ID: {media_id}")

    registrar_publicacion(imagen["archivo"], "post", media_id)
    return media_id


def publicar_story(imagen: dict) -> str:
    """Publica imagen como story en Instagram. Retorna el media ID."""
    token, account_id = _credenciales()

    print(f"\n  Archivo : {imagen['archivo']}")

    # 1. Adaptar a 9:16 y guardar en carpeta (el repo ya tiene la imagen base,
    #    la versión _story.png se genera localmente y debe estar en GitHub antes
    #    de publicar — si el modo automático corre desde GitHub Actions, ya estará)
    _adaptar_story(imagen["ruta"])
    url = url_github_story(imagen["archivo"])

    # 2. Crear contenedor de story
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media",
        params={
            "image_url": url,
            "media_type": "STORIES",
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json()["id"]
    print(f"  Contenedor: {container_id}")

    # 3. Esperar
    _esperar_contenedor(account_id, container_id, token)

    # 4. Publicar
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"  ✅ STORY publicada — Media ID: {media_id}")

    registrar_publicacion(imagen["archivo"], "story", media_id)
    return media_id


# ─── Tareas programadas ──────────────────────────────────────────────────────

def tarea_post():
    print(f"\n{'═'*60}")
    print(f"  📸 POST AUTOMÁTICO — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'═'*60}")
    imagen = seleccionar_imagen("post")
    if not imagen:
        print("  ⚠️  No hay imágenes disponibles para publicar.")
        return
    try:
        publicar_post(imagen)
    except Exception as e:
        print(f"  ❌ Error: {e}")


def tarea_story():
    print(f"\n{'═'*60}")
    print(f"  📱 STORY AUTOMÁTICA — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'═'*60}")
    imagen = seleccionar_imagen("story")
    if not imagen:
        print("  ⚠️  No hay imágenes disponibles para story.")
        return
    try:
        publicar_story(imagen)
    except Exception as e:
        print(f"  ❌ Error: {e}")


def activar_modo_automatico():
    """
    Programa el calendario semanal de publicaciones:
      Posts:   Martes 12:00 PM | Viernes 12:00 PM
      Stories: Lunes 10:00 AM | Miércoles 10:00 AM | Jueves 10:00 AM | Sábado 10:00 AM
    """
    print("\n  ⏰ Modo automático activado:")
    print("  ┌─ POSTS (feed)")
    print("  │    Martes  12:00 PM")
    print("  │    Viernes 12:00 PM")
    print("  └─ STORIES")
    print("       Lunes     10:00 AM")
    print("       Miércoles 10:00 AM")
    print("       Jueves    10:00 AM")
    print("       Sábado    10:00 AM")
    print("\n  Presiona Ctrl+C para detener.\n")

    schedule.every().tuesday.at("12:00").do(tarea_post)
    schedule.every().friday.at("12:00").do(tarea_post)

    schedule.every().monday.at("10:00").do(tarea_story)
    schedule.every().wednesday.at("10:00").do(tarea_story)
    schedule.every().thursday.at("10:00").do(tarea_story)
    schedule.every().saturday.at("10:00").do(tarea_story)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n  ⏹  Modo automático detenido.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _listar_imagenes():
    imagenes = obtener_imagenes_disponibles()
    log = cargar_log()
    publicados = set(log.get("publicados", []))
    print(f"\n  📂 Imágenes en carpeta ({len(imagenes)} total):\n")
    for img in imagenes:
        p = "✅" if f"post:{img['archivo']}"  in publicados else "⬜"
        s = "✅" if f"story:{img['archivo']}" in publicados else "⬜"
        print(f"  {img['archivo']}  [post {p}] [story {s}]")
        if img["caption"]:
            prev = img["caption"][:70].replace("\n", " ")
            print(f"    → {prev}")
    print()


def _ver_historial():
    log = cargar_log()
    posts   = log.get("posts",   [])
    stories = log.get("stories", [])
    print(f"\n  📊 Historial (últimas 5 de cada tipo):\n")
    print(f"  Posts publicados: {len(posts)}")
    for p in posts[-5:]:
        print(f"    {p['fecha']}  {p['archivo']}")
    print(f"\n  Stories publicadas: {len(stories)}")
    for s in stories[-5:]:
        print(f"    {s['fecha']}  {s['archivo']}")
    print()


def menu():
    print("\n" + "═"*55)
    print("  🌶️   AGENTE PUBLICADOR INSTAGRAM — SALSAS BESTIAL")
    print("═"*55)
    print("  1. Publicar POST ahora (automático)")
    print("  2. Publicar STORY ahora (automático)")
    print("  3. Ver imágenes disponibles")
    print("  4. Ver historial de publicaciones")
    print("  5. Activar modo automático (horario semanal)")
    print("  6. Salir")
    print("-"*55)
    return input("  Opción: ").strip()


def _validar_credenciales():
    faltan = [v for v in [
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_BUSINESS_ACCOUNT_ID",
        "GITHUB_REPO",
    ] if not os.environ.get(v)]
    if faltan:
        print("\n  ⚠️  Faltan las siguientes variables en .env:\n")
        for v in faltan:
            print(f"    {v}")
        print("\n  Consulta el README de configuración para obtenerlas.")
        sys.exit(1)


def main():
    _validar_credenciales()

    while True:
        opcion = menu()

        if opcion == "1":
            img = seleccionar_imagen("post")
            if img:
                try:
                    publicar_post(img)
                except Exception as e:
                    print(f"\n  ❌ Error: {e}")
            else:
                print("\n  ❌ No hay imágenes disponibles.")

        elif opcion == "2":
            img = seleccionar_imagen("story")
            if img:
                try:
                    publicar_story(img)
                except Exception as e:
                    print(f"\n  ❌ Error: {e}")
            else:
                print("\n  ❌ No hay imágenes disponibles.")

        elif opcion == "3":
            _listar_imagenes()

        elif opcion == "4":
            _ver_historial()

        elif opcion == "5":
            activar_modo_automatico()

        elif opcion == "6":
            print("\n  👋 ¡Hasta luego!\n")
            break

        else:
            print("  ❌ Opción no válida.")


if __name__ == "__main__":
    # Modo automático CLI: python publicar_instagram.py --post | --story
    if len(sys.argv) > 1:
        _validar_credenciales()
        if sys.argv[1] == "--post":
            tarea_post()
        elif sys.argv[1] == "--story":
            tarea_story()
        else:
            print(f"Argumento desconocido: {sys.argv[1]}")
            sys.exit(1)
    else:
        main()
