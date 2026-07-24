# Native title bar and application icon implementation plan

1. Add failing tests for the exact title, bundled runtime icon, theme-derived
   caption colors, and title-bar refresh on theme changes.
2. Generate the hub icon source, remove the chroma-key background, compose the
   dual-theme-safe tile, and export PNG plus multi-resolution ICO assets.
3. Add a small Windows DWM adapter with pure color conversion helpers and safe
   platform guards.
4. Set the application/window icon and exact title, then reapply native chrome
   after startup and every theme transition.
5. Update the PyInstaller data and executable-icon declarations.
6. Run targeted tests, the full suite, visual regression, rebuild the one-file
   executable, smoke-test it, and inspect light/dark native-window captures.
