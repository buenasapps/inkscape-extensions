# 3D Revolve (Revolución 3D) — extensión de Inkscape

Hace girar un trazado 2D (el *perfil*) alrededor de un eje vertical y dibuja el sólido resultante en **vectores puros**: muchos trazados con degradados lineales que simulan la iluminación. Parecido en espíritu a «Revolución» de Illustrator.

- **Versión:** 1.0 · **Autor:** tebicap · **Licencia:** GPL-2.0-or-later (ver `LICENSE`)
- **Requiere:** Inkscape 1.2 o posterior (extensión Python con `inkex`; desarrollada con `inkex` 1.4.1)
- **Idiomas:** inglés, con traducción al español (sigue el idioma de la interfaz de Inkscape)

*Versión en inglés de este documento: `README_EN.md` (mantener ambas sincronizadas).*

## Instalación

Copia estos archivos juntos en la carpeta de extensiones de usuario de Inkscape (Editar → Preferencias → Sistema → «Extensiones de usuario»), opcionalmente dentro de una subcarpeta, y reinicia Inkscape:

```
revolve3d.inx
revolve3d.py
locale/es/LC_MESSAGES/revolve3d.mo     (traducción al español; opcional)
```

El efecto aparece en **Extensiones → 3D effects → 3D Revolve…** (el nombre del menú no se traduce).

## Uso

1. Selecciona un trazado (o una forma básica) y abre **Extensiones → 3D effects → 3D Revolve…**. Elige **Aplicar/actualizar**. El resultado es un grupo con el sólido dibujado y, oculto, tu trazado original.
2. Para cambiar el aspecto, selecciona el grupo (o cualquier objeto dentro), abre el diálogo otra vez, cambia valores y elige **Aplicar/actualizar**. El render anterior se reemplaza.
3. **Quitar efecto** te devuelve el trazado original y guarda en él los parámetros. **Restaurar efecto** los vuelve a aplicar más adelante, sin importar lo que diga el diálogo en ese momento.
4. **Transferir desde el primero / último seleccionado** copia los parámetros del efecto del primer (o último) objeto seleccionado a todos los demás seleccionados. Es silenciosa: no hace nada si hay un solo objeto seleccionado o si el origen no tiene efecto.
5. **Mostrar valores** imprime los parámetros guardados de los objetos seleccionados (grupos con el efecto, o trazados a los que se les quitó) como un único mensaje ordenado, en el idioma de la interfaz. Nunca cambia el dibujo.
6. El diálogo tiene la casilla **Live preview** (desactivada por defecto).

Desagrupar el resultado rompe el vínculo con el perfil original (a propósito).

## Parámetros

| Nombre (.inx = argumento CLI = clave guardada) | Texto del diálogo | Tipo / rango | Por defecto | Qué hace |
|---|---|---|---|---|
| `action` | Acción | `apply` / `reapply` / `restore` / `transfer_first` / `transfer_last` | `apply` | Aplicar: crea o actualiza el efecto con estos valores. Restaurar: lo vuelve a aplicar con los valores guardados (en el grupo, o en el trazado al que le quitaste el efecto). Quitar: devuelve el trazado original y guarda en él los valores. Transferir: copia el efecto del primer/último objeto seleccionado a los demás seleccionados (no hace nada si hay un solo objeto o no tiene efecto). |
| `axis_side` | Eje de giro en el borde | `left` / `right` | `left` | Borde del perfil donde se coloca el eje alrededor del cual gira. |
| `axis_offset` | Separación del eje (px) | float -10000…10000 | `0` | Aleja el eje del perfil. Con un valor mayor que 0 el sólido queda hueco por dentro. |
| `sweep` | Ángulo de revolución (°) | float 1…360, deslizador | `360` | Cuánto gira el perfil. 360° da el sólido completo; menos, una cuña. |
| `start_angle` | Ángulo inicial (°) | float -360…360 | `0` | Dónde empieza el giro. Se nota sobre todo en cuñas (menos de 360°). |
| `cap` | Tapas en los extremos abiertos | bool | `true` | Cierra con una tapa plana los extremos abiertos del perfil. |
| `sides` | Superficie | `auto` / `both` | `auto` | Sólido: oculta la parte trasera (más ligero). Ambos lados: dibuja también el interior de superficies abiertas. |
| `rot_x` | Rotación X (°) | float -180…180, deslizador | `20` | Inclina el objeto hacia adelante o hacia atrás, para ver más su parte de arriba o de abajo. |
| `rot_y` | Rotación Y (°) | float -180…180, deslizador | `0` | Gira el objeto sobre su eje vertical. En un giro completo apenas se nota. |
| `rot_z` | Rotación Z (°) | float -180…180, deslizador | `0` | Inclina el objeto hacia la izquierda o la derecha, como una rueda. |
| `perspective` | Perspectiva (%) | float 0…100, deslizador | `0` | 0 = sin perspectiva (dibujo técnico). Más alto = cámara más cerca: lo cercano se ve más grande. |
| `shading` | Sombreado | `smooth` / `none` | `smooth` | Suave: degradados que dan volumen. Sin sombreado: cada cara de un solo color. |
| `light_az` | Luz: azimut (°) | float -180…180 | `-40` | De qué lado llega la luz: negativo = izquierda, positivo = derecha. |
| `light_el` | Luz: elevación (°) | float -90…90 | `40` | Altura de la luz: 90° desde arriba, 0° de costado. |
| `ambient` | Luz ambiente (%) | float 0…100 | `35` | Luz base que también alcanza las zonas en sombra. |
| `highlight` | Brillo especular (%) | float 0…100 | `25` | Intensidad del reflejo brillante en la zona más iluminada. |
| `fallback_fill` | Color | color (entero RGBA en el .inx) | `#4f9da6` | Color del sólido. Se usa si el trazo no tiene relleno, o siempre si marcas Forzar. |
| `force_color` | Forzar | bool | `false` | Pinta con este color aunque el trazo original ya tenga relleno. |
| `profile_detail` | Máx. bandas por curva | int 2…64 | `24` | Tope de bandas que se usan en cada curva del perfil. |
| `band_step` | Ángulo entre bandas (°) | float 1…30 | `5` | Cuánto puede girar la curva entre una banda y la siguiente. Menos grados = sombreado más suave, pero más objetos. |
| `angular_segments` | Segmentos por vuelta | int 8…120 | `28` | Divisiones de una vuelta completa. Más segmentos = contornos más redondos. |
| `grad_quality` | Paradas de degradado | `low` / `normal` / `high` | `normal` | Cuántas paradas de color lleva cada degradado. Más paradas = más fiel, pero archivo más pesado. |
| `seam_fix` | Disimular costuras (trazo) | bool | `true` | Evita las líneas finas entre bandas añadiendo un trazo muy fino del mismo degradado. |
| `seam_width` | Project-Id-Version: revolve3d
Language: es
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
 | float 0…5 | `0.2` | Grosor del trazo, en px. Con 0 no se dibuja trazo (pueden verse líneas finas entre bandas). |

## Para desarrolladores y agentes de IA

Lo que sigue describe cómo funciona la extensión para que alguien (persona o IA) pueda seguir trabajando en ella.

### Archivos

| Archivo | Función |
|---|---|
| `revolve3d.py` | Toda la lógica (~1150 líneas, documentada; el docstring del módulo explica el diseño). |
| `revolve3d.inx` | Descriptor del diálogo: 4 pestañas (Geometría, Vista, Sombreado, Calidad), todos los parámetros con tooltips, `needs-live-preview="true"`, `translationdomain="revolve3d"`. |
| `locale/es/LC_MESSAGES/revolve3d.mo` | Catálogo español compilado (dominio gettext `revolve3d`). |
| `po/revolve3d.pot`, `po/es.po` | Plantilla de traducción y catálogo español (msgid = texto en inglés, se compara exacto, incluidos los dos puntos finales). |
| `LICENSE` | Texto de la GPL versión 2. |

### El modelo «vivo» (el estado vive en el SVG)

La extensión devuelve un `<g>` que contiene: el perfil original oculto (`display:none`, atributo `data-revolve3d-role="profile"`), un `<defs>` local con los degradados (ids `<idgrupo>-g<n>`) y las caras (`<path>`), ordenadas de atrás hacia adelante. El grupo lleva `data-revolve3d` = JSON `{"version":1,"params":{...}}`. Al ejecutar la extensión sobre el grupo (o cualquier hijo) se borra todo salvo el perfil y se regenera. `purge_orphan_gradients` elimina degradados huérfanos de la raíz con ese prefijo de id. Tras **Quitar efecto**, el trazado original lleva `data-revolve3d-saved` con los parámetros.

### Acciones (los nombres internos NO coinciden con los textos de la interfaz)

| Valor interno | Texto en el diálogo | Qué hace |
|---|---|---|
| `apply` | Aplicar/actualizar | Crea o regenera con los valores del diálogo. |
| `reapply` | Restaurar efecto | Reaplica los parámetros GUARDADOS (del grupo o de `data-revolve3d-saved`); mandan los guardados, el diálogo solo rellena claves ausentes. |
| `restore` | Quitar efecto | Devuelve el trazado original (visible) y guarda en él los parámetros. |
| `show` | Mostrar valores | `Revolve3D.show_values`: solo lectura; imprime un mensaje traducido con los parámetros guardados de cada grupo seleccionado o trazado con `data-revolve3d-saved` (vía `inkex.errormsg`); no cambia nada. Si no hay nada que mostrar, muestra un mensaje breve de «no se encontraron valores». |
| `transfer_first` / `transfer_last` | Transferir desde el primero / último seleccionado | `Revolve3D.transfer`: copia los parámetros guardados del origen a los demás seleccionados. Silenciosa: sin mensajes y sin cambios si hay menos de 2 objetos, el origen no tiene efecto, o un destino no es un perfil válido (se salta). Depende del orden de `self.svg.selection`. |

Cuando no hay cambios, `inkex` no emite salida y Inkscape lo interpreta como «sin cambios».

### Flujo del código

`Revolve3D.effect` → `apply()` / `restore()` / `transfer()`. `apply` valida el perfil **antes** de tocar el documento, construye `RevolveEngine(params, path, color).build(prefix)` → caras `(z, d, style)` + degradados → las escribe dentro del grupo.

`RevolveEngine`: `flatten_profile` (polilínea adaptativa del perfil) → `_build_profile` (una *banda* por segmento; `_orientation` fija el lado de la normal) → `_build_band` (parte el barrido en arcos visibles con `_runs`/`_facing`, y en el ángulo opuesto a cada corte con `_split_runs`) → `_emit_band_run` (contorno con `_arc_points`; `spline_cmds` = Catmull-Rom→Bézier cúbica) → `_band_gradient` / `_grad_frame` / `_split_monotonic` (degradado lineal perpendicular al eje proyectado; se parten los arcos donde la posición del degradado deja de ser monótona) → `shade` (ambiente + Lambert + Blinn-Phong, exponente 24) → `simplify_stops` (niveles `GRAD_QUALITY`: low (7, 6.0), normal (11, 1.6), high (17, 0.7)) → `_build_cap` / `_build_cuts` (caras planas) → `build` ordena por z medio y luego llama a `_place_plane` para tapas y caras de corte.

### Convenciones geométricas

- Perfil `(r, h)`: r = distancia al eje, h = altura (hacia arriba). Mundo: `(±r·cosθ, h, r·sinθ)`; el signo es el lado del eje.
- Matriz de vista `M = Rz·Rx·Ry`, +z hacia el espectador. Pantalla = `(axis_x + x, pivot_y − y)`; factor de perspectiva opcional `d/(d−z)` con `cam_dist = bound·M/(M−1)/perspective`, donde `bound` = radio de la esfera que contiene al objeto alrededor de su pivote y `M = PERSPECTIVE_MAX_MAGNIFICATION` (5): al 100 % el punto más cercano posible del objeto se amplía M veces y la cámara nunca entra en el objeto; la intensidad crece linealmente con el control. El objeto permanece anclado a su eje al rotar la vista.
- El modo «Sólido» (`sides=auto`) descarta las caras traseras cuando hay tapa o perfil cerrado.
- Algoritmo del pintor por z medio, con una corrección: las caras planas (tapas y caras de corte) se colocan con su **plano** (`_place_plane`): lo que queda al otro lado del plano respecto al observador se dibuja antes, lo que queda de su lado después, y lo que cruza el plano conserva el orden por z. Cada cara guarda su rango de alturas y de ángulos para esta prueba.

### Decisiones de diseño (no deshacer sin motivo)

- El trazo de costura usa el **mismo degradado** que el relleno (un color plano deja líneas visibles). Grosor por defecto 0,2 px (unidades del documento). Con `seam_width = 0` pueden verse líneas finas entre bandas.
- Las bandas **no** se agrandan ni se solapan (se probó; las uniones se veían mal). `seam_fix` solo añade el trazo.
- Los degradados se simplifican; `simplify_stops` ya quita cualquier parada que la interpolación reproduzca, así que los degradados de un solo color quedan con 2 paradas (se probó un paso extra de «mismo color» y no quitó paradas en ningún caso de prueba).
- Los degradados viven en un `<defs>` local dentro del grupo, así duplicar o borrar el grupo no deja referencias colgando.
- Las tapas y las caras de corte son de color plano.

### Decisiones de producto tomadas por el propietario

- Los textos de la interfaz se mantienen **cortos**; cada tooltip es sencillo y termina con «Por defecto: X.» (salvo acción y lado del eje).
- Las unidades del borde/trazo son px.
- Sin entradas de menú separadas y sin habilitar/deshabilitar controles según la acción (INX no permite habilitación condicional).
- Las acciones de transferir anulan todo lo demás del diálogo y deben seguir siendo silenciosas.
- La vista previa en vivo está disponible y desactivada por defecto.

### Límites conocidos

- El algoritmo del pintor es una aproximación: superficies que se cruzan pueden ordenarse mal (las caras planas se resuelven con su plano).
- No se admiten perfiles que crucen el eje.
- Pueden aparecer líneas muy tenues donde se parte el degradado de un anillo (toro).
- El diálogo no puede precargarse con los valores guardados en un grupo (limitación de INX).

### Pruebas sin Inkscape

```bash
python3 revolve3d.py --id=<id_trazado> --action=apply [--rot_x=30 ...] entrada.svg > salida.svg
python3 revolve3d.py --id=<id_grupo> --action=restore salida.svg > restaurado.svg
python3 revolve3d.py --action=transfer_last --id=<a> --id=<b> entrada.svg > salida.svg   # salida vacía = sin cambios
rsvg-convert -b white -w 800 salida.svg -o salida.png
```

- Comprueba la estructura con `inkex.load_svg(...)`, no con expresiones regulares sobre ids.
- `inkex` genera ids aleatorios: siembra `random` en un pequeño envoltorio para comparar dos ejecuciones.
- Validación útil durante el desarrollo: un pequeño trazador de rayos que calcula la visibilidad real de una esfera (vista ortogonal) y compara qué caras son visibles con la salida del motor para vistas y barridos aleatorios.
- Tras cualquier cambio: `python3 -m pyflakes revolve3d.py`, comprobar que el `.inx` es XML bien formado y que sus nombres de parámetro coinciden con las claves de `DEFAULTS`.

### Reglas de mantenimiento

- Los nombres de parámetro son idénticos en tres sitios: `<param name>` del `.inx`, el argumento CLI de `add_arguments` y la clave en `DEFAULTS` / JSON guardado. Si cambias un valor por defecto, cámbialo en `DEFAULTS`, en el valor del `.inx` **y** en el texto del tooltip (`Default: …`). El color por defecto `#4f9da6` es el entero `1335731967` en el `.inx` (0x4f9da6ff).
- Al añadir o cambiar un texto de la interfaz (`.inx` o `_("…")` en el `.py`), actualiza `po/revolve3d.pot` y `po/es.po` y recompila el `.mo` (`msgfmt po/es.po -o locale/es/LC_MESSAGES/revolve3d.mo`).
- Inkscape no traduce el nombre de la extensión (`<name>`).
- Mantén `README_EN.md` y `README_ES.md` sincronizados.
