# Bypass Layout Fidelity Design

## Goal

Make the motor and output cards match the approved second rendering rather than
only reproducing its controls. The firmware protocol, command flow, confirmed
state handling, and interlocks remain unchanged.

## Motor card

- Keep the MODE badge, current/bypass surface, divider, and six mode buttons.
- Use one 10 px spacing token between MODE and the current/bypass surface and
  the same token between that surface and the divider.
- Remove the shared fixed-height centering stretches that currently create a
  larger second blank band.
- Keep the current value on the left and the complete MOTOR BYPASS switch and
  label on the right. Both halves retain stable minimum widths.

## Output card

- Replace the two ordinary horizontal rows with one hierarchy surface.
- Row 1 contains CHARGE and CHARGE BYPASS at the left and right endpoints,
  joined by a dependency line. Labels use spaces, not protocol underscores.
- Row 2 contains DRIVE centered above its children.
- Row 3 contains NMOS1, NMOS2, and LIGHTS under a visible branch connector.
  CHARGE BYPASS and LIGHTS share the same horizontal center.
- ALL OFF remains centered below the hierarchy.
- Every toggle cell reserves enough width and height for the complete switch,
  focus ring, and label at supported window sizes and DPI scaling.
- Disabled and enabled styling continues to reflect confirmed firmware state.

## Rendering and tests

- Draw connector lines in a dedicated native PySide widget behind the controls;
  no bitmap rendering is shipped.
- Add geometry tests for equal motor spacing, complete toggle containment,
  hierarchy alignment, and parent-child vertical order.
- Refresh dark/light fixed-window and fullscreen visual baselines only after
  inspecting the newly rendered images against the approved reference.
- Run focused widget tests, all visual regressions, the complete test suite, and
  a clean packaged `--fake` smoke test before integration.

