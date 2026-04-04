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


def registrar_publicacion(archivo: str, tipo: str, ig_media_id: str, contexto_id: str = ""):
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
        "contexto_id": contexto_id,
        "metricas": {},
    })
    guardar_log(log)


# ─── Leer imágenes disponibles ────────────────────────────────────────────────

def _parsear_md(md_content: str) -> tuple[str, str, str, str]:
    """Extrae caption, caption_story, hashtags y contexto_id de un archivo .md generado."""
    caption_lines = []
    story_lines = []
    hashtags = ""
    contexto_id = ""
    in_caption = False
    in_story = False
    in_hashtags = False

    for line in md_content.split("\n"):
        stripped = line.strip()

        # Extraer contexto_id de la línea "**Contexto ID:** valor"
        if stripped.startswith("**Contexto ID:**"):
            contexto_id = stripped.replace("**Contexto ID:**", "").strip()
            continue

        if stripped.startswith("## Caption Story"):
            in_caption, in_story, in_hashtags = False, True, False
            continue
        if stripped == "## Caption":
            in_caption, in_story, in_hashtags = True, False, False
            continue
        if stripped.startswith("## Hashtags"):
            in_caption, in_story, in_hashtags = False, False, True
            continue
        if stripped.startswith("## ") or stripped.startswith("# "):
            in_caption, in_story, in_hashtags = False, False, False

        if in_caption and stripped:
            caption_lines.append(stripped)
        if in_story and stripped:
            story_lines.append(stripped)
        if in_hashtags and stripped:
            hashtags = stripped

    caption = "\n\n".join(caption_lines)
    caption_story = "\n".join(story_lines)
    return caption, caption_story, hashtags, contexto_id


def obtener_imagenes_disponibles() -> list[dict]:
    """
    Retorna lista de imágenes con metadata, más reciente primero.
    Solo incluye imágenes con su archivo .md correspondiente.
    Excluye imágenes _story (son derivadas).
    """
    imagenes = []
    for png in sorted(CARPETA_INSTAGRAM.glob("bestial_*.png"), reverse=True):
        if png.stem.endswith("_story"):
            continue
        md_file = png.with_suffix(".md")
        if not md_file.exists():
            continue
        caption, caption_story, hashtags, contexto_id = _parsear_md(
            md_file.read_text(encoding="utf-8")
        )
        texto = caption
        if hashtags:
            texto += "\n\n" + hashtags
        imagenes.append({
            "archivo": png.name,
            "ruta": str(png),
            "caption": caption,
            "caption_story": caption_story,
            "hashtags": hashtags,
            "texto_completo": texto,
            "contexto_id": contexto_id,
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

    registrar_publicacion(imagen["archivo"], "post", media_id, imagen.get("contexto_id", ""))
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

    # Mostrar caption sugerido para agregar como texto/sticker manualmente
    caption_story = imagen.get("caption_story", "")
    if caption_story:
        print(f"\n  💬 Texto sugerido para sticker en la story:")
        print(f"  ┌{'─'*50}")
        for linea in caption_story.split("\n"):
            print(f"  │ {linea}")
        print(f"  └{'─'*50}")

    registrar_publicacion(imagen["archivo"], "story", media_id, imagen.get("contexto_id", ""))
    return media_id


# ─── Carousel ────────────────────────────────────────────────────────────────

def es_semana_carousel() -> bool:
    """Semanas pares → carousel (MESA + PERSONAS). Semanas impares → post individual."""
    semana_iso = datetime.now().isocalendar()[1]
    return (semana_iso % 2 == 0)


def _crear_contenedor_hijo(account_id: str, url: str, token: str) -> str:
    """Crea un contenedor de media para un ítem de carousel."""
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media",
        params={
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publicar_carousel(imagen_mesa: dict, imagen_personas: dict) -> str:
    """
    Publica ambas imágenes del día (MESA + PERSONAS) como un carousel.
    Retorna el media ID del carousel.
    """
    token, account_id = _credenciales()

    print(f"\n  Carousel: {imagen_mesa['archivo']} + {imagen_personas['archivo']}")

    url_mesa     = url_github(imagen_mesa["archivo"])
    url_personas = url_github(imagen_personas["archivo"])

    # 1. Crear contenedores hijo
    print("  Creando contenedores hijo...")
    id_mesa     = _crear_contenedor_hijo(account_id, url_mesa, token)
    id_personas = _crear_contenedor_hijo(account_id, url_personas, token)
    print(f"  Hijo 1 (mesa):     {id_mesa}")
    print(f"  Hijo 2 (personas): {id_personas}")

    # 2. Crear contenedor carousel
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media",
        params={
            "media_type": "CAROUSEL",
            "children": f"{id_mesa},{id_personas}",
            "caption": imagen_mesa["texto_completo"],
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    carousel_id = resp.json()["id"]
    print(f"  Contenedor carousel: {carousel_id}")

    # 3. Esperar
    _esperar_contenedor(account_id, carousel_id, token)

    # 4. Publicar
    resp = requests.post(
        f"{INSTAGRAM_API_URL}/{account_id}/media_publish",
        params={"creation_id": carousel_id, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"  ✅ CAROUSEL publicado — Media ID: {media_id}")

    registrar_publicacion(imagen_mesa["archivo"],     "post", media_id, imagen_mesa.get("contexto_id", ""))
    registrar_publicacion(imagen_personas["archivo"], "post", media_id, imagen_personas.get("contexto_id", ""))
    return media_id


def _buscar_par_del_dia(imagenes: list[dict]) -> tuple[dict | None, dict | None]:
    """
    Busca el par MESA + PERSONAS más reciente no publicado para hacer carousel.
    Retorna (imagen_mesa, imagen_personas) o (None, None) si no hay par disponible.
    """
    log = cargar_log()
    publicados = set(log.get("publicados", []))

    # Agrupar por fecha (prefijo bestial_YYYYMMDD)
    por_fecha: dict[str, dict] = {}
    for img in imagenes:
        nombre = img["archivo"]
        if nombre.endswith("_mesa.png"):
            fecha = nombre.replace("bestial_", "").replace("_mesa.png", "")
            por_fecha.setdefault(fecha, {})["mesa"] = img
        elif nombre.endswith("_personas.png"):
            fecha = nombre.replace("bestial_", "").replace("_personas.png", "")
            por_fecha.setdefault(fecha, {})["personas"] = img

    # Buscar la fecha más reciente donde ambas estén sin publicar
    for fecha in sorted(por_fecha.keys(), reverse=True):
        par = por_fecha[fecha]
        if "mesa" not in par or "personas" not in par:
            continue
        mesa     = par["mesa"]
        personas = par["personas"]
        if (f"post:{mesa['archivo']}" not in publicados and
                f"post:{personas['archivo']}" not in publicados):
            return mesa, personas

    return None, None


# ─── Tareas programadas ──────────────────────────────────────────────────────

def tarea_post():
    semana = datetime.now().isocalendar()[1]
    carousel = es_semana_carousel()
    modo = "CAROUSEL" if carousel else "INDIVIDUAL"
    print(f"\n{'═'*60}")
    print(f"  📸 POST AUTOMÁTICO — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Semana {semana} → modo {modo}")
    print(f"{'═'*60}")

    imagenes = obtener_imagenes_disponibles()

    if carousel:
        mesa, personas = _buscar_par_del_dia(imagenes)
        if not mesa or not personas:
            print("  ⚠️  No hay par MESA+PERSONAS disponible para carousel. Publicando individual.")
            carousel = False
        else:
            try:
                publicar_carousel(mesa, personas)
                return
            except Exception as e:
                print(f"  ❌ Error en carousel: {e}")
                return

    if not carousel:
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


# ─── Analytics ───────────────────────────────────────────────────────────────

def _obtener_metricas_post(media_id: str, token: str) -> dict:
    """
    Obtiene métricas de alcance e impresiones de un post publicado.
    Retorna dict con las métricas disponibles (puede estar vacío si el post es muy reciente).
    """
    metricas = {}
    try:
        # Intentar obtener insights (requiere permisos instagram_manage_insights)
        resp = requests.get(
            f"{INSTAGRAM_API_URL}/{media_id}/insights",
            params={
                "metric": "reach,impressions,saved",
                "access_token": token,
            },
            timeout=20,
        )
        if resp.ok:
            for item in resp.json().get("data", []):
                metricas[item["name"]] = item["values"][0]["value"] if item.get("values") else item.get("value", 0)
    except Exception:
        pass

    try:
        # Obtener likes y comments directamente del objeto media
        resp2 = requests.get(
            f"{INSTAGRAM_API_URL}/{media_id}",
            params={
                "fields": "like_count,comments_count,timestamp",
                "access_token": token,
            },
            timeout=20,
        )
        if resp2.ok:
            data = resp2.json()
            if "like_count" in data:
                metricas["likes"] = data["like_count"]
            if "comments_count" in data:
                metricas["comments"] = data["comments_count"]
    except Exception:
        pass

    return metricas


def actualizar_metricas():
    """
    Recorre todos los posts publicados en el log y actualiza sus métricas
    desde la Graph API. Solo actualiza si el post tiene media_id y las métricas están vacías.
    """
    try:
        token, _ = _credenciales()
    except ValueError as e:
        print(f"  ❌ {e}")
        return

    log = cargar_log()
    actualizados = 0

    for entrada in log.get("posts", []):
        media_id = entrada.get("ig_media_id", "")
        if not media_id:
            continue
        metricas_actuales = entrada.get("metricas", {})
        # Solo actualizar si vacías o faltan reach/likes
        if metricas_actuales.get("reach") and metricas_actuales.get("likes"):
            continue
        nuevas = _obtener_metricas_post(media_id, token)
        if nuevas:
            entrada["metricas"] = {**metricas_actuales, **nuevas}
            actualizados += 1
            print(f"  ✅ {entrada['archivo']} — reach: {nuevas.get('reach','?')} likes: {nuevas.get('likes','?')}")

    guardar_log(log)
    print(f"\n  Métricas actualizadas: {actualizados} posts")


def reporte_rendimiento():
    """
    Muestra ranking de contextos por alcance promedio e informe de los últimos posts.
    """
    log = cargar_log()
    posts = log.get("posts", [])

    if not posts:
        print("\n  No hay posts publicados aún.")
        return

    # Agrupar por contexto_id
    por_contexto: dict[str, list] = {}
    sin_contexto = []
    for p in posts:
        cid = p.get("contexto_id", "")
        metricas = p.get("metricas", {})
        if not cid:
            sin_contexto.append(p)
            continue
        por_contexto.setdefault(cid, []).append(metricas)

    print(f"\n  {'═'*55}")
    print(f"  📊 REPORTE DE RENDIMIENTO — SALSAS BESTIAL")
    print(f"  {'═'*55}")
    print(f"  Total posts publicados: {len(posts)}\n")

    # Ranking por reach promedio
    ranking = []
    for cid, lista_metricas in por_contexto.items():
        reaches = [m.get("reach", 0) for m in lista_metricas if m.get("reach")]
        likes   = [m.get("likes", 0) for m in lista_metricas if m.get("likes")]
        saved   = [m.get("saved", 0) for m in lista_metricas if m.get("saved")]
        ranking.append({
            "contexto_id": cid,
            "posts": len(lista_metricas),
            "reach_avg": sum(reaches) / len(reaches) if reaches else 0,
            "likes_avg": sum(likes) / len(likes) if likes else 0,
            "saved_avg": sum(saved) / len(saved) if saved else 0,
        })

    ranking.sort(key=lambda x: x["reach_avg"], reverse=True)

    if ranking:
        print(f"  🏆 Ranking por alcance promedio:\n")
        print(f"  {'#':<3} {'Contexto':<25} {'Posts':<6} {'Reach':<8} {'Likes':<7} {'Guardados'}")
        print(f"  {'─'*60}")
        for i, r in enumerate(ranking, 1):
            reach = f"{r['reach_avg']:.0f}" if r["reach_avg"] else "—"
            likes = f"{r['likes_avg']:.1f}" if r["likes_avg"] else "—"
            saved = f"{r['saved_avg']:.1f}" if r["saved_avg"] else "—"
            print(f"  {i:<3} {r['contexto_id']:<25} {r['posts']:<6} {reach:<8} {likes:<7} {saved}")

    # Últimos 5 posts con métricas
    print(f"\n  📅 Últimos 5 posts:\n")
    for p in posts[-5:]:
        m = p.get("metricas", {})
        reach = m.get("reach", "—")
        likes = m.get("likes", "—")
        print(f"  {p['fecha']}  {p['archivo']}")
        print(f"    reach: {reach}  likes: {likes}  contexto: {p.get('contexto_id','?')}")
    print()


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
    semana = datetime.now().isocalendar()[1]
    modo_post = "CAROUSEL" if es_semana_carousel() else "INDIVIDUAL"
    print("\n" + "═"*55)
    print("  🌶️   AGENTE PUBLICADOR INSTAGRAM — SALSAS BESTIAL")
    print("═"*55)
    print(f"  Semana {semana} → próximo post en modo {modo_post}")
    print("-"*55)
    print("  1. Publicar POST ahora (automático)")
    print("  2. Publicar STORY ahora (automático)")
    print("  3. Ver imágenes disponibles")
    print("  4. Ver historial de publicaciones")
    print("  5. Activar modo automático (horario semanal)")
    print("  6. Actualizar métricas desde Instagram")
    print("  7. Ver reporte de rendimiento por contexto")
    print("  8. Salir")
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
            print("\n  Actualizando métricas...")
            actualizar_metricas()

        elif opcion == "7":
            reporte_rendimiento()

        elif opcion == "8":
            print("\n  👋 ¡Hasta luego!\n")
            break

        else:
            print("  ❌ Opción no válida.")


if __name__ == "__main__":
    # Modo automático CLI: python publicar_instagram.py --post | --story | --preparar-story
    if len(sys.argv) > 1:
        _validar_credenciales()
        if sys.argv[1] == "--post":
            tarea_post()
        elif sys.argv[1] == "--story":
            tarea_story()
        elif sys.argv[1] == "--preparar-story":
            # Solo prepara la imagen story (9:16) y la guarda en disco.
            # Usado por GitHub Actions para subirla al repo ANTES de publicar.
            imagen = seleccionar_imagen("story")
            if imagen:
                _adaptar_story(imagen["ruta"])
                print(f"  Story preparada: {imagen['archivo']}")
            else:
                print("  ⚠️  No hay imágenes disponibles para story.")
        else:
            print(f"Argumento desconocido: {sys.argv[1]}")
            sys.exit(1)
    else:
        main()
