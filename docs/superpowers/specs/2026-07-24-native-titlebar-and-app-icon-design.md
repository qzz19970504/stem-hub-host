# Native title bar and application icon design

## Goal

Make the Windows title bar feel like a continuous part of the application in
both color schemes, replace the default Qt executable icon, and use the exact
window title `stem hub host`.

## Visual design

- The native caption background uses the same `BG_BASE` token as the adjacent
  application tab header.
- Caption text uses `FG_PRIMARY`, and the native dark-mode flag follows the
  active application scheme.
- The caption border is painted with the caption background color so there is
  no light seam between native and Qt surfaces.
- The application icon is a wordless hardware-hub mark: one central device and
  three connected nodes. Mint cyan on a deep navy rounded tile keeps the mark
  recognizable against both light and dark Windows surfaces.
- The icon source is retained as a PNG and exported to a multi-resolution ICO
  containing 16, 20, 24, 32, 40, 48, 64, 128, and 256 pixel images.

## Integration

- `QApplication` and `MainWindow` receive the bundled icon at runtime.
- PyInstaller embeds the ICO into the executable and bundles the PNG/ICO
  resources for one-file runtime use.
- Windows DWM attributes are applied after the native handle exists and are
  reapplied whenever the color scheme changes.
- Non-Windows and non-native Qt platforms safely skip the DWM operation.

## Acceptance criteria

1. `MainWindow.windowTitle()` is exactly `stem hub host`.
2. The application and main-window icons are non-null in source and packaged
   execution.
3. Dark title bar colors equal the dark `BG_BASE`/`FG_PRIMARY` tokens.
4. Light title bar colors equal the light `BG_BASE`/`FG_PRIMARY` tokens.
5. Switching themes reapplies the native title bar.
6. The PyInstaller spec embeds the ICO instead of using the Qt default icon.
7. Existing behavior and visual regression tests remain green.
