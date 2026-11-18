"""
2D Live Preview Canvases for Schematic Symbol & PCB Footprint (wxPython)
Renders EasyEDA/KiCad symbol and footprint geometry directly inside the plugin window.
"""

import wx
from typing import Dict, Any, Optional


class SymbolPreviewCanvas(wx.Panel):
    """Renders a 2D preview of the schematic symbol (body, pins, pin names/numbers)."""

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.geom: Optional[Dict[str, Any]] = None
        self.title: str = "Şematik Sembol Önizleme"
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def set_geometry(self, geom: Optional[Dict[str, Any]], title: str = ""):
        self.geom = geom
        if title:
            self.title = f"Sembol: {title}"
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()
        dc.SetBackground(wx.Brush(wx.Colour(250, 250, 245)))
        dc.Clear()

        # Header title
        dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        dc.SetTextForeground(wx.Colour(60, 60, 60))
        dc.DrawText(self.title, 6, 4)

        if not self.geom:
            dc.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
            dc.SetTextForeground(wx.Colour(140, 140, 140))
            dc.DrawText("Önizleme için listeden bir komponent seçin", 16, h // 2 - 8)
            return

        min_x, min_y, max_x, max_y = self.geom.get("bbox_mm", (-5, -5, 5, 5))
        span_x = max(4.0, (max_x - min_x) + 6.0)
        span_y = max(4.0, (max_y - min_y) + 6.0)
        cx_mm = (min_x + max_x) / 2.0
        cy_mm = (min_y + max_y) / 2.0

        usable_w = max(20, w - 24)
        usable_h = max(20, h - 32)
        scale = min(usable_w / span_x, usable_h / span_y)

        def to_px(x_mm: float, y_mm: float):
            px = int(w / 2.0 + (x_mm - cx_mm) * scale)
            py = int((h + 16) / 2.0 - (y_mm - cy_mm) * scale)
            return px, py

        # Subtle origin crosshair
        ox, oy = to_px(0, 0)
        dc.SetPen(wx.Pen(wx.Colour(225, 225, 220), 1, wx.PENSTYLE_DOT))
        dc.DrawLine(0, oy, w, oy)
        dc.DrawLine(ox, 20, ox, h)

        # Draw rectangles (KiCad symbol yellow fill & maroon outline)
        for r in self.geom.get("rects", []):
            x1, y1 = to_px(r["x1"], r["y1"])
            x2, y2 = to_px(r["x2"], r["y2"])
            left, top = min(x1, x2), min(y1, y2)
            rw, rh = max(2, abs(x2 - x1)), max(2, abs(y2 - y1))
            dc.SetPen(wx.Pen(wx.Colour(132, 0, 0), 2))
            dc.SetBrush(wx.Brush(wx.Colour(255, 255, 194)))
            dc.DrawRectangle(left, top, rw, rh)

        # Draw polylines
        dc.SetPen(wx.Pen(wx.Colour(132, 0, 0), 2))
        for pl in self.geom.get("polylines", []):
            pts = [to_px(px, py) for px, py in pl.get("pts", [])]
            if len(pts) >= 2:
                dc.DrawLines(pts)

        # Draw circles
        for c in self.geom.get("circles", []):
            cx, cy = to_px(c["cx"], c["cy"])
            rad = max(2, int(c["r"] * scale))
            dc.SetPen(wx.Pen(wx.Colour(132, 0, 0), 2))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawCircle(cx, cy, rad)

        # Draw pins
        dc.SetFont(wx.Font(7, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        for p in self.geom.get("pins", []):
            x1, y1 = to_px(p["x"], p["y"])
            ang = p.get("angle", 0)
            length = p.get("length", 2.54)
            dx, dy = 0.0, 0.0
            if ang == 0:
                dx = length
            elif ang == 180:
                dx = -length
            elif ang == 90:
                dy = length
            elif ang == 270:
                dy = -length
            x2, y2 = to_px(p["x"] + dx, p["y"] + dy)

            dc.SetPen(wx.Pen(wx.Colour(132, 0, 0), 2))
            dc.DrawLine(x1, y1, x2, y2)
            dc.SetBrush(wx.Brush(wx.Colour(132, 0, 0)))
            dc.DrawCircle(x1, y1, 2)

            p_name = p.get("name", "")
            if p_name and p_name != "~" and scale > 4.0:
                dc.SetTextForeground(wx.Colour(0, 100, 100))
                dc.DrawText(p_name[:10], x2 + (3 if dx >= 0 else -32), y2 - 6)


class FootprintPreviewCanvas(wx.Panel):
    """Renders a 2D preview of the PCB footprint (SMD/THT pads, silkscreen, fab outline, 3D status)."""

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.geom: Optional[Dict[str, Any]] = None
        self.title: str = "PCB Footprint Önizleme"
        self.has_3d: bool = False
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def set_geometry(self, geom: Optional[Dict[str, Any]], title: str = "", has_3d: bool = False):
        self.geom = geom
        self.has_3d = has_3d
        if title:
            self.title = f"Footprint: {title}"
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()
        dc.SetBackground(wx.Brush(wx.Colour(22, 26, 30)))
        dc.Clear()

        # Header & 3D badge
        dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        dc.SetTextForeground(wx.Colour(220, 220, 220))
        dc.DrawText(self.title, 6, 4)

        badge_text = "3D STEP: Hazır ✓" if self.has_3d else "3D Model: Yok"
        badge_col = wx.Colour(46, 160, 67) if self.has_3d else wx.Colour(140, 100, 40)
        tw, th = dc.GetTextExtent(badge_text)
        dc.SetBrush(wx.Brush(badge_col))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRoundedRectangle(w - tw - 16, 3, tw + 10, th + 4, 3)
        dc.SetTextForeground(wx.Colour(255, 255, 255))
        dc.DrawText(badge_text, w - tw - 11, 5)

        if not self.geom:
            dc.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
            dc.SetTextForeground(wx.Colour(130, 140, 150))
            dc.DrawText("Footprint önizlemesi burada görünecek", 16, h // 2 - 8)
            return

        min_x, min_y, max_x, max_y = self.geom.get("bbox_mm", (-3, -3, 3, 3))
        span_x = max(2.0, (max_x - min_x) + 2.5)
        span_y = max(2.0, (max_y - min_y) + 2.5)
        cx_mm = (min_x + max_x) / 2.0
        cy_mm = (min_y + max_y) / 2.0

        usable_w = max(20, w - 24)
        usable_h = max(20, h - 32)
        scale = min(usable_w / span_x, usable_h / span_y)

        def to_px(x_mm: float, y_mm: float):
            px = int(w / 2.0 + (x_mm - cx_mm) * scale)
            py = int((h + 16) / 2.0 + (y_mm - cy_mm) * scale)
            return px, py

        # Crosshair at origin
        ox, oy = to_px(0, 0)
        dc.SetPen(wx.Pen(wx.Colour(55, 65, 75), 1, wx.PENSTYLE_DOT))
        dc.DrawLine(0, oy, w, oy)
        dc.DrawLine(ox, 22, ox, h)

        # Draw tracks (Silkscreen / Fab / Courtyard)
        for trk in self.geom.get("tracks", []):
            layer = trk.get("layer", "F.SilkS")
            if "Silk" in layer:
                col = wx.Colour(242, 237, 161)
            elif "CrtYd" in layer:
                col = wx.Colour(180, 100, 220)
            else:
                col = wx.Colour(130, 150, 170)
            dc.SetPen(wx.Pen(col, max(1, int(trk.get("width", 0.15) * scale))))
            pts = [to_px(px, py) for px, py in trk.get("pts", [])]
            if len(pts) >= 2:
                dc.DrawLines(pts)

        # Draw circles
        for c in self.geom.get("circles", []):
            cx, cy = to_px(c["cx"], c["cy"])
            rad = max(2, int(c["r"] * scale))
            dc.SetPen(wx.Pen(wx.Colour(242, 237, 161), 1))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawCircle(cx, cy, rad)

        # Draw Pads
        dc.SetFont(wx.Font(7, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        for p in self.geom.get("pads", []):
            px, py = to_px(p["x"], p["y"])
            rot = p.get("rot", 0.0)
            pw = max(3, int(p["w"] * scale))
            ph = max(3, int(p["h"] * scale))
            if int(abs(rot)) in (90, 270):
                pw, ph = ph, pw

            if p.get("type") == "thru_hole":
                dc.SetBrush(wx.Brush(wx.Colour(210, 180, 60)))
                dc.SetPen(wx.Pen(wx.Colour(240, 210, 90), 1))
            else:
                dc.SetBrush(wx.Brush(wx.Colour(200, 52, 52)))
                dc.SetPen(wx.Pen(wx.Colour(230, 80, 80), 1))

            if p.get("shape") == "circle":
                dc.DrawCircle(px, py, max(2, pw // 2))
            elif p.get("shape") == "oval":
                dc.DrawRoundedRectangle(px - pw // 2, py - ph // 2, pw, ph, min(pw, ph) // 2)
            else:
                dc.DrawRectangle(px - pw // 2, py - ph // 2, pw, ph)

            # Drill hole if THT
            if p.get("drill", 0) > 0:
                dr = max(1, int((p["drill"] * scale) / 2))
                dc.SetBrush(wx.Brush(wx.Colour(30, 30, 30)))
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.DrawCircle(px, py, dr)

            # Pad number
            num = str(p.get("number", ""))
            if num and pw >= 10 and ph >= 8:
                dc.SetTextForeground(wx.Colour(255, 255, 255))
                tw, th = dc.GetTextExtent(num)
                dc.DrawText(num, px - tw // 2, py - th // 2)
