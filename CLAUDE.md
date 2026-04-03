# Agente Instagram - Salsas Bestial

Genera 2 imágenes diarias para Instagram de @salsas.bestial con captions y hashtags en español.
Todo corre en la nube (GitHub Actions) sin necesidad de tener el computador encendido.

---

## Arquitectura

```
GitHub Actions (nube) — sin PC encendido
  9:00 AM Colombia  → generar_imagen_diaria.py  → 2 imágenes (MESA + PERSONAS) → sube al repo
  Martes/Viernes 12PM → publicar_instagram.py --post  → publica en feed Instagram
  L/Mi/Ju/Sa 10AM  → publicar_instagram.py --story → publica en stories Instagram

PC Local (cuando está encendido)
  Al iniciar Windows → descargar_imagenes.py → descarga imágenes nuevas desde GitHub
```

---

## Scripts principales

### `generar_imagen_diaria.py`
Genera 2 imágenes por día usando Claude (caption) + Gemini (imagen con referencia real del frasco).

```bash
python generar_imagen_diaria.py              # genera las imágenes de hoy
python generar_imagen_diaria.py --forzar    # regenera aunque ya existan
python generar_imagen_diaria.py --listar    # muestra historial
```

### `publicar_instagram.py`
Publica posts y stories en Instagram vía Graph API. Las imágenes se sirven desde GitHub raw.

```bash
python publicar_instagram.py                # menú interactivo
python publicar_instagram.py --post         # publica un post ahora
python publicar_instagram.py --story        # publica una story ahora
```

### `descargar_imagenes.py`
Descarga desde GitHub los archivos nuevos `bestial_*.png` y `historial_generaciones.json`.
Corre automáticamente al iniciar Windows (via `.bat` en carpeta Startup).

```bash
python descargar_imagenes.py                # ejecutar manualmente
```

### `instagram_agent.py`
Genera plan de contenido semanal completo (captions, guiones de reels, ideas de stories).

```bash
python instagram_agent.py                   # menú interactivo
```

---

## Reglas críticas — Generación de imágenes

### Dos tipos de imagen por día
- **MESA** (`bestial_YYYYMMDD_mesa.png`): solo comida, sin personas. Frasco como condimento a un lado.
- **PERSONAS** (`bestial_YYYYMMDD_personas.png`): 2-3 personas latinoamericanas (25-40 años) compartiendo comida. Estilo lifestyle, candidato, no stock photo.

### Frasco — proporciones CRÍTICAS
- El frasco es de **230ml tipo compota** (~8cm alto × 7cm ancho, tamaño mermelada pequeña).
- Debe verse **3-4x más pequeño** que un plato o tabla de cortar.
- Se coloca al costado o esquina como condimento. NUNCA domina el frame.
- Siempre pasar la imagen de referencia real a Gemini — NUNCA solo descripción de texto.
- Referencias: `Imagenes Instgram/Salsa Bestial.JPEG` y `Salsa Bestial2.JPEG` (alternan por día).

### Apariencia del frasco
Reproducir EXACTAMENTE: etiqueta amarilla · letras rojas BESTIAL · logo gorila · tapa dorada · vidrio tipo compota.

---

## Estilo de caption

**Tono**: comercial, directo, apasionado. Habla de TÚ. Máx 2-3 emojis con intención.

**Estructura obligatoria**:
1. Frase que conecta el contexto con la necesidad de la salsa
2. Describe el producto: Salsa Tatemada, habaneros rostizados al fuego, sabor ahumado
3. Cierre con CTA claro para hacer el pedido

**Ejemplo aprobado**:
> "Hay comidas que saben bien... y comidas que saben BESTIAL.
> La diferencia está en la salsa.
> Nuestra Salsa Tatemada es hecha artesanalmente con habaneros rostizados al fuego. Ese sabor ahumado y profundo que transforma cualquier comida.
> Haz tu pedido ahora."

**Evitar**:
- Frases solo de hype sin mencionar el producto ni invitar a pedirlo
- Lenguaje corporativo o genéricamente motivacional
- Más de 3 emojis
- Mencionar teléfonos, horarios o conservantes

---

## Contextos disponibles (14) — rotan automáticamente por menor uso

| ID | Nombre |
|----|--------|
| `asado_familiar` | Asado familiar |
| `parrilla_premium` | Parrilla premium |
| `mesa_madera_rustica` | Mesa de madera rústica |
| `evento_deportivo` | Evento deportivo |
| `cocina_moderna` | Cocina moderna |
| `picnic_campo` | Picnic al aire libre |
| `terraza_noche` | Terraza nocturna |
| `playa_verano` | Playa y verano |
| `cumpleanos_fiesta` | Fiesta y celebración |
| `desayuno_brunch` | Desayuno / Brunch |
| `street_food` | Street food / Mercado |
| `cocina_campo` | Cocina de campo / Rancho |
| `post_entrenamiento` | Post entrenamiento / Healthy |
| `mesa_restaurante` | Mesa de restaurante |

El historial y frecuencia de uso se guarda en `Imagenes Instgram/historial_generaciones.json`.

---

## GitHub Actions

**Repositorio**: `github.com/cgomeznavarrete/bestial-instagram` (privado)

| Workflow | Archivo | Horario |
|----------|---------|---------|
| Generar imágenes | `generar_imagen.yml` | 9:00 AM Colombia (14:00 UTC) diario |
| Publicar post | `publicar_instagram.yml` | 12:00 PM Colombia (17:00 UTC) · Martes y Viernes |
| Publicar story | `publicar_instagram.yml` | 10:00 AM Colombia (15:00 UTC) · L/Mi/Ju/Sá |

**Ejecutar manualmente**:
1. Ir a `github.com/cgomeznavarrete/bestial-instagram/actions`
2. Seleccionar workflow → "Run workflow"

**Secrets configurados en GitHub**:
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`

---

## Git workflow local — IMPORTANTE

GitHub Actions sube imágenes al repo en paralelo. Antes de hacer push siempre:

```bash
git pull --rebase origin main
git push
```

Si hay conflicto con archivos de imágenes al hacer pull:
```bash
git add "Imagenes Instgram/bestial_FECHA.png"
git stash
git pull --rebase origin main
git stash pop
git push
```

---

## Variables de entorno (`.env`)

```
ANTHROPIC_API_KEY=...          # Claude — generación de captions
GOOGLE_API_KEY=...             # Gemini — generación de imágenes
INSTAGRAM_ACCESS_TOKEN=...     # Token Instagram Login API (expira ~60 días)
INSTAGRAM_BUSINESS_ACCOUNT_ID=36080190431580119  # User ID de API (NO el del console)
GITHUB_REPO=cgomeznavarrete/bestial-instagram
GITHUB_TOKEN_LOCAL=...         # Token OAuth GitHub CLI (para descargar imágenes)
```

El `.env` está en `.gitignore` — nunca se sube al repo.

---

## Mantenimiento

### Token de Instagram (renovar cada ~60 días)
Próxima renovación: **~2026-06-01**

1. Ir a Meta Developers → App 976739284916354
2. Casos de uso → Configuración de la API con inicio de sesión con Instagram
3. Paso 2 → Generar token nuevo
4. Actualizar `INSTAGRAM_ACCESS_TOKEN` en:
   - `.env` local
   - GitHub Secret del repo

### Dependencias Python
```bash
pip install anthropic google-genai pillow requests
```

---

## Notas técnicas

- **Python local**: `C:/Python314/python.exe`
- **Carpeta de salida**: `Imagenes Instgram/` — el espacio en el nombre es intencional (nombre original)
- **Instagram Business Account ID para la API**: `36080190431580119` — es el User ID, NO el ID del Business Manager (`17841469613901943`)
- **Modelo de imagen**: `gemini-3-pro-image-preview` — requiere cuenta Google con plan de pago
- **Modelo de caption**: `claude-opus-4-6`
- **Descarga automática local**: `descargar_imagenes.bat` en carpeta Startup de Windows (`C:/Users/cgome/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/`)
