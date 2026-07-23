# Bundled fonts

The application registers these fonts with `QFontDatabase` before constructing
the main window so screenshots and packaged builds do not depend on fonts
installed on the target machine.

- `Rajdhani-SemiBold.ttf`: Rajdhani, Google Fonts, SIL Open Font License 1.1.
  Source: https://github.com/google/fonts/tree/main/ofl/rajdhani
- `JetBrainsMono-Regular.ttf` and `JetBrainsMono-Bold.ttf`: JetBrains Mono,
  SIL Open Font License 1.1.
  Source: https://github.com/JetBrains/JetBrainsMono
- `NotoSansSC-Regular.ttf`: Noto Sans SC, SIL Open Font License 1.1. The local
  Windows Noto variable font is bundled under the stable application filename.
  Source: https://fonts.google.com/noto/specimen/Noto+Sans+SC

See `OFL.txt` for the common license text.
