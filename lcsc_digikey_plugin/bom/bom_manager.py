"""
Smart Engineering BOM & Live Pricing/Stock Engine for KiCad 10
Extracts components from active PCB board AND project .kicad_sch schematics,
enriches with local cache + live LCSC / DigiKey API pricing & stock,
and exports Engineering BOM (CSV & HTML), JLCPCB BOM, and DigiKey Bulk CSV.
"""

import os
import re
import csv
import glob
from typing import Dict, Any, List, Optional, Tuple
from lcsc_digikey_plugin.config import ConfigManager
from lcsc_digikey_plugin.api.hybrid_service import HybridSupplierService


class BomManager:
    """Extracts, enriches, prices, and exports Bill of Materials (BOM) data."""

    def __init__(self, config: ConfigManager, supplier_service: HybridSupplierService):
        self.config = config
        self.supplier_service = supplier_service

    def extract_project_bom(self, board=None, project_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extracts components from the active pcbnew.BOARD and/or .kicad_sch files in project_dir,
        cross-referencing with local component cache and grouping into BOM rows.
        """
        if not project_dir and board is not None:
            try:
                board_file = str(board.GetFileName() or "")
                if board_file:
                    project_dir = os.path.dirname(os.path.abspath(board_file))
            except Exception:
                pass

        # 1. Parse schematic symbol properties (.kicad_sch) in project_dir for rich custom fields
        sch_props_by_ref: Dict[str, Dict[str, str]] = {}
        if project_dir and os.path.isdir(project_dir):
            sch_props_by_ref = self._parse_project_schematics(project_dir)

        # 2. Extract instances from PCB board if available; otherwise from schematic instances
        raw_instances: List[Dict[str, Any]] = []
        if board is not None:
            raw_instances = self._extract_from_pcb_board(board, sch_props_by_ref)

        if not raw_instances and sch_props_by_ref:
            for ref, props in sch_props_by_ref.items():
                if ref.startswith("#") or ref.startswith("PWR"):
                    continue
                raw_instances.append(self._normalize_instance(ref, props))

        # 3. Group instances into BOM lines
        return self._group_bom_items(raw_instances)

    def _extract_from_pcb_board(self, board, sch_props_by_ref: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        instances: List[Dict[str, Any]] = []
        try:
            import pcbnew
            footprints = board.GetFootprints()
        except Exception:
            return instances

        for fp in footprints:
            try:
                if hasattr(fp, "IsDNP") and fp.IsDNP():
                    continue
                attrs = fp.GetAttributes()
                if attrs & pcbnew.FP_EXCLUDE_FROM_BOM:
                    continue
            except Exception:
                pass

            try:
                ref = str(fp.GetReference() or "").strip()
            except Exception:
                ref = ""
            if not ref or ref.startswith("REF**") or ref.startswith("#"):
                continue

            props: Dict[str, str] = {}
            # Merge schematic properties first
            if ref in sch_props_by_ref:
                props.update(sch_props_by_ref[ref])

            # Extract PCB footprint fields/properties
            try:
                props["Reference"] = ref
                props["Value"] = str(fp.GetValue() or props.get("Value", "")).strip()
                fpid = fp.GetFPID()
                if hasattr(fpid, "GetLibItemName"):
                    item = fpid.GetLibItemName()
                    fp_name = str(item.AsString()) if hasattr(item, "AsString") else str(item)
                else:
                    fp_name = str(fpid)
                props["Footprint"] = fp_name or props.get("Footprint", "")
            except Exception:
                pass

            # KiCad 8/9/10 footprint custom fields
            try:
                if hasattr(fp, "GetFieldsText"):
                    fields_map = fp.GetFieldsText()
                    for k in fields_map.keys():
                        val = str(fields_map[k] or "").strip()
                        if val:
                            props[str(k)] = val
                elif hasattr(fp, "GetProperties"):
                    props_map = fp.GetProperties()
                    for k in props_map.keys():
                        val = str(props_map[k] or "").strip()
                        if val:
                            props[str(k)] = val
            except Exception:
                pass

            instances.append(self._normalize_instance(ref, props))

        return instances

    def _parse_project_schematics(self, project_dir: str) -> Dict[str, Dict[str, str]]:
        """
        Parses all `.kicad_sch` files in `project_dir` to extract placed symbol properties
        (MPN, LCSC_Part, DigiKey_Part, Unit_Price, Manufacturer, Supplier_URL, etc.).
        """
        result: Dict[str, Dict[str, str]] = {}
        sch_files = glob.glob(os.path.join(project_dir, "*.kicad_sch"))

        for sch_path in sch_files:
            try:
                with open(sch_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # Find placed symbol blocks (outside lib_symbols section)
            lib_sym_idx = content.find("(lib_symbols")
            search_start = 0
            if lib_sym_idx != -1:
                lib_sym_end = self._find_matching_paren(content, lib_sym_idx)
                if lib_sym_end != -1:
                    search_start = lib_sym_end + 1

            pos = search_start
            while True:
                sym_idx = content.find("(symbol", pos)
                if sym_idx == -1:
                    break
                after = content[sym_idx + 7 : sym_idx + 8]
                if after not in (" ", "\t", "\r", "\n"):
                    pos = sym_idx + 7
                    continue
                end_idx = self._find_matching_paren(content, sym_idx)
                if end_idx == -1:
                    break

                block = content[sym_idx : end_idx + 1]
                if "(lib_id " in block and "(in_bom no)" not in block and "(dnp yes)" not in block:
                    props: Dict[str, str] = {}
                    for m in re.finditer(r'\(property\s+"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"', block):
                        p_key = m.group(1).replace('\\"', '"')
                        p_val = m.group(2).replace('\\"', '"').strip()
                        if p_val:
                            props[p_key] = p_val

                    # Also check instances -> path -> reference in KiCad 8/9/10 schematics
                    inst_ref_m = re.search(r'\(reference\s+"([^"]+)"\)', block)
                    ref = (inst_ref_m.group(1) if inst_ref_m else props.get("Reference", "")).strip()
                    if ref and not ref.endswith("?") and not ref.startswith("#"):
                        props["Reference"] = ref
                        result[ref] = props

                pos = end_idx + 1

        return result

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

    def _normalize_instance(self, ref: str, props: Dict[str, str]) -> Dict[str, Any]:
        def pick(*keys: str) -> str:
            for k in keys:
                for pk, pv in props.items():
                    if pk.lower() == k.lower() and pv.strip():
                        return pv.strip()
            return ""

        val = pick("Value")
        fp = pick("Footprint")
        if ":" in fp:
            fp_short = fp.split(":", 1)[1]
        else:
            fp_short = fp

        mpn = pick("MPN", "Manufacturer Part", "Manufacturer_Part_Number", "PartNumber", "Mfg Part") or val
        lcsc = pick("LCSC_Part", "LCSC Part", "LCSC", "JLC", "JLCPCB")
        dk = pick("DigiKey_Part", "DigiKey Part", "DigiKey", "DK_Part")
        mfg = pick("Manufacturer", "Brand", "Mfg")
        cat = pick("Category")
        pkg = pick("Package") or fp_short
        ds = pick("Datasheet")
        desc = pick("Description")
        sup_url = pick("Supplier_URL", "LCSC_URL")
        dk_url = pick("DigiKey_URL")
        part_type = pick("Part_Type", "JLCPCB Part Class")

        def parse_float(s: str) -> float:
            try:
                clean = re.sub(r"[^0-9.]", "", str(s or ""))
                return float(clean) if clean else 0.0
            except Exception:
                return 0.0

        def parse_int(s: str) -> int:
            try:
                clean = re.sub(r"[^0-9]", "", str(s or ""))
                return int(clean) if clean else 0
            except Exception:
                return 0

        unit_price = parse_float(pick("Unit_Price", "Price"))
        lcsc_price = parse_float(pick("LCSC_Price"))
        dk_price = parse_float(pick("DigiKey_Price"))
        stock = parse_int(pick("Stock"))
        price_tiers = []

        # Enrich from local imported component cache if any field is missing
        cached = self.config.lookup_cached_part(mpn=mpn, lcsc=lcsc, digikey=dk)
        if cached:
            mpn = mpn or cached.get("mpn", "")
            lcsc = lcsc or cached.get("lcsc_part", "")
            dk = dk or cached.get("digikey_part", "")
            mfg = mfg or cached.get("manufacturer", "")
            cat = cat or cached.get("category", "")
            pkg = pkg or cached.get("package", "")
            ds = ds or cached.get("datasheet", "")
            desc = desc or cached.get("description", "")
            sup_url = sup_url or cached.get("supplier_url", "")
            dk_url = dk_url or cached.get("digikey_url", "")
            part_type = part_type or cached.get("part_type", "")
            price_tiers = cached.get("price_tiers", [])
            if unit_price <= 0:
                unit_price = float(cached.get("unit_price") or 0.0)
            if lcsc_price <= 0:
                lcsc_price = float(cached.get("lcsc_price") or 0.0)
            if dk_price <= 0:
                dk_price = float(cached.get("digikey_price") or 0.0)
            if stock <= 0:
                stock = int(cached.get("stock") or 0)

        if not cat:
            cat = ConfigManager.detect_category("", desc, mpn)

        return {
            "ref": ref,
            "value": val,
            "footprint": fp_short,
            "mpn": mpn,
            "manufacturer": mfg,
            "lcsc_part": lcsc,
            "digikey_part": dk,
            "category": cat,
            "package": pkg,
            "unit_price": unit_price,
            "lcsc_price": lcsc_price,
            "digikey_price": dk_price,
            "price_tiers": price_tiers,
            "stock": stock,
            "part_type": part_type,
            "datasheet": ds,
            "supplier_url": sup_url,
            "digikey_url": dk_url,
            "description": desc,
        }

    def _group_bom_items(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        groups: Dict[Tuple[str, ...], Dict[str, Any]] = {}

        for inst in instances:
            key = (
                (inst.get("mpn") or inst.get("value") or "").upper(),
                (inst.get("lcsc_part") or "").upper(),
                (inst.get("digikey_part") or "").upper(),
                (inst.get("footprint") or "").upper(),
            )
            if key not in groups:
                row = dict(inst)
                row["refs"] = [inst["ref"]]
                row["qty_per_board"] = 1
                groups[key] = row
            else:
                groups[key]["refs"].append(inst["ref"])
                groups[key]["qty_per_board"] += 1

        bom_rows = []
        for row in groups.values():
            row["refs"].sort(key=self._natural_ref_key)
            row["designators"] = ", ".join(row["refs"])
            bom_rows.append(row)

        bom_rows.sort(key=lambda r: self._natural_ref_key(r["refs"][0] if r["refs"] else ""))
        return bom_rows

    @staticmethod
    def _natural_ref_key(ref: str) -> Tuple[str, int]:
        m = re.match(r"^([A-Za-z_]+)(\d+)$", ref or "")
        if m:
            return (m.group(1), int(m.group(2)))
        return (ref or "", 0)

    def refresh_live_pricing_and_stock(
        self,
        bom_rows: List[Dict[str, Any]],
        board_count: int = 1,
        progress_cb=None,
    ) -> List[Dict[str, Any]]:
        """
        Queries LCSC and DigiKey APIs for every BOM line to fetch live stock, part numbers,
        and quantity-adjusted unit prices.
        """
        total = len(bom_rows)
        board_count = max(1, int(board_count))

        for idx, row in enumerate(bom_rows):
            if progress_cb:
                progress_cb(idx + 1, total, row.get("mpn") or row.get("value") or "")

            lcsc_code = (row.get("lcsc_part") or "").strip()
            mpn = (row.get("mpn") or row.get("value") or "").strip()
            dk_code = (row.get("digikey_part") or "").strip()
            total_qty = max(1, int(row.get("qty_per_board", 1)) * board_count)

            # 1. Query LCSC by LCSC code or MPN
            query_str = lcsc_code or mpn
            if query_str:
                lcsc_matches = self.supplier_service.lcsc.search_components(query_str, page_size=5)
                best = None
                for m in lcsc_matches:
                    if lcsc_code and (m.get("lcsc_part") or "").upper() == lcsc_code.upper():
                        best = m
                        break
                    if mpn and (m.get("mpn") or "").upper() == mpn.upper():
                        best = m
                        break
                if not best and lcsc_matches:
                    best = lcsc_matches[0]

                if best:
                    row["lcsc_part"] = row.get("lcsc_part") or best.get("lcsc_part", "")
                    row["mpn"] = row.get("mpn") or best.get("mpn", "")
                    row["manufacturer"] = row.get("manufacturer") or best.get("manufacturer", "")
                    row["datasheet"] = row.get("datasheet") or best.get("datasheet", "")
                    row["description"] = row.get("description") or best.get("description", "")
                    row["supplier_url"] = row.get("supplier_url") or best.get("supplier_url", "")
                    row["part_type"] = row.get("part_type") or best.get("part_type", "")
                    row["price_tiers"] = best.get("price_tiers") or row.get("price_tiers", [])
                    eff_lcsc_price = HybridSupplierService.get_unit_price_for_qty(
                        row["price_tiers"], best.get("lcsc_price", 0.0), total_qty
                    )
                    if eff_lcsc_price > 0:
                        row["lcsc_price"] = eff_lcsc_price
                        row["unit_price"] = eff_lcsc_price
                    if best.get("stock", 0) > 0 or row.get("stock", 0) == 0:
                        row["stock"] = best.get("stock", 0)
                        row["lcsc_stock"] = best.get("stock", 0)

            # 2. Query DigiKey if configured
            if self.supplier_service.digikey.is_configured and (dk_code or mpn):
                dk_info = None
                if dk_code:
                    dk_info = self.supplier_service.digikey.get_product_details(dk_code)
                if not dk_info and mpn:
                    dk_list = self.supplier_service.digikey.search_keyword(mpn, limit=3)
                    if dk_list:
                        dk_info = dk_list[0]
                if dk_info:
                    row["digikey_part"] = row.get("digikey_part") or dk_info.get("digikey_part", "")
                    row["digikey_url"] = row.get("digikey_url") or dk_info.get("digikey_url", "")
                    eff_dk_price = HybridSupplierService.get_unit_price_for_qty(
                        dk_info.get("price_tiers", []), dk_info.get("digikey_price", 0.0), total_qty
                    )
                    if eff_dk_price > 0:
                        row["digikey_price"] = eff_dk_price
                        if row.get("unit_price", 0.0) <= 0:
                            row["unit_price"] = eff_dk_price
                    if dk_info.get("digikey_stock", 0) > 0:
                        row["digikey_stock"] = dk_info["digikey_stock"]
                        if row.get("stock", 0) <= 0:
                            row["stock"] = dk_info["digikey_stock"]

            if not row.get("digikey_url") and row.get("mpn"):
                row["digikey_url"] = self.supplier_service.digikey.build_digikey_search_url(row["mpn"])

            # Save enriched record back to local DB
            self.config.save_component_to_db(row)

        self.recalculate_totals(bom_rows, board_count)
        return bom_rows

    @staticmethod
    def recalculate_totals(bom_rows: List[Dict[str, Any]], board_count: int = 1) -> Dict[str, float]:
        board_count = max(1, int(board_count))
        single_board_total = 0.0
        batch_total = 0.0

        for row in bom_rows:
            qty_1 = int(row.get("qty_per_board") or 1)
            total_qty = qty_1 * board_count
            tiers = row.get("price_tiers") or []
            base_up = float(row.get("unit_price") or row.get("lcsc_price") or row.get("digikey_price") or 0.0)
            up = HybridSupplierService.get_unit_price_for_qty(tiers, base_up, total_qty)
            row["unit_price"] = up
            row["total_qty"] = total_qty
            row["ext_price_1_board"] = round(qty_1 * up, 4)
            row["ext_price_batch"] = round(total_qty * up, 4)

            single_board_total += row["ext_price_1_board"]
            batch_total += row["ext_price_batch"]

        return {
            "single_board_cost": round(single_board_total, 4),
            "batch_total_cost": round(batch_total, 4),
            "unique_parts": len(bom_rows),
            "total_placements_per_board": sum(int(r.get("qty_per_board") or 1) for r in bom_rows),
        }

    def export_bom_csv(
        self,
        bom_rows: List[Dict[str, Any]],
        target_path: str,
        fmt: str = "engineering",
        board_count: int = 1,
    ) -> str:
        """
        fmt: "engineering" | "jlcpcb" | "digikey"
        Writes UTF-8 with BOM (utf-8-sig) so Microsoft Excel opens Turkish characters & symbols cleanly.
        """
        summary = self.recalculate_totals(bom_rows, board_count)

        with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)

            if fmt == "jlcpcb":
                writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
                for r in bom_rows:
                    writer.writerow([
                        r.get("mpn") or r.get("value", ""),
                        r.get("designators", ""),
                        r.get("package") or r.get("footprint", ""),
                        r.get("lcsc_part", ""),
                    ])
                return target_path

            if fmt == "digikey":
                writer.writerow([
                    "DigiKey Part Number",
                    "Manufacturer Part Number",
                    "Manufacturer",
                    "Customer Reference",
                    "Quantity 1",
                    "Target Unit Price ($)",
                ])
                for r in bom_rows:
                    writer.writerow([
                        r.get("digikey_part", ""),
                        r.get("mpn") or r.get("value", ""),
                        r.get("manufacturer", ""),
                        r.get("designators", ""),
                        r.get("total_qty", r.get("qty_per_board", 1)),
                        f'{float(r.get("digikey_price") or r.get("unit_price") or 0.0):.4f}',
                    ])
                return target_path

            # Default: Full Engineering BOM with part numbers, prices, stock, and links
            writer.writerow([
                "Item #",
                "Designators (Ref)",
                "Qty (1 PCB)",
                f"Total Qty ({board_count} PCB)",
                "Value",
                "Footprint / Package",
                "Category",
                "Manufacturer",
                "MPN (Üretici Parça No)",
                "LCSC Part #",
                "DigiKey Part #",
                "Unit Price ($)",
                "Cost / 1 PCB ($)",
                f"Total Cost / {board_count} PCB ($)",
                "LCSC Price ($)",
                "DigiKey Price ($)",
                "Stock",
                "Part Type",
                "Datasheet URL",
                "LCSC URL",
                "DigiKey URL",
                "Description",
            ])

            for i, r in enumerate(bom_rows, start=1):
                up = float(r.get("unit_price") or 0.0)
                lp = float(r.get("lcsc_price") or 0.0)
                dp = float(r.get("digikey_price") or 0.0)
                ext1 = float(r.get("ext_price_1_board") or 0.0)
                extb = float(r.get("ext_price_batch") or 0.0)

                writer.writerow([
                    i,
                    r.get("designators", ""),
                    r.get("qty_per_board", 1),
                    r.get("total_qty", 1),
                    r.get("value", ""),
                    r.get("footprint") or r.get("package", ""),
                    r.get("category", ""),
                    r.get("manufacturer", ""),
                    r.get("mpn", ""),
                    r.get("lcsc_part", ""),
                    r.get("digikey_part", ""),
                    f"{up:.4f}" if up > 0 else "",
                    f"{ext1:.4f}" if up > 0 else "",
                    f"{extb:.4f}" if up > 0 else "",
                    f"{lp:.4f}" if lp > 0 else "",
                    f"{dp:.4f}" if dp > 0 else "",
                    r.get("stock", ""),
                    r.get("part_type", ""),
                    r.get("datasheet", ""),
                    r.get("supplier_url", ""),
                    r.get("digikey_url", ""),
                    r.get("description", ""),
                ])

            writer.writerow([])
            writer.writerow([
                "SUMMARY",
                f"Unique Parts: {summary['unique_parts']}",
                summary["total_placements_per_board"],
                summary["total_placements_per_board"] * board_count,
                "",
                "",
                "",
                "",
                "",
                "",
                "TOTAL COST ($):",
                "",
                f"{summary['single_board_cost']:.4f}",
                f"{summary['batch_total_cost']:.4f}",
            ])

        return target_path
