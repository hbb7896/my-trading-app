# Trading Master icon

Approved concept: option 2, mint TM monogram on deep navy (2026-11-17).

- `tm-selected-concept.png`: original selected concept.
- `tm-icon-master.png`: full-bleed production artwork made with the built-in ImageGen tool.
- `../tool/package_tm_icon.ps1`: deterministic resizing into web, Apple touch, Flutter asset and Android launcher PNG sizes. Run with PowerShell from any directory.
- Android adaptive and Android 12 splash foreground: `../android/app/src/main/res/drawable/tm_mark.xml`, matching the selected monogram silhouette.

Production edit brief: preserve the exact selected TM geometry and mint gradient, remove the outer rounded tile boundary and black margin, and extend the deep navy background to all four edges. No new symbols, lettering or decoration. Keep the mark centered with safe padding for platform masks.

Web uses versioned PNG URLs in the manifest and a loading screen removed after Flutter's first frame. Existing installed shortcuts may retain their old icon until refreshed or re-added. Native Android installs require an updated APK; deploying the website alone cannot replace an installed APK's launcher icon.

The shared workspace keeps its existing Trend Lab name and package ID. The standalone Trading Master build keeps its existing name and package ID. No account or trading data is changed by this branding update.
