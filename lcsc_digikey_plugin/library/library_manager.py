"""
KiCad 10 Library & Lib-Table Manager
Manages category-based .kicad_sym files, .pretty footprint folders, .3dshapes folders,
and automatic registration in Global or Project sym-lib-table and fp-lib-table.
"""

import os
import re
import shutil
from typing import Dict, Any, Optional, Tuple, List
from lcsc_digikey_plugin.config import ConfigManager
from lcsc_digikey_plugin.converters.easyeda_converter import EasyEDA2KiCadConverter
from lcsc_digikey_plugin.api.lcsc_easyeda_client import LcscEasyEdaClient


class LibraryManager:
    """Handles writing symbols, footprints, 3D models, and updating KiCad lib-tables."""

    def __init__(self, config: ConfigManager, lcsc_client: Optional[LcscEasyEdaClient] = None):
        self.config = config
        self.converter = EasyEDA2KiCadConverter()
        self.lcsc_client = lcsc_client or LcscEasyEdaClient()

    def resolve_base_dir(self, project_dir: Optional[str] = None) -> Tuple[str, bool]:
        """
        Returns (base_library_dir, is_project_scope).
        """
        scope = self.config.settings.get("library_scope", "global")
        if scope == "project" and project_dir and os.path.isdir(project_dir):
            sub = self.config.settings.get("project_library_subdir", "Libraries").strip() or "Libraries"
            return os.path.join(project_dir, sub), True
        global_dir = self.config.settings.get("global_library_dir") or self.config._get_default_global_lib_dir()
        return global_dir, False

    def get_library_name_for_category(self, category: str) -> str:
        prefix = (self.config.settings.get("library_prefix") or "ARI_").strip()
        if not self.config.settings.get("organize_by_category", True):
            single = (self.config.settings.get("single_library_name") or "Custom_Components").strip()
            return f"{prefix}{single}" if prefix and not single.startswith(prefix) else single
        clean_cat = re.sub(r"[^A-Za-z0-9_-]", "_", category or "Misc_Components")
        return f"{prefix}{clean_cat}" if prefix and not clean_cat.startswith(prefix) else clean_cat

    def import_component(
        self,
        part_info: Dict[str, Any],
        cad_data: Dict[str, Any],
        project_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exports Symbol (.kicad_sym), Footprint (.kicad_mod), and 3D Models (.step / .wrl)
        into the target category library and registers the library in KiCad's lib-tables.
        """
        base_dir, is_project_scope = self.resolve_base_dir(project_dir)
        symbols_dir = os.path.join(base_dir, "symbols")
        footprints_dir = os.path.join(base_dir, "footprints")
        models_dir = os.path.join(base_dir, "3dmodels")

        os.makedirs(symbols_dir, exist_ok=True)
        os.makedirs(footprints_dir, exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)

        category = part_info.get("category") or "Misc_Components"
        lib_name = self.get_library_name_for_category(category)

        sym_file_path = os.path.join(symbols_dir, f"{lib_name}.kicad_sym")
        pretty_dir_path = os.path.join(footprints_dir, f"{lib_name}.pretty")
        shapes3d_dir_path = os.path.join(models_dir, f"{lib_name}.3dshapes")

        os.makedirs(pretty_dir_path, exist_ok=True)
        os.makedirs(shapes3d_dir_path, exist_ok=True)

        mpn = self._sanitize_identifier(part_info.get("mpn") or cad_data.get("title") or part_info.get("lcsc_part") or "Part")
        fp_name = self._sanitize_identifier(
            part_info.get("footprint_name")
            or cad_data.get("footprint_name")
            or part_info.get("package")
            or f"{mpn}_FP"
        )
        fp_file_path = os.path.join(pretty_dir_path, f"{fp_name}.kicad_mod")

        # 1. Download 3D Models (.step / .wrl) if available
        model_3d_info = cad_data.get("model_3d")
        model_3d_paths: List[str] = []
        downloaded_3d_files: List[str] = []

        if model_3d_info and model_3d_info.get("uuid"):
            uuid_3d = model_3d_info["uuid"]
            model_title = self._sanitize_identifier(model_3d_info.get("title") or fp_name or mpn)

            if self.config.settings.get("download_3d_step", True):
                step_file = os.path.join(shapes3d_dir_path, f"{model_title}.step")
                if not os.path.exists(step_file) or os.path.getsize(step_file) < 100:
                    self.lcsc_client.download_step_model(uuid_3d, step_file)
                if os.path.exists(step_file) and os.path.getsize(step_file) >= 100:
                    downloaded_3d_files.append(step_file)
                    if is_project_scope and project_dir:
                        rel_step = os.path.relpath(step_file, project_dir).replace("\\", "/")
                        model_3d_paths.append(f"${{KIPRJMOD}}/{rel_step}")
                    else:
                        model_3d_paths.append(step_file.replace("\\", "/"))

            if self.config.settings.get("download_3d_wrl", False):
                wrl_file = os.path.join(shapes3d_dir_path, f"{model_title}.wrl")
                if not os.path.exists(wrl_file) or os.path.getsize(wrl_file) < 100:
                    self.lcsc_client.download_wrl_model(uuid_3d, wrl_file)
                if os.path.exists(wrl_file) and os.path.getsize(wrl_file) >= 100:
                    downloaded_3d_files.append(wrl_file)
                    if is_project_scope and project_dir:
                        rel_wrl = os.path.relpath(wrl_file, project_dir).replace("\\", "/")
                        model_3d_paths.append(f"${{KIPRJMOD}}/{rel_wrl}")
                    else:
                        model_3d_paths.append(wrl_file.replace("\\", "/"))

        # 2. Generate and save .kicad_mod footprint file
        footprint_data = cad_data.get("footprint_data") or {}
        if footprint_data:
            fp_sexpr = self.converter.generate_kicad_footprint(
                footprint_name=fp_name,
                footprint_data=footprint_data,
                model_3d_paths=model_3d_paths,
                model_3d_info=model_3d_info,
                description=part_info.get("description", ""),
            )
            if self.config.settings.get("overwrite_existing_footprint", True) or not os.path.exists(fp_file_path):
                with open(fp_file_path, "w", encoding="utf-8") as f:
                    f.write(fp_sexpr)

        # 3. Generate and insert/update .kicad_sym symbol block with full BOM fields
        footprint_ref = f"{lib_name}:{fp_name}"
        raw_prefix = (cad_data.get("metadata") or {}).get("prefix", "")
        ref_prefix = ConfigManager.get_reference_prefix(category, part_info.get("reference_prefix") or raw_prefix)

        unit_price = part_info.get("unit_price", 0.0)
        lcsc_price = part_info.get("lcsc_price", 0.0)
        dk_price = part_info.get("digikey_price", 0.0)

        sym_properties = {
            "Reference": ref_prefix,
            "Value": part_info.get("value") or mpn,
            "Footprint": footprint_ref,
            "Datasheet": part_info.get("datasheet", ""),
            "Description": part_info.get("description", ""),
            "Manufacturer": part_info.get("manufacturer", ""),
            "MPN": part_info.get("mpn") or mpn,
            "LCSC_Part": part_info.get("lcsc_part", ""),
            "DigiKey_Part": part_info.get("digikey_part", ""),
            "Category": category,
            "Package": part_info.get("package", ""),
            "Unit_Price": f"{float(unit_price):.4f}" if unit_price else "",
            "LCSC_Price": f"{float(lcsc_price):.4f}" if lcsc_price else "",
            "DigiKey_Price": f"{float(dk_price):.4f}" if dk_price else "",
            "Stock": str(part_info.get("stock", "")),
            "Part_Type": part_info.get("part_type", ""),
            "Supplier_URL": part_info.get("supplier_url", ""),
            "DigiKey_URL": part_info.get("digikey_url", ""),
        }

        symbol_data = cad_data.get("symbol_data") or {}
        sym_block = self.converter.generate_kicad_symbol_block(
            symbol_name=mpn,
            symbol_data=symbol_data,
            properties=sym_properties,
        )
        self._upsert_symbol_in_library(
            sym_file_path=sym_file_path,
            symbol_name=mpn,
            symbol_block=sym_block,
            overwrite=self.config.settings.get("overwrite_existing_symbol", True),
        )

        # 4. Register in sym-lib-table and fp-lib-table
        sym_table_updated = False
        fp_table_updated = False
        if self.config.settings.get("auto_register_lib_tables", True):
            sym_table_updated, fp_table_updated = self.register_libraries_in_tables(
                lib_name=lib_name,
                sym_file_path=sym_file_path,
                pretty_dir_path=pretty_dir_path,
                is_project_scope=is_project_scope,
                project_dir=project_dir,
                category=category,
            )

        # 5. Save component metadata in local database for fast BOM enrichment
        part_record = dict(part_info)
        part_record["symbol_lib"] = f"{lib_name}:{mpn}"
        part_record["footprint_ref"] = footprint_ref
        self.config.save_component_to_db(part_record)

        return {
            "success": True,
            "lib_name": lib_name,
            "symbol_name": mpn,
            "symbol_ref": f"{lib_name}:{mpn}",
            "footprint_ref": footprint_ref,
            "sym_file_path": sym_file_path,
            "fp_file_path": fp_file_path,
            "downloaded_3d_files": downloaded_3d_files,
            "sym_table_updated": sym_table_updated,
            "fp_table_updated": fp_table_updated,
        }

    def _upsert_symbol_in_library(
        self,
        sym_file_path: str,
        symbol_name: str,
        symbol_block: str,
        overwrite: bool = True,
    ) -> None:
        """Inserts or replaces a `(symbol "<symbol_name>" ...)` block inside a `.kicad_sym` file."""
        if not os.path.exists(sym_file_path) or os.path.getsize(sym_file_path) < 20:
            content = (
                "(kicad_symbol_lib\n"
                "\t(version 20231120)\n"
                '\t(generator "kicad_lcsc_digikey_importer")\n'
                '\t(generator_version "10.0")\n'
                f"{symbol_block}\n"
                ")\n"
            )
            with open(sym_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return

        with open(sym_file_path, "r", encoding="utf-8") as f:
            existing = f.read()

        escaped_name = self.converter.escape_sexpr_str(symbol_name)
        target_header = f'(symbol "{escaped_name}"'

        # Check if symbol already exists in library
        start_idx = self._find_top_level_symbol(existing, target_header)
        if start_idx != -1:
            if not overwrite:
                return
            end_idx = self._find_matching_paren(existing, start_idx)
            if end_idx != -1:
                # Replace existing symbol block
                line_start = existing.rfind("\n", 0, start_idx)
                if line_start == -1:
                    line_start = start_idx
                else:
                    line_start += 1
                new_content = existing[:line_start] + symbol_block + existing[end_idx + 1:]
                with open(sym_file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return

        # Append before final closing ')'
        last_paren = existing.rfind(")")
        if last_paren != -1:
            prefix = existing[:last_paren].rstrip()
            new_content = f"{prefix}\n{symbol_block}\n)\n"
        else:
            new_content = existing + f"\n{symbol_block}\n)\n"

        with open(sym_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    @staticmethod
    def _find_top_level_symbol(text: str, target_header: str) -> int:
        pos = 0
        while True:
            idx = text.find(target_header, pos)
            if idx == -1:
                return -1
            after_char = text[idx + len(target_header) : idx + len(target_header) + 1]
            if after_char in ("", " ", "\t", "\r", "\n"):
                return idx
            pos = idx + len(target_header)

    @staticmethod
    def _find_matching_paren(text: str, start_idx: int) -> int:
        depth = 0
        in_str = False
        escape = False
        for i in range(start_idx, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        return i
        return -1

    def register_libraries_in_tables(
        self,
        lib_name: str,
        sym_file_path: str,
        pretty_dir_path: str,
        is_project_scope: bool,
        project_dir: Optional[str],
        category: str,
    ) -> Tuple[bool, bool]:
        if is_project_scope and project_dir:
            table_dir = project_dir
            rel_sym = os.path.relpath(sym_file_path, project_dir).replace("\\", "/")
            rel_fp = os.path.relpath(pretty_dir_path, project_dir).replace("\\", "/")
            sym_uri = f"${{KIPRJMOD}}/{rel_sym}"
            fp_uri = f"${{KIPRJMOD}}/{rel_fp}"
        else:
            table_dir = self.config.settings.get("kicad_config_dir") or self.config._get_kicad_config_dir()
            sym_uri = sym_file_path.replace("\\", "/")
            fp_uri = pretty_dir_path.replace("\\", "/")

        os.makedirs(table_dir, exist_ok=True)
        sym_table_path = os.path.join(table_dir, "sym-lib-table")
        fp_table_path = os.path.join(table_dir, "fp-lib-table")

        descr = f"LCSC & DigiKey Auto Library ({category})"
        sym_added = self._ensure_lib_table_entry(sym_table_path, "sym_lib_table", lib_name, sym_uri, descr)
        fp_added = self._ensure_lib_table_entry(fp_table_path, "fp_lib_table", lib_name, fp_uri, descr)
        return sym_added, fp_added

    @staticmethod
    def _ensure_lib_table_entry(
        table_path: str,
        root_tag: str,
        lib_name: str,
        uri: str,
        descr: str,
    ) -> bool:
        entry_line = f'\t(lib (name "{lib_name}") (type "KiCad") (uri "{uri}") (options "") (descr "{descr}"))'

        if not os.path.exists(table_path):
            content = f"({root_tag}\n\t(version 7)\n{entry_line}\n)\n"
            with open(table_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

        with open(table_path, "r", encoding="utf-8") as f:
            content = f.read()

        if f'(name "{lib_name}")' in content:
            return False

        # Backup once before modifying
        bak_path = f"{table_path}.importer_bak"
        if not os.path.exists(bak_path):
            try:
                shutil.copy2(table_path, bak_path)
            except Exception:
                pass

        last_paren = content.rfind(")")
        if last_paren != -1:
            new_content = content[:last_paren].rstrip() + f"\n{entry_line}\n)\n"
        else:
            new_content = f"({root_tag}\n\t(version 7)\n{entry_line}\n)\n"

        with open(table_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        clean = re.sub(r'[\\/:*?"<>|\s]+', "_", (name or "").strip())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "Component"
