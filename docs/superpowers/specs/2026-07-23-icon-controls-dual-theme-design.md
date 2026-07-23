# Icon, Control Material, and Dual Theme Design

## Scope

This pass addresses the four annotated screenshots without changing serial,
controller, or hardware behavior:

- redraw the battery and temperature glyphs;
- make MOTOR buttons translucent and add a MODE text glow;
- remove toggle aliasing and reposition ALL OFF;
- add status dots to the serial controls;
- add a persistent dark/light appearance switch.

## Component design

### Sensor glyphs

The battery glyph becomes a clean rounded battery outline with a ratio-driven
energy fill. Temperature tiles use a compact circular sensor badge with a
single thermometer silhouette; the decorative steam strokes and bulky square
tile are removed. Both remain vector-painted and DPI-independent.

### MOTOR material

Inactive buttons use a shared translucent slate gradient, allowing the card
surface to remain visible beneath them. Selected buttons use a translucent
semantic gradient with a restrained glow. The MODE value receives a separate
soft glow so the state reads as an illuminated instrument display.

### Output controls

Toggle switches render to a supersampled off-screen image and downsample with
smooth transformation, eliminating jagged ellipse edges. ALL OFF moves to its
own centered footer row above the divider so the five controls form a clean
2+3 grid.

### Serial status

The status badge paints a semantic LED dot: gray/offline, amber/opening,
green/connected, red/error. The action button paints a small contrasting dot,
making CONNECT/DISCONNECT read as a paired instrument control.

### Appearance switch

A custom sun/moon pill sits in the tab bar’s top-right corner. It switches
between:

- **Night:** current slate/cyan console.
- **Day:** cool pearl-gray surfaces, navy text, teal accent, soft blue-gray
  borders, and restrained shadows.

The selected scheme is stored with `QSettings`. Theme switching updates global
QSS, custom painters, inline styles, terminal log colors, and plots without
rebuilding controller state.

## Verification

- Red/green widget tests cover appearance switching, persistence API, serial
  dots, ALL OFF geometry, translucent MOTOR material, and supersampled toggles.
- Deterministic screenshots cover both themes and all pages.
- Existing protocol and behavior tests remain green.
- The packaged EXE must start in fake mode with all fonts and QSS bundled.

