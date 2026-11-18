"""
KiCad 10 Installer Script for LCSC & DigiKey Component Importer & Smart BOM
Follows official PCM directory naming (dots replaced with underscores:
com_github_aridrones_lcsc-digikey-importer)
"""

import os
import json
import shutil
from build_pcm_package import build_package


def install():
    src = os.path.dirname(os.path.abspath(__file__))
    build_package()

    # Remove old local test folder if present
    for old_dir in [
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\plugins\com_ari_lcsc_digikey_importer"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\com_ari_lcsc_digikey_importer"),
    ]:
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir, ignore_errors=True)

    # Official PCM extracted directory name: dots replaced with underscores
    pcm_pkg_folder = "com_github_aridrones_lcsc-digikey-importer"
    targets = [
        os.path.expandvars(rf"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\{pcm_pkg_folder}"),
        os.path.expandvars(rf"%USERPROFILE%\Documents\KiCad\10.0\plugins\{pcm_pkg_folder}"),
    ]

    for t in targets:
        if os.path.exists(t):
            shutil.rmtree(t)
        shutil.copytree(
            src,
            t,
            ignore=shutil.ignore_patterns("dist", "__pycache__", "*.pyc", ".git"),
        )
        print("Installed to:", t)

    # Register in eeschema.json and pcbnew.json
    action_key = "com.github.aridrones.lcsc-digikey-importer.open-importer"
    old_key = "com.ari.lcsc_digikey_importer.open_importer"

    for cfg_name in ("eeschema.json", "pcbnew.json"):
        cfg_path = os.path.expandvars(rf"%APPDATA%\kicad\10.0\{cfg_name}")
        if not os.path.exists(cfg_path):
            continue
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        plugins_sec = cfg.setdefault("plugins", {})
        actions_list = plugins_sec.setdefault("actions", [])
        actions_list = [a for a in actions_list if not (isinstance(a, dict) and old_key in a)]
        if not any(isinstance(a, dict) and action_key in a for a in actions_list):
            actions_list.append({action_key: True})
        plugins_sec["actions"] = actions_list

        if cfg_name == "eeschema.json":
            bom_sec = cfg.setdefault("bom", {})
            bom_plugins = bom_sec.setdefault("plugins", [])
            runner_path = os.path.join(targets[0], "run_standalone.py").replace("\\", "/")
            bom_cmd = f'"E:\\KiCad\\bin\\pythonw.exe" "{runner_path}" "%I"'
            bom_name = "LCSC_DigiKey_Kutuphane_ve_Fiyatli_BOM"
            bom_plugins = [p for p in bom_plugins if p.get("name") != bom_name]
            bom_plugins.append({
                "command": bom_cmd,
                "name": bom_name,
                "path": runner_path,
            })
            bom_sec["plugins"] = bom_plugins
            bom_sec["selected_plugin"] = bom_name

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"Updated {cfg_name} with official plugin identifier!")


if __name__ == "__main__":
    install()
