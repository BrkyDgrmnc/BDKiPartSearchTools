"""
LCSC / JLCPCB & EasyEDA API Client
Fetches parametric data, live tiered pricing, stock, datasheets,
schematic symbol shapes, PCB footprint shapes, and 3D STEP/WRL models.
"""

import re
import json
import requests
from typing import Dict, Any, List, Optional, Tuple
from lcsc_digikey_plugin.config import ConfigManager


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
}


class LcscEasyEdaClient:
    """Client for searching LCSC/JLCPCB parts and pulling EasyEDA CAD models."""

    JLC_SEARCH_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    EASYEDA_COMP_URL = "https://easyeda.com/api/products/{lcsc_id}/components?version=6.4.19.5"
    EASYEDA_STEP_URL = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid_3d}"
    EASYEDA_OBJ_URL = "https://modules.easyeda.com/3dmodel/{uuid_3d}"

    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    @staticmethod
    def normalize_lcsc_id(code: str) -> str:
        code = (code or "").strip().upper()
        if re.match(r"^C\d+$", code):
            return code
        if re.match(r"^\d+$", code):
            return f"C{code}"
        return code

    def search_components(self, query: str, page: int = 1, page_size: int = 25) -> List[Dict[str, Any]]:
        """
        Searches LCSC/JLCPCB catalog by keyword, MPN, or LCSC Part Number (Cxxxx).
        Returns normalized component dictionaries with pricing and stock.
        """
        query = (query or "").strip()
        if not query:
            return []

        results: List[Dict[str, Any]] = []
        try:
            payload = {
                "currentPage": page,
                "pageSize": page_size,
                "keyword": query,
            }
            headers = dict(BROWSER_HEADERS)
            headers["Content-Type"] = "application/json"
            resp = requests.post(
                self.JLC_SEARCH_URL,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                page_info = (data.get("data") or {}).get("componentPageInfo") or {}
                items = page_info.get("list") or []
                for item in items:
                    parsed = self._parse_jlc_item(item)
                    if parsed:
                        results.append(parsed)
        except Exception as e:
            print(f"[LcscEasyEdaClient] Search error: {e}")

        # If user searched an exact LCSC ID like C2040 and search didn't return it first, fetch directly
        norm_id = self.normalize_lcsc_id(query)
        if re.match(r"^C\d+$", norm_id):
            if not any(r.get("lcsc_part") == norm_id for r in results):
                direct = self.fetch_component_summary_from_easyeda(norm_id)
                if direct:
                    results.insert(0, direct)

        return results

    def _parse_jlc_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        lcsc_code = (item.get("componentCode") or "").strip()
        mpn = (item.get("componentModelEn") or "").strip()
        brand = (item.get("componentBrandEn") or "").strip()
        raw_cat = (item.get("componentTypeEn") or "").strip()
        pkg = (item.get("componentSpecificationEn") or "").strip()
        desc = (item.get("describe") or "").strip()
        stock = int(item.get("stockCount") or 0)
        lib_type = (item.get("componentLibraryType") or "").strip()
        part_type = "Basic" if lib_type == "base" else ("Extended" if lib_type else "")

        raw_prices = item.get("componentPrices") or []
        price_tiers = []
        unit_price = 0.0
        for p in raw_prices:
            try:
                start_qty = int(p.get("startNumber") or 1)
                end_qty = int(p.get("endNumber") or -1)
                price_val = float(p.get("productPrice") or 0.0)
                price_tiers.append({
                    "min_qty": start_qty,
                    "max_qty": end_qty,
                    "price": price_val,
                })
            except Exception:
                pass
        price_tiers.sort(key=lambda x: x["min_qty"])
        if price_tiers:
            unit_price = price_tiers[0]["price"]

        datasheet = (item.get("dataManualUrl") or "").strip()
        lcsc_url = (item.get("lcscGoodsUrl") or "").strip()
        if not lcsc_url and lcsc_code:
            lcsc_url = f"https://www.lcsc.com/product-detail/{lcsc_code}.html"

        category = ConfigManager.detect_category(raw_cat, desc, mpn)
        attributes = {}
        for attr in (item.get("attributes") or []):
            k = (attr.get("attribute_name_en") or "").strip()
            v = (attr.get("attribute_value_name") or "").strip()
            if k and v:
                attributes[k] = v

        return {
            "source": "LCSC",
            "lcsc_part": lcsc_code,
            "digikey_part": "",
            "mpn": mpn,
            "manufacturer": brand,
            "category": category,
            "raw_category": raw_cat,
            "package": pkg,
            "description": desc,
            "datasheet": datasheet,
            "stock": stock,
            "lcsc_stock": stock,
            "digikey_stock": 0,
            "unit_price": unit_price,
            "lcsc_price": unit_price,
            "digikey_price": 0.0,
            "price_tiers": price_tiers,
            "part_type": part_type,
            "supplier_url": lcsc_url,
            "digikey_url": "",
            "attributes": attributes,
        }

    def fetch_component_summary_from_easyeda(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        cad = self.fetch_cad_data(lcsc_id)
        if not cad:
            return None
        meta = cad.get("metadata", {})
        mpn = meta.get("mpn") or cad.get("title") or lcsc_id
        raw_cat = meta.get("raw_category", "")
        desc = cad.get("description", "")
        category = ConfigManager.detect_category(raw_cat, desc, mpn)
        return {
            "source": "LCSC/EasyEDA",
            "lcsc_part": meta.get("lcsc_part", lcsc_id),
            "digikey_part": "",
            "mpn": mpn,
            "manufacturer": meta.get("manufacturer", ""),
            "category": category,
            "raw_category": raw_cat,
            "package": meta.get("package", ""),
            "description": desc,
            "datasheet": meta.get("datasheet", ""),
            "stock": meta.get("stock", 0),
            "lcsc_stock": meta.get("stock", 0),
            "digikey_stock": 0,
            "unit_price": meta.get("unit_price", 0.0),
            "lcsc_price": meta.get("unit_price", 0.0),
            "digikey_price": 0.0,
            "price_tiers": [],
            "part_type": meta.get("part_type", ""),
            "supplier_url": meta.get("supplier_url", f"https://www.lcsc.com/product-detail/{lcsc_id}.html"),
            "digikey_url": "",
            "attributes": meta.get("c_para", {}),
            "_cad_data": cad,
        }

    def fetch_cad_data(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches full schematic symbol, footprint, and 3D model info from EasyEDA API.
        """
        lcsc_id = self.normalize_lcsc_id(lcsc_id)
        if not re.match(r"^C\d+$", lcsc_id):
            return None

        url = self.EASYEDA_COMP_URL.format(lcsc_id=lcsc_id)
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=self.timeout)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            result = payload.get("result")
            if not result or not isinstance(result, dict):
                return None

            data_str = result.get("dataStr") or {}
            if isinstance(data_str, str):
                data_str = json.loads(data_str)

            head = data_str.get("head") or {}
            c_para = head.get("c_para") or {}

            pkg_detail = result.get("packageDetail") or {}
            pkg_data_str = pkg_detail.get("dataStr") or {}
            if isinstance(pkg_data_str, str):
                pkg_data_str = json.loads(pkg_data_str)

            pkg_head = pkg_data_str.get("head") or {}
            pkg_shapes = pkg_data_str.get("shape") or []

            # Extract 3D model UUID and transform from SVGNODE in footprint shapes
            model_3d_info = self._extract_3d_info(pkg_shapes, pkg_head)

            lcsc_meta = result.get("lcsc") if isinstance(result.get("lcsc"), dict) else {}
            szlcsc_meta = result.get("szlcsc") if isinstance(result.get("szlcsc"), dict) else {}

            mpn = (
                c_para.get("Manufacturer Part")
                or c_para.get("name")
                or result.get("title")
                or lcsc_id
            )
            manufacturer = (
                c_para.get("Manufacturer")
                or c_para.get("BOM_Manufacturer")
                or ""
            )
            package_name = (
                c_para.get("package")
                or pkg_detail.get("title")
                or ""
            )
            datasheet = (
                c_para.get("link")
                or lcsc_meta.get("url")
                or ""
            )
            prefix = (c_para.get("pre") or "U?").replace("?", "").strip()
            value = c_para.get("Value") or mpn

            try:
                unit_price = float(lcsc_meta.get("price") or szlcsc_meta.get("price") or 0.0)
            except Exception:
                unit_price = 0.0
            try:
                stock = int(lcsc_meta.get("stock") or szlcsc_meta.get("stock") or 0)
            except Exception:
                stock = 0

            tags_raw = result.get("tags") or []
            if isinstance(tags_raw, list):
                raw_cat_str = " ".join(str(t) for t in tags_raw)
            elif isinstance(tags_raw, dict):
                raw_cat_str = " ".join(str(v) for v in tags_raw.values())
            else:
                raw_cat_str = str(tags_raw)

            return {
                "lcsc_part": lcsc_id,
                "title": result.get("title") or mpn,
                "description": result.get("description") or "",
                "symbol_data": data_str,
                "footprint_data": pkg_data_str,
                "footprint_name": self._clean_footprint_name(package_name or f"{mpn}_FP"),
                "model_3d": model_3d_info,
                "metadata": {
                    "lcsc_part": lcsc_id,
                    "mpn": mpn,
                    "manufacturer": manufacturer,
                    "package": package_name,
                    "prefix": prefix,
                    "value": value,
                    "datasheet": datasheet,
                    "unit_price": unit_price,
                    "stock": stock,
                    "part_type": c_para.get("JLCPCB Part Class", ""),
                    "supplier_url": lcsc_meta.get("url") or f"https://www.lcsc.com/product-detail/{lcsc_id}.html",
                    "raw_category": raw_cat_str,
                    "c_para": c_para,
                },
            }
        except Exception as e:
            print(f"[LcscEasyEdaClient] CAD fetch error for {lcsc_id}: {e}")
            return None

    def _extract_3d_info(self, pkg_shapes: List[str], pkg_head: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fp_origin_x = float(pkg_head.get("x") or 0.0)
        fp_origin_y = float(pkg_head.get("y") or 0.0)

        for shape in pkg_shapes:
            if not isinstance(shape, str) or not shape.startswith("SVGNODE~"):
                continue
            try:
                raw_json = shape.split("~", 1)[1]
                node = json.loads(raw_json)
                attrs = node.get("attrs") or {}
                if attrs.get("c_etype") == "outline3D" or attrs.get("uuid"):
                    uuid_3d = attrs.get("uuid", "")
                    title = attrs.get("title") or uuid_3d
                    c_origin = (attrs.get("c_origin") or "0,0").split(",")
                    ox = float(c_origin[0]) if len(c_origin) > 0 and c_origin[0] else fp_origin_x
                    oy = float(c_origin[1]) if len(c_origin) > 1 and c_origin[1] else fp_origin_y
                    z_raw = float(attrs.get("z") or 0.0)

                    # Convert EasyEDA 10mil units to mm (1 unit = 0.254 mm)
                    offset_x_mm = (ox - fp_origin_x) * 0.254
                    offset_y_mm = -(oy - fp_origin_y) * 0.254
                    offset_z_mm = z_raw * 0.254

                    rot_parts = (attrs.get("c_rotation") or "0,0,0").split(",")
                    rx = float(rot_parts[0]) if len(rot_parts) > 0 and rot_parts[0] else 0.0
                    ry = float(rot_parts[1]) if len(rot_parts) > 1 and rot_parts[1] else 0.0
                    rz = float(rot_parts[2]) if len(rot_parts) > 2 and rot_parts[2] else 0.0

                    return {
                        "uuid": uuid_3d,
                        "title": self._sanitize_name(title),
                        "offset_xyz": (round(offset_x_mm, 4), round(offset_y_mm, 4), round(offset_z_mm, 4)),
                        "rotation_xyz": (round(rx, 2), round(ry, 2), round(rz, 2)),
                    }
            except Exception:
                continue
        return None

    def download_step_model(self, uuid_3d: str, target_file: str) -> bool:
        """Downloads binary STEP AP214 3D model from EasyEDA server."""
        if not uuid_3d:
            return False
        url = self.EASYEDA_STEP_URL.format(uuid_3d=uuid_3d)
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 100 and b"ISO-10303-21" in resp.content[:256]:
                with open(target_file, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception as e:
            print(f"[LcscEasyEdaClient] STEP download error ({uuid_3d}): {e}")
        return False

    def download_wrl_model(self, uuid_3d: str, target_file: str) -> bool:
        """Downloads EasyEDA 3D OBJ model and converts it into VRML 2.0 (.wrl) for KiCad."""
        if not uuid_3d:
            return False
        url = self.EASYEDA_OBJ_URL.format(uuid_3d=uuid_3d)
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
            if resp.status_code != 200 or not resp.text:
                return False
            wrl_content = self._convert_easyeda_obj_to_wrl(resp.text)
            if wrl_content:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(wrl_content)
                return True
        except Exception as e:
            print(f"[LcscEasyEdaClient] WRL download error ({uuid_3d}): {e}")
        return False

    @staticmethod
    def _convert_easyeda_obj_to_wrl(obj_text: str) -> str:
        """Converts EasyEDA custom OBJ format into standard VRML 2.0 (.wrl) scaled for KiCad (1 unit = 2.54mm)."""
        vertices: List[Tuple[float, float, float]] = []
        materials: Dict[str, Dict[str, Any]] = {}
        current_mtl = None
        faces_by_mtl: Dict[str, List[List[int]]] = {}

        lines = obj_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    # KiCad WRL uses 1 unit = 0.1 inch = 2.54 mm
                    vx = float(parts[1]) / 2.54
                    vy = float(parts[2]) / 2.54
                    vz = float(parts[3]) / 2.54
                    vertices.append((vx, vy, vz))
            elif line.startswith("newmtl "):
                current_mtl = line.split(" ", 1)[1].strip()
                materials[current_mtl] = {"Kd": (0.8, 0.8, 0.8), "Ka": (0.2, 0.2, 0.2), "Ks": (0.1, 0.1, 0.1), "d": 0.0}
            elif line.startswith("Kd ") and current_mtl in materials:
                p = line.split()
                if len(p) >= 4:
                    materials[current_mtl]["Kd"] = (float(p[1]), float(p[2]), float(p[3]))
            elif line.startswith("usemtl "):
                current_mtl = line.split(" ", 1)[1].strip()
                if current_mtl not in faces_by_mtl:
                    faces_by_mtl[current_mtl] = []
            elif line.startswith("f "):
                parts = line.split()[1:]
                idx_list = []
                for p in parts:
                    v_idx = int(p.split("/")[0]) - 1
                    idx_list.append(v_idx)
                if len(idx_list) >= 3:
                    mtl_key = current_mtl or "default"
                    faces_by_mtl.setdefault(mtl_key, []).append(idx_list)
            i += 1

        if not vertices or not faces_by_mtl:
            return ""

        out = ["#VRML V2.0 utf8", "# Generated by KiCad LCSC & DigiKey Importer"]
        for mtl_name, faces in faces_by_mtl.items():
            mat = materials.get(mtl_name, {"Kd": (0.7, 0.7, 0.7)})
            kd = mat["Kd"]
            coord_points = []
            coord_indices = []
            local_map = {}
            for face in faces:
                mapped_face = []
                for v_idx in face:
                    if 0 <= v_idx < len(vertices):
                        if v_idx not in local_map:
                            local_map[v_idx] = len(coord_points)
                            vx, vy, vz = vertices[v_idx]
                            coord_points.append(f"{vx:.5f} {vy:.5f} {vz:.5f}")
                        mapped_face.append(str(local_map[v_idx]))
                if len(mapped_face) >= 3:
                    coord_indices.append(", ".join(mapped_face) + ", -1")

            if coord_points and coord_indices:
                out.append("Shape {")
                out.append("  appearance Appearance {")
                out.append("    material Material {")
                out.append(f"      diffuseColor {kd[0]:.3f} {kd[1]:.3f} {kd[2]:.3f}")
                out.append("      specularColor 0.2 0.2 0.2")
                out.append("      ambientIntensity 0.2")
                out.append("      shininess 0.2")
                out.append("    }")
                out.append("  }")
                out.append("  geometry IndexedFaceSet {")
                out.append("    ccw TRUE")
                out.append("    solid FALSE")
                out.append("    coord Coordinate { point [ " + ", ".join(coord_points) + " ] }")
                out.append("    coordIndex [ " + ", ".join(coord_indices) + " ]")
                out.append("  }")
                out.append("}")
        return "\n".join(out)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        clean = re.sub(r'[\\/:*?"<>|\s]+', "_", (name or "").strip())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "Component"

    @staticmethod
    def _clean_footprint_name(name: str) -> str:
        s = (name or "").strip()
        s = re.sub(r"_L\d+(?:\.\d+)?-W\d+(?:\.\d+)?.*$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\(\d+(?:\.\d+)?x\d+(?:\.\d+)?(?:mm)?\)", "", s, flags=re.IGNORECASE)
        clean = re.sub(r'[\\/:*?"<>|\s()]+', "_", s)
        clean = re.sub(r"_+", "_", clean).strip("_-")
        return clean or "Footprint"
