# repository.anrielK

Kodi repozitář pro doplněk Stream Cinema Community (fork). Obsah (`addons.xml`, `zips/`) se
generuje automaticky – needitovat ručně.

**Instalace:** stáhni `repository.anrielK-<verze>.zip` a v Kodi zvol Doplňky → Instalovat ze souboru ZIP.
Adresa repozitáře: https://anrielk.github.io/repository.anrielK/

## Jak to funguje
- Zdroj doplňku: [AnrielK/plugin.video.stream-cinema-2](https://github.com/AnrielK/plugin.video.stream-cinema-2) (větev `main`).
- Workflow `.github/workflows/publish.yml` každých 30 min (nebo ručně přes Actions → Run workflow)
  stáhne zdroj a sestaví nový ZIP. **Nová verze se publikuje po zvýšení `version` v `addon.xml` zdroje.**
- Závislosti dodávané z repozitáře (např. `script.module.yt-dlp`) jsou hotové ZIPy v `extras/`.
- Lokálně: `python tools/kodi_repo.py build --src ../plugin.video.stream-cinema-2 --out .`
