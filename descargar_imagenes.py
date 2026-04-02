#!/usr/bin/env python3
"""
Descarga automáticamente las imágenes nuevas generadas en GitHub.
Se ejecuta con Task Scheduler cuando el computador está encendido.
"""
import json
import os
import urllib.request
from pathlib import Path
from datetime import datetime

# Cargar .env local
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            if not os.environ.get(_k.strip()):
                os.environ[_k.strip()] = _v.strip()

REPO         = os.environ.get("GITHUB_REPO", "")          # usuario/repositorio
TOKEN        = os.environ.get("GITHUB_TOKEN_LOCAL", "")   # token de acceso personal
CARPETA      = Path(__file__).parent / "Imagenes Instgram"

LOG = Path(__file__).parent / "descarga_log.txt"

def log(msg):
    linea = f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] {msg}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def descargar():
    if not REPO:
        log("ERROR: GITHUB_REPO no está configurado en .env")
        return

    headers = {"User-Agent": "BestialBot/1.0"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"

    api_url = f"https://api.github.com/repos/{REPO}/contents/Imagenes%20Instgram"
    req = urllib.request.Request(api_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            archivos = json.loads(resp.read())
    except Exception as e:
        log(f"Error consultando GitHub: {e}")
        return

    descargados = 0
    for archivo in archivos:
        if archivo.get("type") != "file":
            continue
        nombre = archivo["name"]
        ruta_local = CARPETA / nombre

        # Descargar imágenes nuevas y el historial actualizado
        if not ruta_local.exists() and (nombre.startswith("bestial_") or nombre == "historial_generaciones.json"):
            dl_req = urllib.request.Request(archivo["download_url"], headers=headers)
            try:
                with urllib.request.urlopen(dl_req, timeout=60) as resp:
                    ruta_local.write_bytes(resp.read())
                log(f"Descargado: {nombre}")
                descargados += 1
            except Exception as e:
                log(f"Error descargando {nombre}: {e}")

    if descargados == 0:
        log("Sin imágenes nuevas.")
    else:
        log(f"{descargados} archivo(s) descargado(s) en {CARPETA}")

CARPETA.mkdir(exist_ok=True)
descargar()
