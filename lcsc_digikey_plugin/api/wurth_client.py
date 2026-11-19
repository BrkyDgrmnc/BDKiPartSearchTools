"""
Würth Elektronik Official KiCad Library Client
Supports searching and importing symbols (.kicad_sym), footprints (.kicad_mod),
and 3D STEP/WRL models from both local repository clone and GitHub:
https://github.com/WurthElektronik/KiCad-Library
"""

import os
import re
import json
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

from lcsc_digikey_plugin.config import ConfigManager


class WurthClient:
    """Manages searching and resolving Würth Elektronik components, symbols, footprints, and 3D models."""

    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/WurthElektronik/KiCad-Library/main/"

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config
        self.catalog: List[Dict[str, Any]] = []
        self.local_root: Optional[str] = self._detect_local_root()
        self._load_catalog()

    def _detect_local_root(self) -> Optional[str]:
        """Detects if Würth Elektronik library is locally cloned."""
        candidates = []
        if self.config:
            custom = self.config.settings.get("wurth_library_dir", "").strip()
            if custom:
                candidates.append(custom)
        
        env_dirs = [
            os.environ.get("ARI_WE_LIB_DIR", ""),
            os.environ.get("WE_LIB_DIR", ""),
            r"E:\PCB_Workspace\PCB_Library\kicad_wurth_library",
            os.path.expandvars(r"%USERPROFILE%\Documents\KiCad\libraries\kicad_wurth_library"),
        ]
        candidates.extend(env_dirs)

        for c in candidates:
            if c and os.path.isdir(c):
                sym_path = os.path.join(c, "symbols")
                if os.path.isdir(sym_path):
                    return os.path.abspath(c)
        return None

    def _load_catalog(self):
        """Loads pre-indexed catalog from package data/wurth_catalog.json."""
        catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "wurth_catalog.json")
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    self.catalog = json.load(f)
            except Exception as ex:
                print(f"[WurthClient] Error loading catalog: {ex}")

    def search_components(self, query: str, page_size: int = 30) -> List[Dict[str, Any]]:
        """Searches components by MPN, symbol name, value, description, or footprint."""
        query = (query or "").strip().lower()
        if not query:
            return []

        tokens = query.split()
        results: List[Dict[str, Any]] = []

        for item in self.catalog:
            search_str = f"{item.get('mpn', '')} {item.get('sym_name', '')} {item.get('val', '')} {item.get('desc', '')} {item.get('fp', '')}".lower()
            if all(tok in search_str for tok in tokens):
                raw_fp = item.get("fp", "")
                clean_fp = raw_fp.split(":", 1)[-1] if ":" in raw_fp else raw_fp
                results.append({
                    "source": "Würth Elektronik",
                    "mpn": item.get("mpn") or item.get("val") or item.get("sym_name"),
                    "manufacturer": "Wurth Elektronik",
                    "category": item.get("category", "Misc_Components"),
                    "package": clean_fp,
                    "lcsc_part": "",
                    "digikey_part": "",
                    "unit_price": 0.0,
                    "stock": 0,
                    "description": item.get("desc", ""),
                    "datasheet": item.get("ds", ""),
                    "supplier_url": item.get("ds") or "https://www.we-online.com",
                    "_is_wurth": True,
                    "_wurth_item": item,
                })
                if len(results) >= page_size:
                    break

        return results

    def _read_file_text(self, rel_path: str) -> Optional[str]:
        """Reads file from local repository or falls back to GitHub raw URL."""
        rel_clean = rel_path.replace("\\", "/").lstrip("/")
        if self.local_root:
            local_full = os.path.join(self.local_root, rel_clean)
            if os.path.exists(local_full):
                try:
                    with open(local_full, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()
                except Exception:
                    pass

        # Fallback to GitHub raw
        url = self.GITHUB_RAW_BASE + rel_clean
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BDKiPartSearchTools/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as ex:
            print(f"[WurthClient] Failed to fetch {url}: {ex}")
            return None

    def fetch_symbol_sexpr(self, item: Dict[str, Any]) -> Optional[str]:
        """Extracts the exact S-expression symbol block from .kicad_sym file."""
        sym_file = item.get("sym_file", "")
        sym_name = item.get("sym_name", "")
        if not sym_file or not sym_name:
            return None

        content = self._read_file_text(sym_file)
        if not content:
            return None

        start_marker = f'(symbol "{sym_name}"'
        idx = content.find(start_marker)
        if idx == -1:
            return None

        # S-expression parenthesis counter
        depth = 0
        end_idx = -1
        for i in range(idx, len(content)):
            ch = content[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        if end_idx != -1:
            return content[idx:end_idx]
        return None

    def fetch_footprint_sexpr(self, item: Dict[str, Any]) -> Optional[str]:
        """Fetches the complete .kicad_mod footprint content."""
        fp_file = item.get("fp_file", "")
        if not fp_file:
            return None
        return self._read_file_text(fp_file)

    def resolve_3d_models(self, item: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (step_source, wrl_source).
        If local file exists, returns local path. Otherwise returns GitHub raw URL.
        """
        step_rel = item.get("step_file", "").replace("\\", "/").lstrip("/")
        wrl_rel = item.get("wrl_file", "").replace("\\", "/").lstrip("/")

        step_src = None
        wrl_src = None

        if self.local_root and step_rel:
            local_step = os.path.join(self.local_root, step_rel)
            if os.path.exists(local_step):
                step_src = os.path.abspath(local_step)
        if not step_src and step_rel:
            step_src = self.GITHUB_RAW_BASE + step_rel

        if self.local_root and wrl_rel:
            local_wrl = os.path.join(self.local_root, wrl_rel)
            if os.path.exists(local_wrl):
                wrl_src = os.path.abspath(local_wrl)
        if not wrl_src and wrl_rel:
            wrl_src = self.GITHUB_RAW_BASE + wrl_rel

        return step_src, wrl_src

    def parse_kicad_symbol_geometry(self, sym_sexpr: str) -> Dict[str, Any]:
        """Parses symbol primitives (pins, polylines, rects, arcs) into 2D canvas geometry."""
        geom: Dict[str, Any] = {
            "bbox_mm": (-10.0, -10.0, 10.0, 10.0),
            "rects": [],
            "polylines": [],
            "circles": [],
            "pins": [],
        }
        if not sym_sexpr:
            return geom

        all_x: List[float] = []
        all_y: List[float] = []

        # Parse pins: (pin <type> <shape> (at <x> <y> <rot>) (length <len>) ... (name "<name>") (number "<num>"))
        pin_matches = re.finditer(
            r'\(pin\s+\w+\s+\w+\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)\s+\(length\s+([-0-9.]+)\).*?\(name\s+"([^"]*)".*?\(number\s+"([^"]*)"',
            sym_sexpr,
            re.DOTALL,
        )
        for m in pin_matches:
            px = float(m.group(1))
            py = float(m.group(2))
            rot = float(m.group(3) or 0.0)
            plen = float(m.group(4) or 2.54)
            pname = m.group(5)
            pnum = m.group(6)
            geom["pins"].append({
                "x": px,
                "y": py,
                "rot": rot,
                "length": plen,
                "name": pname,
                "num": pnum,
            })
            all_x.extend([px, px + plen])
            all_y.extend([py, py + plen])

        # Parse rectangles: (rectangle (start <x1> <y1>) (end <x2> <y2>)
        rect_matches = re.finditer(r'\(rectangle\s+\(start\s+([-0-9.]+)\s+([-0-9.]+)\)\s+\(end\s+([-0-9.]+)\s+([-0-9.]+)\)', sym_sexpr)
        for m in rect_matches:
            x1, y1 = float(m.group(1)), float(m.group(2))
            x2, y2 = float(m.group(3)), float(m.group(4))
            rx = min(x1, x2)
            ry = min(y1, y2)
            rw = abs(x2 - x1)
            rh = abs(y2 - y1)
            geom["rects"].append({"x": rx, "y": ry, "w": rw, "h": rh, "fill": "none"})
            all_x.extend([x1, x2])
            all_y.extend([y1, y2])

        # Parse polylines: (pts (xy <x> <y>) ...)
        poly_matches = re.finditer(r'\(polyline\s+\(pts\s+([^\)]+)\)', sym_sexpr)
        for pm in poly_matches:
            pts_str = pm.group(1)
            pts: List[Tuple[float, float]] = []
            for xy_m in re.finditer(r'\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)', pts_str):
                xx, yy = float(xy_m.group(1)), float(xy_m.group(2))
                pts.append((xx, yy))
                all_x.append(xx)
                all_y.append(yy)
            if len(pts) >= 2:
                geom["polylines"].append({"pts": pts})

        # Calculate bounding box
        if all_x and all_y:
            min_x, max_x = min(all_x) - 2.0, max(all_x) + 2.0
            min_y, max_y = min(all_y) - 2.0, max(all_y) + 2.0
            geom["bbox_mm"] = (min_x, min_y, max_x, max_y)

        return geom

    def parse_kicad_footprint_geometry(self, fp_sexpr: str) -> Dict[str, Any]:
        """Parses footprint primitives (pads, lines, poly) into 2D canvas geometry."""
        geom: Dict[str, Any] = {
            "bbox_mm": (-5.0, -5.0, 5.0, 5.0),
            "pads": [],
            "tracks": [],
            "circles": [],
            "regions": [],
            "holes": [],
        }
        if not fp_sexpr:
            return geom

        all_x: List[float] = []
        all_y: List[float] = []

        # Parse pads: (pad "<num>" <type> <shape> (at <x> <y> [<rot>]) (size <w> <h>)
        pad_matches = re.finditer(
            r'\(pad\s+"([^"]*)"\s+(\w+)\s+(\w+)\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)\s+\(size\s+([-0-9.]+)\s+([-0-9.]+)\)',
            fp_sexpr,
        )
        for m in pad_matches:
            pnum = m.group(1)
            ptype = m.group(2)
            pshape = m.group(3)
            px = float(m.group(4))
            py = float(m.group(5))
            prot = float(m.group(6) or 0.0)
            pw = float(m.group(7))
            ph = float(m.group(8))

            geom["pads"].append({
                "number": pnum,
                "type": ptype,
                "shape": pshape,
                "x": px,
                "y": py,
                "w": pw,
                "h": ph,
                "rot": prot,
                "drill": 0.0,
            })
            all_x.extend([px - pw / 2.0, px + pw / 2.0])
            all_y.extend([py - ph / 2.0, py + ph / 2.0])

        # Parse fp_line: (fp_line (start <x1> <y1>) (end <x2> <y2>) ... (layer "<layer>")
        line_matches = re.finditer(
            r'\(fp_line\s+\(start\s+([-0-9.]+)\s+([-0-9.]+)\)\s+\(end\s+([-0-9.]+)\s+([-0-9.]+)\).*?\(layer\s+"([^"]+)"',
            fp_sexpr,
        )
        for m in line_matches:
            x1, y1 = float(m.group(1)), float(m.group(2))
            x2, y2 = float(m.group(3)), float(m.group(4))
            layer = m.group(5)
            geom["tracks"].append({
                "layer": layer,
                "width": 0.15,
                "pts": [(x1, y1), (x2, y2)],
            })
            all_x.extend([x1, x2])
            all_y.extend([y1, y2])

        if all_x and all_y:
            min_x, max_x = min(all_x) - 1.0, max(all_x) + 1.0
            min_y, max_y = min(all_y) - 1.0, max(all_y) + 1.0
            geom["bbox_mm"] = (min_x, min_y, max_x, max_y)

        return geom

    def fetch_cad_data(self, part_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resolves complete CAD data (native S-expressions + 3D model sources + 2D preview)."""
        item = part_info.get("_wurth_item")
        if not item:
            return None

        sym_sexpr = self.fetch_symbol_sexpr(item)
        fp_sexpr = self.fetch_footprint_sexpr(item)
        step_src, wrl_src = self.resolve_3d_models(item)

        raw_fp = item.get("fp", "")
        clean_fp = raw_fp.split(":", 1)[-1] if ":" in raw_fp else raw_fp

        sym_geom = self.parse_kicad_symbol_geometry(sym_sexpr or "")
        fp_geom = self.parse_kicad_footprint_geometry(fp_sexpr or "")

        cat = item.get("category", "Misc_Components")
        prefix = ConfigManager.get_reference_prefix(cat)

        return {
            "metadata": {
                "prefix": prefix,
                "manufacturer": "Wurth Elektronik",
                "datasheet": item.get("ds", ""),
                "package": clean_fp,
            },
            "footprint_name": clean_fp,
            "_is_native_kicad": True,
            "_wurth_item": item,
            "symbol_sexpr": sym_sexpr,
            "footprint_sexpr": fp_sexpr,
            "model_3d": {
                "step_source": step_src,
                "wrl_source": wrl_src,
                "uuid": bool(step_src or wrl_src),
            },
            "symbol_data": sym_geom,
            "footprint_data": fp_geom,
        }
