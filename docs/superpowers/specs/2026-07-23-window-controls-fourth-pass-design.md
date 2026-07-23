# Window and controls fourth-pass design

## Goal

Apply the five annotated visual corrections without changing device-control
semantics or telemetry mappings.

## Window surface

- Keep the default size at 1600×900.
- Remove the fixed-size constraint so the native minimize, maximize, restore,
  and resize controls work normally.
- Keep a 1280×720 minimum to protect the dashboard layout.
- Let the root UI fill the entire client area. Remove the aspect-fit inner
  canvas, 100px outer gutters, cyan root border, and rounded root corners.
- Retain F11, Escape, and tab-header double-click fullscreen behavior.

## Battery and temperature layout

- Move the small battery glyph upward into the visual center of the free space
  above the voltage line.
- Keep the battery-temperature tile labeled `BATTERY`.
- Map the remaining three telemetry fields exactly:
  - `ntc1_c` → `NTC1`
  - `ntc2_c` → `NTC2`
  - `ntc3_c` → `NTC3`
- Use a tighter icon/text composition: centered icon column, aligned value and
  title baselines, and more balanced internal padding.

## Motor controls

- Preserve the six existing commands and mutual selection behavior.
- Present three visually explicit pairs:
  - SLEEP / WAKE: translucent slate group
  - FWD / REV: translucent cyan group
  - BRAKE / STOP: translucent warm safety group
- Use smaller spacing inside a pair and larger spacing between pairs.
- Every inactive button retains a visible tinted fill and matching border;
  active buttons become brighter and keep the existing glow.
- Supersample the custom button painter to avoid hard raster edges.

## Output switches

- Preserve the five output names, states, animation, keyboard interaction, and
  safety behavior.
- Render at 4× resolution and smooth-downsample.
- Inset the track so antialiased pixels are not clipped.
- Use a translucent gradient track, soft outer halo, subtle inner highlight,
  and a bordered/highlighted knob.
- Reduce the physical footprint slightly so the right card feels less blunt.

## Verification

- Regression tests prove window resizability, client-area fill, fullscreen
  restore, exact NTC labels/mappings, three motor groups, supersampling, and
  battery-glyph placement.
- Generate connected and disconnected screenshots in dark and light themes.
- Inspect the annotated regions visually.
- Run the full test suite, rebuild the PyInstaller executable, and smoke-launch
  the packaged app.
