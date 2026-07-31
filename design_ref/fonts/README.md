# Fonts

No custom font files were supplied with the brief. The LawGIQ system uses three families, all loaded from **Google Fonts** via the `@import` at the top of `colors_and_type.css`:

| Family | Role | URL |
|---|---|---|
| Instrument Serif | Display, marketing hero copy, editorial moments | https://fonts.google.com/specimen/Instrument+Serif |
| Geist | UI, body, dense product surfaces | https://fonts.google.com/specimen/Geist |
| JetBrains Mono | Citations, case numbers, mono | https://fonts.google.com/specimen/JetBrains+Mono |

**If LawGIQ has licensed custom fonts**, drop the `.woff2` files into this folder and replace the Google Fonts `@import` with a local `@font-face` block. The CSS variables (`--font-display`, `--font-sans`, `--font-mono`) are already abstract — only the import needs to change.
