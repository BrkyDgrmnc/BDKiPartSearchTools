"""
KiCad 10 Installer Script for BDPartSearchTools (by Berkay Değirmenci)
Cleans up legacy plugin copies and installs into 3rdparty/plugins/com_berkaydegirmenci_bdpartsearchtools
"""

import os
import json
import shutil
from build_pcm_package import build_package


def install():
    src = os.path.dirname(os.path.abspath(__file__))
    build_package()

    # Remove all old/duplicate plugin folders so KiCad never has duplicate identifier conflicts
    old_dirs = [
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\plugins\com_ari_lcsc_digikey_importer"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\com_ari_lcsc_digikey_importer"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\plugins\com_github_aridrones_lcsc-digikey-importer"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\com_github_aridrones_lcsc-digikey-importer"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\plugins\com_aridrones_lcscdigikeyimporter"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\com_aridrones_lcscdigikeyimporter"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\com_berkaydegirmenci_bdpartsearchtools"),
        os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins\kicad-lcsc-digikey-plugin"),
    ]
    for old_dir in old_dirs:
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir, ignore_errors=True)

    pcm_pkg_folder = "com_berkaydegirmenci_bdkipartsearchtools"
    target = os.path.expandvars(rf"%USERPROFILE%\Documents\KiCad\10.0\3rdparty\plugins\{pcm_pkg_folder}")
    os.makedirs(target, exist_ok=True)
    shutil.copytree(
        src,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("dist", "__pycache__", "*.pyc", ".git"),
    )
    print("Installed to:", target)

    # Register in eeschema.json and pcbnew.json
    action_key = "com.berkaydegirmenci.bdkipartsearchtools.open_bdkipartsearchtools"
    old_keys = {
        "com.ari.lcsc_digikey_importer.open_importer",
        "com.github.aridrones.lcsc-digikey-importer.open-importer",
        "com.aridrones.lcscdigikeyimporter.open_importer",
        "com.berkaydegirmenci.bdpartsearchtools.open_bdpartsearchtools",
    }

    for cfg_name in ("eeschema.json", "pcbnew.json"):
        cfg_path = os.path.expandvars(rf"%APPDATA%\kicad\10.0\{cfg_name}")
        if not os.path.exists(cfg_path):
            continue
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        plugins_sec = cfg.setdefault("plugins", {})
        actions_list = plugins_sec.setdefault("actions", [])
        actions_list = [
            a for a in actions_list
            if not (isinstance(a, dict) and any(k in a for k in old_keys))
        ]
        if not any(isinstance(a, dict) and action_key in a for a in actions_list):
            actions_list.append({action_key: True})
        plugins_sec["actions"] = actions_list

        if cfg_name == "pcbnew.json":
            ap_list = cfg.setdefault("action_plugins", [])
            ap_list = [
                x for x in ap_list
                if not (isinstance(x, dict) and x.get("name") in ("LCSC & DigiKey Kütüphane ve BOM Yöneticisi", "BDPartSearchTools", "BDKiPartSearchTools"))
            ]
            ap_list.append({
                "name": "BDKiPartSearchTools",
                "path": os.path.join(target, "__init__.py").replace("\\", "/"),
                "visible": True,
            })
            cfg["action_plugins"] = ap_list

        if cfg_name == "eeschema.json":
            bom_sec = cfg.setdefault("bom", {})
            bom_plugins = bom_sec.setdefault("plugins", [])
            runner_path = os.path.join(target, "run_standalone.py").replace("\\", "/")
            bom_cmd = f'"E:\\KiCad\\bin\\pythonw.exe" "{runner_path}" "%I"'
            bom_name = "BDKiPartSearchTools"
            bom_plugins = [
                p for p in bom_plugins
                if p.get("name") not in ("LCSC_DigiKey_Kutuphane_ve_Fiyatli_BOM", "BDPartSearchTools", "BDKiPartSearchTools")
            ]
            bom_plugins.append({
                "command": bom_cmd,
                "name": bom_name,
                "path": runner_path,
            })
            bom_sec["plugins"] = bom_plugins
            bom_sec["selected_plugin"] = bom_name

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"Updated {cfg_name} with BDKiPartSearchTools identifier!")

    # Clean up old LC_DK_Library auto-entries from sym-lib-table and fp-lib-table and pre-register all 14 BDKi_* category libraries
    from lcsc_digikey_plugin.config import ConfigManager
    from lcsc_digikey_plugin.library.library_manager import LibraryManager
    cfg_mgr = ConfigManager()
    kicad_cfg_dir = cfg_mgr._get_kicad_config_dir()
    for tbl_name in ("sym-lib-table", "fp-lib-table"):
        tbl_path = os.path.join(kicad_cfg_dir, tbl_name)
        if os.path.exists(tbl_path):
            with open(tbl_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cleaned = [ln for ln in lines if "LC_DK_Library" not in ln]
            if len(cleaned) != len(lines):
                with open(tbl_path, "w", encoding="utf-8") as f:
                    f.writelines(cleaned)

    lib_mgr = LibraryManager(cfg_mgr)
    lib_mgr.ensure_all_category_libraries_initialized()
    print("Pre-registered all 14 BDKi_* category libraries in sym-lib-table and fp-lib-table!")


if __name__ == "__main__":
    install()
