# Visual Unification Design

## Intent

Preserve every controller, serial, plotting, and passthrough behavior while
bringing all three pages closer to `docs/design_dark.png`. The reference image
is authoritative for hierarchy, surface brightness, button material, border
weight, and terminal composition.

## Visual direction

- Lift the working surfaces from near-black to layered slate-blue surfaces.
- Keep cyan as the only dominant accent; reserve amber and red for semantic
  motor/fault states.
- Use subtle outlines and restrained glow. Large black inset rectangles and
  saturated inactive controls are removed.
- Keep the existing 1600×900 geometry and 2×3 console layout unchanged.

## Console page

- The MOTOR mode display becomes a softly tinted cyan/slate panel with the
  label and value treated as one visual unit.
- Inactive motor buttons share one muted slate fill and quiet border. Their
  icons retain semantic color at reduced intensity. The selected mode remains
  a bright filled control with a small glow.
- The AT terminal has exactly two visible boundaries: the outer terminal card
  and the command-entry bar. The log area blends into the outer card.

## Charts page

- The sample-rate control and clear action sit in a compact toolbar surface.
- Channel selectors render as consistent toggle chips, not default Qt
  checkboxes.
- Plot background, grid, labels, and surrounding card use the same slate-blue
  hierarchy as the console page.

## Passthrough page

- Bridge selection becomes a segmented row of four mode chips.
- TX and RX become matching sub-panels with consistent headers, editors,
  counters, and action buttons.
- Primary, secondary, checked, hover, focus, pressed, and disabled states use
  the global button language.

## Verification

- Widget tests verify terminal boundary structure, semantic object names, and
  cross-page control roles before implementation.
- Deterministic screenshots cover console, charts, passthrough, disconnected,
  and fullscreen states.
- The RGB comparison against `design_dark.png` must not regress.
- The complete test suite and packaged EXE smoke test must pass.

