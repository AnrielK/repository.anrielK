#!/usr/bin/env python3
"""Sestaví Kodi repozitář (zips/ + addons.xml + addons.xml.md5) z doplňku ve zdrojovém repu.

  python tools/kodi_repo.py build --src CESTA_KE_ZDROJI --out DIR [--force]
      přidá ZIP aktuální verze doplňku (+ ZIPy z extras/ a repozitářový doplněk)
      do DIR a přegeneruje addons.xml + md5. Hotovou verzi nepřepisuje (kromě --force),
      takže opakované spuštění nic nemění.

  python tools/kodi_repo.py repo-addon [--base URL] [--out FILE]
      vyrobí jen instalační ZIP repozitářového doplňku

Jen standardní knihovna.
"""
import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent.parent  # repo s tools/ a extras/
EXCLUDE_DIRS = {".git", ".github", "tools", "extras", "__pycache__", ".idea", ".vscode"}
EXCLUDE_FILES = {"dev-requirements.txt", ".gitignore", ".gitattributes", "Readme.md", "README.md"}
EXCLUDE_RE = re.compile(r"^addon\d+\.xml$|\.pyc$")
FIXED_DATE = (2020, 1, 1, 0, 0, 0)  # deterministické ZIPy

REPO_ID = "repository.anrielK"
REPO_VERSION = "1.0.0"
# GitHub Pages repa AnrielK/repository.anrielK
DEFAULT_BASE = "https://anrielk.github.io/repository.anrielK"


def read_meta(xml_text):
    head = re.search(r"<addon\b[^>]*>", xml_text).group(0)
    return (re.search(r'\bid="([^"]+)"', head).group(1),
            re.search(r'\bversion="([^"]+)"', head).group(1))


def vkey(v):
    return [int(p) if p.isdigit() else p for p in re.split(r"[.\-]", v)]


def strip_decl(xml_text):
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml_text).strip()


def read_meta_from_zip(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("/addon.xml") and n.count("/") == 1)
        return read_meta(z.read(name).decode("utf-8"))


def zwrite(z, arcname, data):
    zi = zipfile.ZipInfo(arcname, FIXED_DATE)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    z.writestr(zi, data)


def build_zip(src, out, force):
    xml = (src / "addon.xml").read_text(encoding="utf-8")
    addon_id, version = read_meta(xml)
    dest = out / "zips" / addon_id
    dest.mkdir(parents=True, exist_ok=True)
    zpath = dest / f"{addon_id}-{version}.zip"
    if zpath.exists() and not force:
        print(f"SKIP: {zpath.relative_to(out)} už existuje (zvyš version v addon.xml)")
        return zpath
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src)
            if p.is_dir() or EXCLUDE_DIRS & set(rel.parts):
                continue
            if rel.name in EXCLUDE_FILES or EXCLUDE_RE.search(rel.name):
                continue
            zwrite(z, f"{addon_id}/{rel.as_posix()}", p.read_bytes())
    # ikona/fanart vedle ZIPu (Kodi je zobrazí v seznamu repozitáře)
    for asset in ("icon", "fanart"):
        m = re.search(rf"<{asset}>([^<]+)</{asset}>", xml)
        if m and (src / m.group(1)).exists():
            (dest / f"{asset}{Path(m.group(1)).suffix}").write_bytes((src / m.group(1)).read_bytes())
    return zpath


def add_extras(out):
    """Přidá hotové ZIPy doplňků z extras/ (např. závislosti). Složku v ZIPu přejmenuje na id doplňku."""
    for src in sorted((TOOL_ROOT / "extras").glob("*.zip")):
        with zipfile.ZipFile(src) as zin:
            names = [n for n in zin.namelist() if not n.endswith("/")]
            top = names[0].split("/")[0]
            addon_id, version = read_meta(zin.read(f"{top}/addon.xml").decode("utf-8"))
            dest = out / "zips" / addon_id
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / f"{addon_id}-{version}.zip"
            if target.exists():
                continue
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
                for n in names:
                    zwrite(zout, f"{addon_id}/{n.split('/', 1)[1]}", zin.read(n))
        print(f"OK: {target.relative_to(out)} (extras)")


def repo_addon_xml(base, version=REPO_VERSION):
    base = base.rstrip("/")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{REPO_ID}" name="AnrielK repozitář" version="{version}" provider-name="AnrielK">
    <extension point="xbmc.addon.repository" name="AnrielK repozitář">
        <dir>
            <info compressed="false">{base}/addons.xml</info>
            <checksum>{base}/addons.xml.md5</checksum>
            <datadir zip="true">{base}/zips/</datadir>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary>AnrielK repozitář (Stream Cinema Community)</summary>
        <platform>all</platform>
    </extension>
</addon>
'''


def write_repo_addon_zip(path, base):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        zwrite(z, f"{REPO_ID}/addon.xml", repo_addon_xml(base))


def add_repo_addon(out, base):
    """Repozitářový doplněk jde i do repozitáře (samoaktualizace) a jako ZIP do kořene ke stažení."""
    name = f"{REPO_ID}-{REPO_VERSION}.zip"
    write_repo_addon_zip(out / "zips" / REPO_ID / name, base)
    for old in out.glob("repository.*.zip"):
        if old.name != name:
            old.unlink()
    write_repo_addon_zip(out / name, base)


def generate_index(out):
    parts = []
    for d in sorted((out / "zips").iterdir()):
        zips = list(d.glob("*.zip"))
        if not zips:
            continue
        latest = max(zips, key=lambda p: vkey(read_meta_from_zip(p)[1]))
        with zipfile.ZipFile(latest) as z:
            xml = z.read(f"{d.name}/addon.xml").decode("utf-8")
        parts.append(strip_decl(xml))
    body = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' \
           + "\n".join(parts) + "\n</addons>\n"
    (out / "addons.xml").write_text(body, encoding="utf-8")
    (out / "addons.xml.md5").write_text(
        hashlib.md5(body.encode("utf-8")).hexdigest(), encoding="utf-8")


def cmd_build(a):
    src = Path(a.src).resolve()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    z = build_zip(src, out, a.force)
    add_extras(out)
    add_repo_addon(out, a.base)
    generate_index(out)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"OK: addons.xml, addons.xml.md5 ({z.name})")


def cmd_repo_addon(a):
    out = Path(a.out)
    write_repo_addon_zip(out, a.base)
    print(f"OK: {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", default=str(TOOL_ROOT), help="cesta ke zdrojovému repu doplňku")
    b.add_argument("--out", required=True)
    b.add_argument("--base", default=DEFAULT_BASE)
    b.add_argument("--force", action="store_true", help="přepsat ZIP i při stejné verzi")
    b.set_defaults(fn=cmd_build)
    r = sub.add_parser("repo-addon")
    r.add_argument("--base", default=DEFAULT_BASE)
    r.add_argument("--out", default=f"{REPO_ID}-{REPO_VERSION}.zip")
    r.set_defaults(fn=cmd_repo_addon)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
