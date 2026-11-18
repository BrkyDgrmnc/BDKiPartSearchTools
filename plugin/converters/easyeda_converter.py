"""
Self-Contained EasyEDA to KiCad 10 Converter (Symbols & Footprints)
Converts EasyEDA JSON shapes into:
1. KiCad 8/9/10 S-expression Symbol (.kicad_sym) with full BOM properties
2. KiCad 8/9/10 S-expression Footprint (.kicad_mod) with 3D model alignment
3. Normalized 2D geometry primitives for live wxPython canvas preview
"""

import re
import math
from typing import Dict, Any, List, Tuple, Optional

# 1 EasyEDA unit = 10 mil = 0.254 mm
EE_TO_MM = 0.254

EASYEDA_PIN_TYPES = {
    "0": "unspecified",
    "1": "input",
    "2": "output",
    "3": "bidirectional",
    "4": "power_in",
}

EASYEDA_LAYER_MAP = {
    "1": "F.Cu",
    "2": "B.Cu",
    "3": "F.SilkS",
    "4": "B.SilkS",
    "5": "F.Paste",
    "6": "B.Paste",
    "7": "F.Mask",
    "8": "B.Mask",
    "10": "Edge.Cuts",
    "11": "Edge.Cuts",
    "12": "Cmts.User",
    "13": "F.Fab",
    "14": "B.Fab",
    "15": "Dwgs.User",
    "99": "F.CrtYd",
    "100": "F.Fab",
    "101": "F.Fab",
}


class EasyEDA2KiCadConverter:
    """Converts EasyEDA Symbol and Footprint JSON data into KiCad 10 formats and preview primitives."""

    @staticmethod
    def escape_sexpr_str(val: Any) -> str:
        s = str(val if val is not None else "")
        s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")
        return s

    # -------------------------------------------------------------------------
    # SYMBOL CONVERSION (.kicad_sym)
    # -------------------------------------------------------------------------

    def parse_symbol_geometry(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses EasyEDA symbol shapes into centered millimeter coordinates (snapped to 1.27mm/2.54mm grid)
        for both .kicad_sym generation and 2D GUI preview.
        """
        shapes = symbol_data.get("shape") or []
        head = symbol_data.get("head") or {}

        raw_pins = []
        raw_rects = []
        raw_polylines = []
        raw_Circles = []
        raw_texts = []
        bbox_xs: List[float] = []
        bbox_ys: List[float] = []

        for shape in shapes:
            if not isinstance(shape, str):
                continue
            if shape.startswith("P~"):
                pin = self._parse_ee_pin(shape)
                if pin:
                    raw_pins.append(pin)
                    bbox_xs.append(pin["x"])
                    bbox_ys.append(pin["y"])
            elif shape.startswith("R~"):
                rect = self._parse_ee_rect(shape)
                if rect:
                    raw_rects.append(rect)
                    bbox_xs.extend([rect["x"], rect["x"] + rect["w"]])
                    bbox_ys.extend([rect["y"], rect["y"] + rect["h"]])
            elif shape.startswith("PL~") or shape.startswith("PG~"):
                poly = self._parse_ee_poly(shape)
                if poly:
                    raw_polylines.append(poly)
                    for px, py in poly["pts"]:
                        bbox_xs.append(px)
                        bbox_ys.append(py)
            elif shape.startswith("C~") or shape.startswith("E~"):
                circ = self._parse_ee_circle(shape)
                if circ:
                    raw_Circles.append(circ)
                    bbox_xs.extend([circ["cx"] - circ["r"], circ["cx"] + circ["r"]])
                    bbox_ys.extend([circ["cy"] - circ["r"], circ["cy"] + circ["r"]])
            elif shape.startswith("T~"):
                txt = self._parse_ee_sym_text(shape)
                if txt:
                    raw_texts.append(txt)

        if bbox_xs and bbox_ys:
            mid_x = (min(bbox_xs) + max(bbox_xs)) / 2.0
            mid_y = (min(bbox_ys) + max(bbox_ys)) / 2.0
            # Snap center to 5 EasyEDA units (50 mil = 1.27 mm) so pins stay aligned to KiCad grid
            cx = round(mid_x / 5.0) * 5.0
            cy = round(mid_y / 5.0) * 5.0
        else:
            cx = float(head.get("x") or 0.0)
            cy = float(head.get("y") or 0.0)

        def to_kx(x_ee: float) -> float:
            return round((x_ee - cx) * EE_TO_MM, 4)

        def to_ky(y_ee: float) -> float:
            # In KiCad schematic (.kicad_sym), +Y is UP, whereas in EasyEDA SVG +Y is DOWN
            return round(-(y_ee - cy) * EE_TO_MM, 4)

        pins = []
        for p in raw_pins:
            pins.append({
                "number": p["number"],
                "name": p["name"],
                "elec_type": p["elec_type"],
                "x": to_kx(p["x"]),
                "y": to_ky(p["y"]),
                "angle": p["angle"],
                "length": round(p["length_ee"] * EE_TO_MM, 4),
            })

        rects = []
        for r in raw_rects:
            x1 = to_kx(r["x"])
            y1 = to_ky(r["y"])
            x2 = to_kx(r["x"] + r["w"])
            y2 = to_ky(r["y"] + r["h"])
            rects.append({
                "x1": min(x1, x2),
                "y1": max(y1, y2),
                "x2": max(x1, x2),
                "y2": min(y1, y2),
                "fill": r["fill"],
            })

        polylines = []
        for pl in raw_polylines:
            pts = [(to_kx(px), to_ky(py)) for px, py in pl["pts"]]
            if pl.get("closed") and pts and pts[0] != pts[-1]:
                pts.append(pts[0])
            polylines.append({
                "pts": pts,
                "closed": pl.get("closed", False),
                "fill": pl.get("fill", False),
            })

        circles = []
        for c in raw_Circles:
            circles.append({
                "cx": to_kx(c["cx"]),
                "cy": to_ky(c["cy"]),
                "r": round(c["r"] * EE_TO_MM, 4),
                "fill": c.get("fill", False),
            })

        texts = []
        for t in raw_texts:
            texts.append({
                "text": t["text"],
                "x": to_kx(t["x"]),
                "y": to_ky(t["y"]),
            })

        # Compute bounding box in mm for Reference/Value label placement
        all_kx = [0.0]
        all_ky = [0.0]
        for r in rects:
            all_kx.extend([r["x1"], r["x2"]])
            all_ky.extend([r["y1"], r["y2"]])
        for p in pins:
            all_kx.append(p["x"])
            all_ky.append(p["y"])
        for pl in polylines:
            for px, py in pl["pts"]:
                all_kx.append(px)
                all_ky.append(py)

        return {
            "pins": pins,
            "rects": rects,
            "polylines": polylines,
            "circles": circles,
            "texts": texts,
            "bbox_mm": (min(all_kx), min(all_ky), max(all_kx), max(all_ky)),
        }

    def _parse_ee_pin(self, shape: str) -> Optional[Dict[str, Any]]:
        try:
            segments = shape.split("^^")
            s0 = segments[0].split("~")
            elec_code = s0[2] if len(s0) > 2 else "0"
            pin_num = s0[3] if len(s0) > 3 else "1"
            px = float(s0[4]) if len(s0) > 4 and s0[4] else 0.0
            py = float(s0[5]) if len(s0) > 5 and s0[5] else 0.0
            rot = int(float(s0[6])) if len(s0) > 6 and s0[6] else 0

            # Pin length from SVG path in segment 2 (e.g. "M 525 230 h -10~#880000")
            length_ee = 10.0
            if len(segments) > 2:
                path_str = segments[2].split("~")[0]
                m = re.search(r"[hvHV]\s*([+-]?\d+(?:\.\d+)?)", path_str)
                if m:
                    length_ee = abs(float(m.group(1)))

            pin_name = "~"
            if len(segments) > 3:
                s3 = segments[3].split("~")
                if len(s3) > 4 and s3[4].strip():
                    pin_name = s3[4].strip()

            if len(segments) > 4:
                s4 = segments[4].split("~")
                if len(s4) > 4 and s4[4].strip():
                    pin_num = s4[4].strip()

            # EasyEDA rotation to KiCad pin orientation
            kicad_angle = (180 + rot) % 360

            return {
                "number": pin_num,
                "name": pin_name,
                "elec_type": EASYEDA_PIN_TYPES.get(elec_code, "passive"),
                "x": px,
                "y": py,
                "angle": kicad_angle,
                "length_ee": length_ee,
            }
        except Exception:
            return None

    def _parse_ee_rect(self, shape: str) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            x = float(p[1])
            y = float(p[2])
            w = float(p[5])
            h = float(p[6])
            fill_str = (p[10] if len(p) > 10 else "none").lower()
            return {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "fill": fill_str not in ("none", ""),
            }
        except Exception:
            return None

    def _parse_ee_poly(self, shape: str) -> Optional[Dict[str, Any]]:
        try:
            closed = shape.startswith("PG~")
            p = shape.split("~")
            coords_str = p[1].strip()
            nums = [float(v) for v in re.split(r"[\s,]+", coords_str) if v]
            pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if len(pts) < 2:
                return None
            fill_str = (p[4] if len(p) > 4 else "none").lower()
            return {
                "pts": pts,
                "closed": closed,
                "fill": closed and fill_str not in ("none", ""),
            }
        except Exception:
            return None

    def _parse_ee_circle(self, shape: str) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            cx = float(p[1])
            cy = float(p[2])
            r = float(p[3])
            fill_str = (p[7] if len(p) > 7 else "none").lower()
            return {
                "cx": cx,
                "cy": cy,
                "r": r,
                "fill": fill_str not in ("none", ""),
            }
        except Exception:
            return None

    def _parse_ee_sym_text(self, shape: str) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            if len(p) > 12:
                x = float(p[2])
                y = float(p[3])
                text = p[12].strip()
                if text and text not in ("~", ""):
                    return {"x": x, "y": y, "text": text}
        except Exception:
            pass
        return None

    def generate_kicad_symbol_block(
        self,
        symbol_name: str,
        symbol_data: Dict[str, Any],
        properties: Dict[str, Any],
    ) -> str:
        """
        Generates a single `(symbol "<symbol_name>" ...)` S-expression block
        compatible with KiCad 8, 9, and 10 (.kicad_sym).
        """
        geom = self.parse_symbol_geometry(symbol_data)
        min_x, min_y, max_x, max_y = geom["bbox_mm"]
        ref_y = round(max_y + 2.54, 2)
        val_y = round(min_y - 2.54, 2)

        sym_id = self.escape_sexpr_str(symbol_name)
        ref_prefix = self.escape_sexpr_str(properties.get("Reference", "U"))
        val_str = self.escape_sexpr_str(properties.get("Value", symbol_name))
        fp_str = self.escape_sexpr_str(properties.get("Footprint", ""))
        ds_str = self.escape_sexpr_str(properties.get("Datasheet", ""))
        desc_str = self.escape_sexpr_str(properties.get("Description", ""))

        lines = [
            f'\t(symbol "{sym_id}"',
            "\t\t(exclude_from_sim no)",
            "\t\t(in_bom yes)",
            "\t\t(on_board yes)",
        ]

        # Standard visible properties: Reference & Value
        lines.extend(self._format_sym_property("Reference", ref_prefix, 0, ref_y, hide=False))
        lines.extend(self._format_sym_property("Value", val_str, 0, val_y, hide=False))
        lines.extend(self._format_sym_property("Footprint", fp_str, 0, round(val_y - 2.54, 2), hide=True))
        lines.extend(self._format_sym_property("Datasheet", ds_str, 0, round(val_y - 5.08, 2), hide=True))
        lines.extend(self._format_sym_property("Description", desc_str, 0, 0, hide=True))

        # Custom BOM & Supplier Properties embedded directly in symbol
        custom_fields = [
            ("Manufacturer", properties.get("Manufacturer", "")),
            ("MPN", properties.get("MPN", symbol_name)),
            ("LCSC_Part", properties.get("LCSC_Part", "")),
            ("DigiKey_Part", properties.get("DigiKey_Part", "")),
            ("Category", properties.get("Category", "")),
            ("Package", properties.get("Package", "")),
            ("Unit_Price", properties.get("Unit_Price", "")),
            ("LCSC_Price", properties.get("LCSC_Price", "")),
            ("DigiKey_Price", properties.get("DigiKey_Price", "")),
            ("Stock", properties.get("Stock", "")),
            ("Part_Type", properties.get("Part_Type", "")),
            ("Supplier_URL", properties.get("Supplier_URL", "")),
            ("DigiKey_URL", properties.get("DigiKey_URL", "")),
        ]

        offset_idx = 3
        for k, v in custom_fields:
            v_clean = self.escape_sexpr_str(v)
            y_pos = round(val_y - offset_idx * 2.54, 2)
            lines.extend(self._format_sym_property(k, v_clean, 0, y_pos, hide=True))
            offset_idx += 1

        # Unit 0_1: Graphical body shapes
        lines.append(f'\t\t(symbol "{sym_id}_0_1"')
        if not geom["rects"] and not geom["polylines"] and not geom["circles"]:
            # Fallback box if symbol had no graphical outline
            lines.extend([
                "\t\t\t(rectangle",
                "\t\t\t\t(start -5.08 5.08)",
                "\t\t\t\t(end 5.08 -5.08)",
                "\t\t\t\t(stroke (width 0.254) (type default))",
                "\t\t\t\t(fill (type background))",
                "\t\t\t)",
            ])

        for r in geom["rects"]:
            fill_type = "background" if not r["fill"] else "outline"
            lines.extend([
                "\t\t\t(rectangle",
                f'\t\t\t\t(start {r["x1"]} {r["y1"]})',
                f'\t\t\t\t(end {r["x2"]} {r["y2"]})',
                "\t\t\t\t(stroke (width 0.254) (type default))",
                f"\t\t\t\t(fill (type {fill_type}))",
                "\t\t\t)",
            ])

        for pl in geom["polylines"]:
            pts_str = " ".join(f"(xy {px} {py})" for px, py in pl["pts"])
            fill_type = "outline" if pl["fill"] else "none"
            lines.extend([
                "\t\t\t(polyline",
                f"\t\t\t\t(pts {pts_str})",
                "\t\t\t\t(stroke (width 0.254) (type default))",
                f"\t\t\t\t(fill (type {fill_type}))",
                "\t\t\t)",
            ])

        for c in geom["circles"]:
            fill_type = "outline" if c["fill"] else "none"
            lines.extend([
                "\t\t\t(circle",
                f'\t\t\t\t(center {c["cx"]} {c["cy"]})',
                f'\t\t\t\t(radius {c["r"]})',
                "\t\t\t\t(stroke (width 0.254) (type default))",
                f"\t\t\t\t(fill (type {fill_type}))",
                "\t\t\t)",
            ])
        lines.append("\t\t)")

        # Unit 1_1: Electrical Pins
        lines.append(f'\t\t(symbol "{sym_id}_1_1"')
        for p in geom["pins"]:
            p_name = self.escape_sexpr_str(p["name"] or "~")
            p_num = self.escape_sexpr_str(p["number"] or "1")
            p_type = p["elec_type"]
            lines.extend([
                f"\t\t\t(pin {p_type} line",
                f'\t\t\t\t(at {p["x"]} {p["y"]} {p["angle"]})',
                f'\t\t\t\t(length {p["length"]})',
                f'\t\t\t\t(name "{p_name}" (effects (font (size 1.27 1.27))))',
                f'\t\t\t\t(number "{p_num}" (effects (font (size 1.27 1.27))))',
                "\t\t\t)",
            ])
        lines.append("\t\t)")
        lines.append("\t)")
        return "\n".join(lines)

    @staticmethod
    def _format_sym_property(name: str, value: str, x: float, y: float, hide: bool = True) -> List[str]:
        hide_line = "\t\t\t\t(hide yes)" if hide else ""
        out = [
            f'\t\t(property "{name}" "{value}"',
            f"\t\t\t(at {x} {y} 0)",
            "\t\t\t(effects",
            "\t\t\t\t(font (size 1.27 1.27))",
        ]
        if hide_line:
            out.append(hide_line)
        out.extend([
            "\t\t\t)",
            "\t\t)",
        ])
        return out

    # -------------------------------------------------------------------------
    # FOOTPRINT CONVERSION (.kicad_mod)
    # -------------------------------------------------------------------------

    def parse_footprint_geometry(self, footprint_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses EasyEDA footprint shapes into millimeter coordinates relative to head.(x, y)
        for both .kicad_mod generation and 2D GUI preview.
        """
        shapes = footprint_data.get("shape") or []
        head = footprint_data.get("head") or {}
        ox = float(head.get("x") or 0.0)
        oy = float(head.get("y") or 0.0)

        def to_fx(x_ee: float) -> float:
            # In KiCad PCB (.kicad_mod), +Y is DOWN, matching EasyEDA SVG +Y DOWN!
            return round((x_ee - ox) * EE_TO_MM, 4)

        def to_fy(y_ee: float) -> float:
            return round((y_ee - oy) * EE_TO_MM, 4)

        pads = []
        tracks = []
        circles = []
        holes = []
        regions = []
        bbox_xs = [0.0]
        bbox_ys = [0.0]

        for shape in shapes:
            if not isinstance(shape, str):
                continue
            if shape.startswith("PAD~"):
                pad = self._parse_ee_pad(shape, to_fx, to_fy)
                if pad:
                    pads.append(pad)
                    bbox_xs.extend([pad["x"] - pad["w"] / 2, pad["x"] + pad["w"] / 2])
                    bbox_ys.extend([pad["y"] - pad["h"] / 2, pad["y"] + pad["h"] / 2])
            elif shape.startswith("TRACK~"):
                trk = self._parse_ee_track(shape, to_fx, to_fy)
                if trk:
                    tracks.append(trk)
                    for px, py in trk["pts"]:
                        bbox_xs.append(px)
                        bbox_ys.append(py)
            elif shape.startswith("CIRCLE~"):
                circ = self._parse_ee_fp_circle(shape, to_fx, to_fy)
                if circ:
                    circles.append(circ)
            elif shape.startswith("HOLE~"):
                hole = self._parse_ee_hole(shape, to_fx, to_fy)
                if hole:
                    holes.append(hole)
            elif shape.startswith("SOLIDREGION~"):
                reg = self._parse_ee_solidregion(shape, to_fx, to_fy)
                if reg:
                    regions.append(reg)

        return {
            "pads": pads,
            "tracks": tracks,
            "circles": circles,
            "holes": holes,
            "regions": regions,
            "bbox_mm": (min(bbox_xs), min(bbox_ys), max(bbox_xs), max(bbox_ys)),
        }

    def _parse_ee_pad(self, shape: str, to_fx, to_fy) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            ee_shape = p[1].upper()
            x = to_fx(float(p[2]))
            y = to_fy(float(p[3]))
            w = max(0.05, round(float(p[4]) * EE_TO_MM, 4))
            h = max(0.05, round(float(p[5]) * EE_TO_MM, 4))
            layer_id = p[6]
            number = p[8].strip()
            hole_rad_ee = float(p[9]) if len(p) > 9 and p[9] else 0.0
            rot = float(p[11]) if len(p) > 11 and p[11] else 0.0
            slot_len_ee = float(p[12]) if len(p) > 12 and p[12] else 0.0

            drill_d = round(hole_rad_ee * 2.0 * EE_TO_MM, 4)
            slot_len = round(slot_len_ee * EE_TO_MM, 4)

            if layer_id == "11" or drill_d > 0.0:
                pad_type = "thru_hole"
                layers = '"*.Cu" "*.Mask"'
            elif layer_id == "2":
                pad_type = "smd"
                layers = '"B.Cu" "B.Paste" "B.Mask"'
            else:
                pad_type = "smd"
                layers = '"F.Cu" "F.Paste" "F.Mask"'

            shape_map = {
                "RECT": "rect",
                "OVAL": "oval",
                "ELLIPSE": "circle" if abs(w - h) < 0.02 else "oval",
                "POLYGON": "custom",
            }
            kicad_shape = shape_map.get(ee_shape, "rect")

            poly_pts = []
            if kicad_shape == "custom" and len(p) > 10 and p[10].strip():
                nums = [float(v) for v in re.split(r"[\s,]+", p[10].strip()) if v]
                for i in range(0, len(nums) - 1, 2):
                    poly_pts.append((round(to_fx(nums[i]) - x, 4), round(to_fy(nums[i + 1]) - y, 4)))
                if len(poly_pts) < 3:
                    kicad_shape = "rect"

            return {
                "number": number,
                "type": pad_type,
                "shape": kicad_shape,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "rot": rot,
                "drill": drill_d,
                "slot_len": slot_len,
                "layers": layers,
                "poly_pts": poly_pts,
            }
        except Exception:
            return None

    def _parse_ee_track(self, shape: str, to_fx, to_fy) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            width = max(0.05, round(float(p[1]) * EE_TO_MM, 4))
            layer = EASYEDA_LAYER_MAP.get(p[2], "F.SilkS")
            coords = [float(v) for v in re.split(r"[\s,]+", p[4].strip()) if v]
            pts = [(to_fx(coords[i]), to_fy(coords[i + 1])) for i in range(0, len(coords) - 1, 2)]
            if len(pts) < 2:
                return None
            return {"width": width, "layer": layer, "pts": pts}
        except Exception:
            return None

    def _parse_ee_fp_circle(self, shape: str, to_fx, to_fy) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            cx = to_fx(float(p[1]))
            cy = to_fy(float(p[2]))
            r = max(0.05, round(float(p[3]) * EE_TO_MM, 4))
            width = max(0.05, round(float(p[4]) * EE_TO_MM, 4))
            layer = EASYEDA_LAYER_MAP.get(p[5], "F.SilkS")
            return {"cx": cx, "cy": cy, "r": r, "width": width, "layer": layer}
        except Exception:
            return None

    def _parse_ee_hole(self, shape: str, to_fx, to_fy) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            x = to_fx(float(p[1]))
            y = to_fy(float(p[2]))
            d = max(0.1, round(float(p[3]) * 2.0 * EE_TO_MM, 4))
            return {"x": x, "y": y, "drill": d}
        except Exception:
            return None

    def _parse_ee_solidregion(self, shape: str, to_fx, to_fy) -> Optional[Dict[str, Any]]:
        try:
            p = shape.split("~")
            layer_id = p[1]
            if layer_id in ("99", "100", "101"):
                layer = EASYEDA_LAYER_MAP.get(layer_id, "F.Fab")
            else:
                layer = EASYEDA_LAYER_MAP.get(layer_id, "F.SilkS")
            path_str = p[3]
            tokens = re.findall(r"[MLZmlz]|[-+]?\d*\.\d+|[-+]?\d+", path_str)
            pts = []
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok.upper() in ("M", "L") and i + 2 < len(tokens):
                    try:
                        px = to_fx(float(tokens[i + 1]))
                        py = to_fy(float(tokens[i + 2]))
                        pts.append((px, py))
                        i += 3
                        continue
                    except Exception:
                        pass
                i += 1
            if len(pts) < 3:
                return None
            return {"layer": layer, "pts": pts}
        except Exception:
            return None

    def generate_kicad_footprint(
        self,
        footprint_name: str,
        footprint_data: Dict[str, Any],
        model_3d_paths: List[str] = None,
        model_3d_info: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> str:
        """
        Generates a complete `.kicad_mod` S-expression file compatible with KiCad 8, 9, and 10.
        """
        geom = self.parse_footprint_geometry(footprint_data)
        min_x, min_y, max_x, max_y = geom["bbox_mm"]
        ref_y = round(min_y - 1.5, 2)
        val_y = round(max_y + 1.5, 2)

        fp_id = self.escape_sexpr_str(footprint_name)
        desc_str = self.escape_sexpr_str(description)
        has_tht = any(p["type"] == "thru_hole" for p in geom["pads"])
        attr_type = "through_hole" if has_tht else "smd"

        lines = [
            f'(footprint "{fp_id}"',
            "\t(version 20240108)",
            '\t(generator "kicad_lcsc_digikey_importer")',
            '\t(layer "F.Cu")',
            f'\t(descr "{desc_str}")',
            f"\t(attr {attr_type})",
            f'\t(fp_text reference "REF**" (at 0 {ref_y}) (layer "F.SilkS")',
            "\t\t(effects (font (size 1 1) (thickness 0.15)))",
            "\t)",
            f'\t(fp_text value "{fp_id}" (at 0 {val_y}) (layer "F.Fab")',
            "\t\t(effects (font (size 1 1) (thickness 0.15)))",
            "\t)",
        ]

        # Tracks / Silkscreen / Fab lines
        for trk in geom["tracks"]:
            pts = trk["pts"]
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                lines.append(
                    f'\t(fp_line (start {x1} {y1}) (end {x2} {y2}) '
                    f'(stroke (width {trk["width"]}) (type solid)) (layer "{trk["layer"]}"))'
                )

        # Circles
        for c in geom["circles"]:
            end_x = round(c["cx"] + c["r"], 4)
            lines.append(
                f'\t(fp_circle (center {c["cx"]} {c["cy"]}) (end {end_x} {c["cy"]}) '
                f'(stroke (width {c["width"]}) (type solid)) (fill none) (layer "{c["layer"]}"))'
            )

        # Solid Regions / Polygons
        for reg in geom["regions"]:
            pts_str = " ".join(f"(xy {px} {py})" for px, py in reg["pts"])
            lines.append(
                f'\t(fp_poly (pts {pts_str}) '
                f'(stroke (width 0.1) (type solid)) (fill solid) (layer "{reg["layer"]}"))'
            )

        # Non-plated Mounting Holes
        for h in geom["holes"]:
            d = h["drill"]
            lines.append(
                f'\t(pad "" np_thru_hole circle (at {h["x"]} {h["y"]}) '
                f'(size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))'
            )

        # Pads
        for p in geom["pads"]:
            num = self.escape_sexpr_str(p["number"])
            at_str = f'(at {p["x"]} {p["y"]} {p["rot"]})' if p["rot"] else f'(at {p["x"]} {p["y"]})'
            drill_str = ""
            if p["drill"] > 0:
                if p["slot_len"] > p["drill"]:
                    drill_str = f' (drill oval {p["drill"]} {p["slot_len"]})'
                else:
                    drill_str = f' (drill {p["drill"]})'

            if p["shape"] == "custom" and p["poly_pts"]:
                pts_str = " ".join(f"(xy {px} {py})" for px, py in p["poly_pts"])
                lines.extend([
                    f'\t(pad "{num}" {p["type"]} custom {at_str} (size 0.1 0.1){drill_str} (layers {p["layers"]})',
                    "\t\t(options (clearance outline) (anchor rect))",
                    f"\t\t(primitives (gr_poly (pts {pts_str}) (width 0.1) (fill yes)))",
                    "\t)",
                ])
            else:
                lines.append(
                    f'\t(pad "{num}" {p["type"]} {p["shape"]} {at_str} '
                    f'(size {p["w"]} {p["h"]}){drill_str} (layers {p["layers"]}))'
                )

        # 3D Models (.step / .wrl)
        if model_3d_paths:
            ox, oy, oz = (0.0, 0.0, 0.0)
            rx, ry, rz = (0.0, 0.0, 0.0)
            if model_3d_info:
                ox, oy, oz = model_3d_info.get("offset_xyz", (0.0, 0.0, 0.0))
                rx, ry, rz = model_3d_info.get("rotation_xyz", (0.0, 0.0, 0.0))

            for m_path in model_3d_paths:
                escaped_path = m_path.replace("\\", "/")
                lines.extend([
                    f'\t(model "{escaped_path}"',
                    f"\t\t(offset (xyz {ox} {oy} {oz}))",
                    "\t\t(scale (xyz 1 1 1))",
                    f"\t\t(rotate (xyz {rx} {ry} {rz}))",
                    "\t)",
                ])

        lines.append(")")
        return "\n".join(lines) + "\n"
