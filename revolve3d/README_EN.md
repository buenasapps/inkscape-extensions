# 3D Revolve — Inkscape extension

Revolves a 2D path (the *profile*) around a vertical axis and draws the resulting solid as **pure vectors**: many paths with linear gradients that fake the lighting. Similar in spirit to Illustrator's "Revolve".

- **Version:** 1.0 · **Author:** tebicap · **License:** GPL-2.0-or-later (see `LICENSE`)
- **Requires:** Inkscape 1.2 or later (Python extension using `inkex`; developed with `inkex` 1.4.1)
- **Languages:** English, with a Spanish translation (follows Inkscape's interface language)

*Spanish version of this document: `README_ES.md` (keep both in sync).*

## Install

Copy these files together into Inkscape's user extensions folder (Edit → Preferences → System → "User extensions"), optionally inside a subfolder, and restart Inkscape:

```
revolve3d.inx
revolve3d.py
locale/es/LC_MESSAGES/revolve3d.mo     (Spanish translation; optional)
```

The effect appears in **Extensions → 3D effects → 3D Revolve…**

## Usage

1. Select a path (or a basic shape) and open **Extensions → 3D effects → 3D Revolve…**. Choose **Apply/update**. The result is a group containing the rendered solid and, hidden, your original path.
2. To change the look, select the group (or any object inside it), open the dialog again, change values and choose **Apply/update**. The previous render is replaced.
3. **Remove effect** gives you back the original path and stores the parameters on it. **Restore effect** applies them again later, ignoring whatever the dialog currently says.
4. **Transfer from first / last selected** copies the effect parameters of the first (or last) selected object onto all the other selected objects. It is silent: it does nothing if only one object is selected or if the source has no effect.
5. **Show values** prints the saved parameters of the selected objects (groups with the effect, or paths whose effect was removed) as one ordered message, in the interface language. It never changes the drawing.
6. The dialog has a **Live preview** checkbox (off by default).

Ungrouping the result breaks the link with the original profile (on purpose).

## Parameters

| Name (.inx = CLI argument = saved key) | Dialog text | Type / range | Default | What it does |
|---|---|---|---|---|
| `action` | Action | `apply` / `reapply` / `restore` / `transfer_first` / `transfer_last` | `apply` | Apply: creates or updates the effect with these values. Restore: re-applies it with the saved values (stored in the group, or in the path you removed the effect from). Remove: gives back the original path and saves the values on it. Transfer: copies the effect of the first/last selected object onto the other selected objects (does nothing if there is only one object or it has no effect). |
| `axis_side` | Axis at profile edge | `left` / `right` | `left` | Edge of the profile where the axis of revolution is placed. |
| `axis_offset` | Axis offset (px) | float -10000…10000 | `0` | Moves the axis away from the profile. Above 0 the solid is hollow inside. |
| `sweep` | Revolve angle (°) | float 1…360, slider | `360` | How far the profile turns. 360° gives the full solid; less gives a wedge. |
| `start_angle` | Start angle (°) | float -360…360 | `0` | Where the turn starts. Mostly visible on wedges (under 360°). |
| `cap` | Caps on open ends | bool | `true` | Closes the open ends of the profile with a flat cap. |
| `sides` | Surface | `auto` / `both` | `auto` | Solid: hides the back side (lighter). Both sides: also draws the inside of open surfaces. |
| `rot_x` | Rotation X (°) | float -180…180, slider | `20` | Tilts the object forward or backward, to see more of its top or bottom. |
| `rot_y` | Rotation Y (°) | float -180…180, slider | `0` | Turns the object around its vertical axis. Barely noticeable on a full revolution. |
| `rot_z` | Rotation Z (°) | float -180…180, slider | `0` | Tilts the object left or right, like a wheel. |
| `perspective` | Perspective (%) | float 0…100, slider | `0` | 0 = no perspective (technical drawing). Higher = camera closer: near parts look bigger. |
| `shading` | Shading | `smooth` / `none` | `smooth` | Smooth: gradients that give volume. No shading: each face a single color. |
| `light_az` | Light: azimuth (°) | float -180…180 | `-40` | Which side the light comes from: negative = left, positive = right. |
| `light_el` | Light: elevation (°) | float -90…90 | `40` | Height of the light: 90° from above, 0° from the side. |
| `ambient` | Ambient light (%) | float 0…100 | `35` | Base light that also reaches shaded areas. |
| `highlight` | Specular highlight (%) | float 0…100 | `25` | Intensity of the shiny reflection on the brightest area. |
| `fallback_fill` | Color | color (RGBA integer in the .inx) | `#4f9da6` | Color of the solid. Used if the path has no fill, or always if Force is checked. |
| `force_color` | Force | bool | `false` | Paints with this color even if the original path already has a fill. |
| `profile_detail` | Max bands per curve | int 2…64 | `24` | Cap on the bands used in each curve of the profile. |
| `band_step` | Angle between bands (°) | float 1…30 | `5` | How much the curve may turn between one band and the next. Fewer degrees = smoother shading, but more objects. |
| `angular_segments` | Segments per turn | int 8…120 | `28` | Divisions of a full turn. More segments = rounder outlines. |
| `grad_quality` | Gradient stops | `low` / `normal` / `high` | `normal` | How many color stops each gradient has. More stops = more faithful, but a heavier file. |
| `seam_fix` | Hide seams (stroke) | bool | `true` | Avoids thin lines between bands by adding a very thin stroke of the same gradient. |
| `seam_width` | — | float 0…5 | `0.2` | Stroke width, in px. With 0 no stroke is drawn (thin lines may show between bands). |

## For developers and AI agents

Everything below describes how the extension works so that someone (human or AI) can keep working on it.

### Files

| File | Role |
|---|---|
| `revolve3d.py` | All the logic (~1,150 lines, fully documented; the module docstring explains the design). |
| `revolve3d.inx` | Dialog descriptor: 4 tabs (Geometry, View, Shading, Quality), all parameters with tooltips, `needs-live-preview="true"`, `translationdomain="revolve3d"`. |
| `locale/es/LC_MESSAGES/revolve3d.mo` | Compiled Spanish catalog (gettext domain `revolve3d`). |
| `po/revolve3d.pot`, `po/es.po` | Translation template and Spanish catalog (msgid = English text, matched exactly, including trailing colons). |
| `LICENSE` | GPL version 2 text. |

### The "live" model (state lives in the SVG)

The extension returns a `<g>` that contains: the original profile hidden (`display:none`, attribute `data-revolve3d-role="profile"`), a local `<defs>` with the gradients (ids `<groupid>-g<n>`) and the faces (`<path>`), sorted back to front. The group has `data-revolve3d` = JSON `{"version":1,"params":{...}}`. Running the extension on the group (or any child) deletes everything except the profile and regenerates. `purge_orphan_gradients` removes root-level orphan gradients with that id prefix. After **Remove effect** the original path carries `data-revolve3d-saved` with the parameters.

### Actions (internal names do NOT match the UI labels)

| Internal value | UI label | What it does |
|---|---|---|
| `apply` | Apply/update | Create or regenerate with the dialog values. |
| `reapply` | Restore effect | Re-apply the SAVED parameters (from the group or from `data-revolve3d-saved`); saved values win, the dialog only fills missing keys. |
| `restore` | Remove effect | Give back the original path (visible) and save the parameters on it. |
| `show` | Show values | `Revolve3D.show_values`: read-only; prints one translated message with the stored parameters of each selected group or path with `data-revolve3d-saved` (via `inkex.errormsg`); changes nothing. Shows a short "no saved values" message if there is nothing to show. |
| `transfer_first` / `transfer_last` | Transfer from first / last selected | `Revolve3D.transfer`: copy the source's stored parameters to the other selected objects. Silent: no messages, no changes if fewer than 2 objects, source without effect, or a target that is not a valid profile (skipped). Relies on the order of `self.svg.selection`. |

When nothing changes, `inkex` emits no output, which Inkscape treats as "no change".

### Code flow

`Revolve3D.effect` → `apply()` / `restore()` / `transfer()`. `apply` validates the profile **before** touching the document, builds `RevolveEngine(params, path, color).build(prefix)` → faces `(z, d, style)` + gradients → writes them into the group.

`RevolveEngine`: `flatten_profile` (adaptive polyline of the profile) → `_build_profile` (one *band* per segment, `_orientation` fixes the normal side) → `_build_band` (splits the sweep into visible runs with `_runs`/`_facing`, and at the angle opposite to each cut with `_split_runs`) → `_emit_band_run` (outline via `_arc_points`, `spline_cmds` = Catmull-Rom→cubic Bézier) → `_band_gradient` / `_grad_frame` / `_split_monotonic` (linear gradient perpendicular to the projected axis; arcs are split where the gradient position stops being monotonic) → `shade` (ambient + Lambert + Blinn-Phong, exponent 24) → `simplify_stops` (`GRAD_QUALITY` tiers low (7, 6.0), normal (11, 1.6), high (17, 0.7)) → `_build_cap` / `_build_cuts` (flat faces) → `build` sorts by mean z and then calls `_place_plane` for caps and cut faces.

### Geometric conventions

- Profile `(r, h)`: r = distance to the axis, h = height (up). World: `(±r·cosθ, h, r·sinθ)`; the sign is the side of the axis.
- View matrix `M = Rz·Rx·Ry`, +z toward the viewer. Screen = `(axis_x + x, pivot_y − y)`; optional perspective factor `d/(d−z)` with `cam_dist = bound·M/(M−1)/perspective`, where `bound` = radius of the sphere that contains the object around its pivot and `M = PERSPECTIVE_MAX_MAGNIFICATION` (5): at 100 % the nearest point the object could possibly have is magnified M times and the camera never enters the object; strength grows linearly with the slider. The object stays anchored to its axis when the view rotates.
- "Solid" mode (`sides=auto`) culls back faces when a cap or a closed profile exists.
- Painter's algorithm by mean z, with one correction: flat faces (caps, cut faces) are placed with their **plane** (`_place_plane`): faces on the far side of the plane (from the viewer) are drawn before, faces on the viewer's side after, faces crossing the plane keep their z order. Each face stores its height range and angular range for this test.

### Design decisions (do not undo without a reason)

- Seam stroke uses the **same gradient** as the fill (a flat color leaves visible lines). Default width 0.2 px (document units). With `seam_width = 0` thin lines may show between bands.
- Bands are **not** enlarged/overlapped (tried; the joins looked bad). `seam_fix` only adds the stroke.
- Gradients are simplified; `simplify_stops` already removes any stop that interpolation reproduces, so constant-color gradients end up with 2 stops (an extra "same color" pass was tried and removed stops in none of the test cases).
- Gradients live in a local `<defs>` inside the group so duplicating/deleting the group leaves no dangling references.
- Caps and cut faces are flat colors.

### Product decisions made by the owner

- UI texts stay **short**; every tooltip is simple and ends with "Default: X." (except action and axis side).
- Border/stroke units are px.
- No separate menu entries and no enabling/disabling of controls depending on the action (INX cannot do conditional enabling anyway).
- The Transfer actions override every other dialog setting and must stay silent.
- Live preview is available and off by default.

### Known limits

- Painter's algorithm is an approximation: surfaces crossing each other may be ordered wrongly (flat faces are handled with their plane).
- Profiles that cross the axis are not supported.
- Very faint lines can appear where a ring's gradient is split (torus).
- The dialog cannot be preloaded with the values stored in a group (INX limitation).

### Testing without Inkscape

```bash
python3 revolve3d.py --id=<path_id> --action=apply [--rot_x=30 ...] input.svg > out.svg
python3 revolve3d.py --id=<group_id> --action=restore out.svg > restored.svg
python3 revolve3d.py --action=transfer_last --id=<a> --id=<b> input.svg > out.svg   # empty output = no change
rsvg-convert -b white -w 800 out.svg -o out.png
```

- Check structure with `inkex.load_svg(...)`, not with regular expressions on ids.
- `inkex` generates random ids: seed `random` in a small wrapper to diff two runs.
- Useful validation used during development: a small ray-caster that renders the ground-truth visibility of a sphere (ortho view) and compares which faces are visible against the engine's output for random views and sweeps.
- After any change: `python3 -m pyflakes revolve3d.py`, check the `.inx` is well-formed XML and that its parameter names equal the keys of `DEFAULTS`.

### Maintenance rules

- Parameter names are identical in three places: `<param name>` in the `.inx`, the CLI argument in `add_arguments` and the key in `DEFAULTS` / saved JSON. If you change a default, change it in `DEFAULTS`, in the `.inx` value **and** in the tooltip text (`Default: …`). The default color `#4f9da6` is the integer `1335731967` in the `.inx` (0x4f9da6ff).
- When you add or change a UI string (`.inx` or `_("…")` in the `.py`), update `po/revolve3d.pot` and `po/es.po` and rebuild the `.mo` (`msgfmt po/es.po -o locale/es/LC_MESSAGES/revolve3d.mo`).
- The extension name (`<name>`) is not translated by Inkscape.
- Keep `README_EN.md` and `README_ES.md` in sync.
