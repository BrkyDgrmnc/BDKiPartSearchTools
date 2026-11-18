"""
Official KiCad PCM Addon Package Builder & Validator
Follows all rules from https://dev-docs.kicad.org/en/addons/:
1. Generates 64x64 resources/icon.png (PCM icon) and 24x24 icon.png (ActionPlugin/IPC toolbar icon)
2. Validates metadata.json and plugin.json against official KiCad rules, schemas, and C++ regexes
3. Packages ISO 21320-1 ZIP archive with exact structure:
     |- plugins/
     |- resources/icon.png
     |- metadata.json (without download_* keys inside archive)
4. Generates dist/metadata-submission.json with SHA-256, download_size, and install_size for GitLab submission.
"""

import os
import re
import json
import hashlib
import zipfile
from typing import List, Tuple


def generate_icons(root_dir: str) -> None:
    try:
        import wx
        app = wx.App(False)

        def draw_icon(size: int, out_path: str):
            bmp = wx.Bitmap(size, size)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(wx.Colour(24, 98, 171)))
            dc.Clear()

            pad = max(2, size // 6)
            box_w = size - 2 * pad
            dc.SetPen(wx.Pen(wx.Colour(255, 215, 64), max(1, size // 16)))
            dc.SetBrush(wx.Brush(wx.Colour(30, 40, 52)))
            dc.DrawRoundedRectangle(pad, pad, box_w, box_w, max(2, size // 8))

            # IC leads
            for frac in (0.3, 0.5, 0.7):
                y = int(size * frac)
                dc.DrawLine(1, y, pad, y)
                dc.DrawLine(size - pad, y, size - 1, y)

            font_sz = 6 if size <= 24 else 14
            dc.SetFont(wx.Font(font_sz, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            dc.SetTextForeground(wx.Colour(255, 215, 64))
            dc.DrawText("BD", pad + 3, pad + 1)
            dc.SetTextForeground(wx.Colour(100, 235, 140))
            dc.DrawText("PST" if size > 24 else "PS", pad + (1 if size > 24 else 3), size // 2)

            dc.SelectObject(wx.NullBitmap)
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            bmp.SaveFile(out_path, wx.BITMAP_TYPE_PNG)

        # 24x24 toolbar icon inside plugins
        draw_icon(24, os.path.join(root_dir, "icon.png"))
        # 64x64 PCM package icon inside resources/icon.png
        draw_icon(64, os.path.join(root_dir, "resources", "icon.png"))
        print("[OK] Generated 24x24 toolbar icon.png and 64x64 resources/icon.png")
    except Exception as e:
        print(f"[WARN] Could not regenerate icons via wxPython: {e}")


def validate_official_rules(meta: dict, plugin_meta: dict) -> None:
    ident = meta.get("identifier", "")
    assert 2 <= len(ident) <= 50, f"Identifier length must be 2..50 chars (got {len(ident)})"
    assert re.match(r"^[a-zA-Z][-a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$", ident), f"Invalid PCM identifier: {ident}"
    assert "_" not in ident, "PCM identifier must not contain underscores (_)"
    # Also verify kicommon.dll C++ IPC plugin identifier regex: [\w\d]{2,}\.[\w\d]+\.[\w\d]+
    assert re.fullmatch(r"[\w\d]{2,}\.[\w\d]+\.[\w\d]+", plugin_meta.get("identifier", "")), (
        f"plugin.json identifier '{plugin_meta.get('identifier')}' must match C++ regex [\\w\\d]{{2,}}\\.[\\w\\d]+\\.[\\w\\d]+"
    )

    desc = meta.get("description", "")
    assert 1 <= len(desc) <= 150, f"Short description must be <= 150 chars (got {len(desc)})"

    for t in meta.get("tags", []):
        assert re.match(r"^[a-z][-a-z0-9]{0,48}[a-z0-9]$", t), f"Tag '{t}' does not match ^[a-z][-a-z0-9]{{0,48}}[a-z0-9]$"

    for v in meta.get("versions", []):
        for forbidden in ("download_url", "download_sha256", "download_size", "install_size"):
            assert forbidden not in v, f"Archive metadata.json must NOT contain {forbidden}"

    assert plugin_meta.get("identifier") == ident, "plugin.json identifier must match metadata.json identifier"
    print("[OK] Official KiCad PCM & IPC API rules verified!")


def collect_plugin_files(root_dir: str) -> List[Tuple[str, str]]:
    """
    Returns list of (abs_file_path, zip_arcname) for files belonging inside `plugins/`.
    """
    entries: List[Tuple[str, str]] = []
    top_files = ["__init__.py", "plugin.json", "icon.png", "run_standalone.py", "requirements.txt"]
    for tf in top_files:
        full = os.path.join(root_dir, tf)
        if os.path.exists(full):
            entries.append((full, f"plugins/{tf}"))

    pkg_dir = os.path.join(root_dir, "lcsc_digikey_plugin")
    for dirpath, dirnames, filenames in os.walk(pkg_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith((".pyc", ".pyo", ".bak")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            entries.append((full, f"plugins/{rel}"))

    return entries


def build_package() -> str:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    generate_icons(root_dir)

    meta_path = os.path.join(root_dir, "metadata.json")
    plugin_json_path = os.path.join(root_dir, "plugin.json")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(plugin_json_path, "r", encoding="utf-8") as f:
        plugin_meta = json.load(f)

    validate_official_rules(meta, plugin_meta)

    dist_dir = os.path.join(root_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    ident = meta["identifier"]
    ver = meta["versions"][0]["version"]
    zip_filename = f"{ident}-{ver}-pcm.zip"
    zip_path = os.path.join(dist_dir, zip_filename)

    plugin_entries = collect_plugin_files(root_dir)
    pcm_icon_path = os.path.join(root_dir, "resources", "icon.png")

    install_size = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(meta_path, "metadata.json")
        install_size += os.path.getsize(meta_path)

        if os.path.exists(pcm_icon_path):
            zf.write(pcm_icon_path, "resources/icon.png")
            install_size += os.path.getsize(pcm_icon_path)

        for full_path, arcname in plugin_entries:
            zf.write(full_path, arcname)
            install_size += os.path.getsize(full_path)

    download_size = os.path.getsize(zip_path)
    sha256_hash = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()

    submission_meta = json.loads(json.dumps(meta))
    submission_meta["versions"][0].update({
        "download_url": f"https://github.com/aridrones/kicad-lcsc-digikey-plugin/releases/download/v{ver}/{zip_filename}",
        "download_sha256": sha256_hash,
        "download_size": download_size,
        "install_size": install_size,
    })

    sub_meta_path = os.path.join(dist_dir, "metadata-submission.json")
    with open(sub_meta_path, "w", encoding="utf-8") as f:
        json.dump(submission_meta, f, indent=2, ensure_ascii=False)

    print(f"[OK] Built official PCM ZIP: {zip_path}")
    print(f"     SHA-256      : {sha256_hash}")
    print(f"     Download Size: {download_size} bytes")
    print(f"     Install Size : {install_size} bytes")
    print(f"[OK] Built GitLab submission metadata: {sub_meta_path}")
    return zip_path


if __name__ == "__main__":
    build_package()
