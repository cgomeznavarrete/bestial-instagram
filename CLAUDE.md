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
Genera 2 imágenes por día usando Claude (caption + caption_story) + Gemini (imagen con referencia real del frasco).
Claude devuelve JSON con `caption` (feed), `caption_story` (story, max 2 líneas) y `hashtags` contextuales.
Cada contexto tiene 6 hashtags propios + 4 de marca fija (`#salsasbestial #salsatatemada #picante #bestial`).

```bash
python generar_imagen_diaria.py              # genera las imágenes de hoy
python generar_imagen_diaria.py --forzar    # regenera aunque ya existan
python generar_imagen_diaria.py --listar    # muestra historial
```

### `publicar_instagram.py`
Publica posts y stories en Instagram vía Graph API. Las imágenes se sirven desde GitHub raw.
Alterna automáticamente entre post individual y carousel (MESA+PERSONAS) por semana:
- **Semanas impares** → post individual (imagen MESA o PERSONAS)
- **Semanas pares** → carousel con ambas imágenes del día

Al publicar una story muestra el `caption_story` como texto sugerido para agregar como sticker manualmente.

```bash
python publicar_instagram.py                # menú interactivo (8 opciones)
python publicar_instagram.py --post         # publica un post ahora (respeta semana carousel/individual)
python publicar_instagram.py --story        # publica una story ahora
```

**Opciones del menú interactivo**:
1. Publicar POST ahora
2. Publicar STORY ahora
3. Ver imágenes disponibles
4. Ver historial de publicaciones
5. Activar modo automático (horario semanal)
6. **Actualizar métricas desde Instagram** (reach, likes, guardados por post)
7. **Ver reporte de rendimiento por contexto** (ranking qué contextos funcionan mejor)
8. Salir

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

### Frasco — proporciones OBLIGATORIAS (regla crítica, no negociable)
El frasco es de **230ml tipo compota** (~8cm alto × 7cm ancho, tamaño mermelada pequeña).
Las siguientes reglas se aplican a TODAS las imágenes (mesa y personas). Violarlas es un error grave:

- El frasco **SIEMPRE debe ser más pequeño que un vaso o copa** en la escena
- El frasco debe verse **al menos 3× más pequeño** que un plato o tabla de cortar
- Si hay una mano sosteniendo el frasco, debe verse natural — como sostener una mermelada, no una botella grande
- Se coloca al costado o esquina como condimento. **NUNCA domina el frame**
- En caso de duda, el frasco va más pequeño — es un producto pequeño

### Imágenes de referencia — USO OBLIGATORIO
Siempre se deben pasar las **3 imágenes** a Gemini en cada generación:
- `Imagenes Instgram/Salsa Bestial.JPEG` — frasco vista frontal/lateral
- `Imagenes Instgram/Salsa Bestial2.JPEG` — frasco segunda referencia
- `Imagenes Instgram/Tapa.jpg` — tapa con logo impreso (crítica para reproducir el logo de la tapa)

**NUNCA** generar el frasco solo con descripción de texto. Las 3 referencias son obligatorias.
La función `_partes_referencia()` en el script carga y valida las 3 automáticamente.

### Apariencia del frasco — reproducir EXACTAMENTE de las referencias
- Etiqueta amarilla/dorada · letras rojas BESTIAL · logo gorila (color y estilo exacto de la referencia)
- Tapa dorada con logo impreso (ver Tapa.jpg)
- Vidrio tipo compota con salsa oscura visible
- NO inventar ni modificar ningún elemento del frasco

---

## Estilo de caption

**Tono**: comercial, directo, apasionado. Habla de TÚ. Máx 2-3 emojis con intención.

### Caption (feed) — estructura obligatoria
1. Frase que conecta el contexto con la necesidad de la salsa
2. Describe el producto: Salsa Tatemada, habaneros rostizados al fuego, sabor ahumado
3. Cierre con CTA claro para hacer el pedido
4. Entre 4 y 6 líneas. Sin listas ni bullets.

**Ejemplo aprobado**:
> "Hay comidas que saben bien... y comidas que saben BESTIAL.
> La diferencia está en la salsa.
> Nuestra Salsa Tatemada es hecha artesanalmente con habaneros rostizados al fuego. Ese sabor ahumado y profundo que transforma cualquier comida.
> Haz tu pedido ahora."

### Caption Story — versión corta
- Máximo 2 líneas. Tono impactante y directo.
- CTA fuerte al final (ej: "Pedila ahora 🔥").
- Máx 2 emojis.
- Se muestra en consola al publicar una story para agregarlo manualmente como sticker de texto.

**Ejemplo**: `Tu asado merece una Bestial. Pedila ahora 🔥`

**Evitar**:
- Frases solo de hype sin mencionar el producto ni invitar a pedirlo
- Lenguaje corporativo o genéricamente motivacional
- Más de 3 emojis
- Mencionar teléfonos, horarios o conservantes

---

## Contextos disponibles (14) — rotan automáticamente por menor uso

Cada contexto tiene 6 hashtags propios que Claude combina con los 4 de marca fija.
El `.md` de cada imagen guarda `**Contexto ID:**` para que analytics pueda agrupar por contexto.

| ID | Nombre | Hashtags contextuales |
|----|--------|-----------------------|
| `asado_familiar` | Asado familiar | #asado #parrillada #asadocolombiano #familytime #bbqtime #carnealaparrilla |
| `parrilla_premium` | Parrilla premium | #parrilla #steaklovers #asadorpremium #grillmaster #carnedeRes #parrillero |
| `mesa_madera_rustica` | Mesa de madera rústica | #mesarustica #comidareal #instafood #homecooked #foodstyling #comidalatina |
| `evento_deportivo` | Evento deportivo | #watchparty #futbol #gamefood #snacktime #friendsandfood #deportes |
| `cocina_moderna` | Cocina moderna | #cocinamoderna #pizzalovers #gourmet #foodphotography #cheflife #receta |
| `picnic_campo` | Picnic al aire libre | #picnic #airlibre #naturaleza #outdoorfood #campestre #finde |
| `terraza_noche` | Terraza nocturna | #terrazanocturna #viernes #nightout #sobremesa #tapas #ciudadnocturna |
| `playa_verano` | Playa y verano | #playa #verano #vacaciones #seafood #playacolombia #tropicalfood |
| `cumpleanos_fiesta` | Fiesta y celebración | #cumpleanos #fiesta #partyfood #celebracion #appetizers #birthdayparty |
| `desayuno_brunch` | Desayuno / Brunch | #brunch #desayuno #brunchtime #morningvibes #weekendbrunch #huevos |
| `street_food` | Street food / Mercado | #streetfood #mercado #comidacallejera #tacos #antojitos #foodmarket |
| `cocina_campo` | Cocina de campo / Rancho | #cocinacampo #rancho #fogon #comidarustica #cocinacriolla #campo |
| `post_entrenamiento` | Post entrenamiento / Healthy | #postworkout #saludable #healthyfood #mealprep #fitness #comidasana |
| `mesa_restaurante` | Mesa de restaurante | #restaurante #finedining #burgerlovers #cenaconestilo #gourmet #restaurantecol |

El historial y frecuencia de uso se guarda en `Imagenes Instgram/historial_generaciones.json`.
Las métricas de rendimiento por contexto se acumulan en `Imagenes Instgram/publicaciones_log.json`.

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

### Formato del archivo `.md` por imagen
Cada imagen generada tiene un `.md` con esta estructura:
```
# Imagen Instagram - DD/MM/YYYY

**Contexto:** Nombre del contexto
**Contexto ID:** id_del_contexto

## Caption

Texto completo para el feed (4-6 líneas)

## Caption Story

Texto corto para story (max 2 líneas + CTA)

## Hashtags

#tag1 #tag2 ... (9-11 hashtags: 6 contextuales + 4 de marca + 1 extra)
```

### Analytics — permisos requeridos
Las métricas de reach/impressions requieren que el token tenga el permiso `instagram_manage_insights`.
Si el token no tiene ese permiso, `actualizar_metricas` captura el error silenciosamente y solo guarda `likes` y `comments` (que sí están disponibles con permisos básicos).

### Carousel — lógica de alternancia
- Semanas impares (1, 3, 5…): post individual. `seleccionar_imagen("post")` elige la más reciente no publicada.
- Semanas pares (2, 4, 6…): carousel MESA+PERSONAS. `_buscar_par_del_dia()` busca el par más reciente donde ambas imágenes estén sin publicar.
- Si no hay par disponible en semana par, cae automáticamente a modo individual.
