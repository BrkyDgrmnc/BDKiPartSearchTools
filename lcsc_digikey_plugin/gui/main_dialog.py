"""
KiCad 10 LCSC & DigiKey Component Importer & Smart BOM Manager - Main wxPython GUI
"""

import os
import threading
import webbrowser
import wx
from typing import Dict, Any, List, Optional

from lcsc_digikey_plugin.config import ConfigManager, DEFAULT_CATEGORIES
from lcsc_digikey_plugin.api.hybrid_service import HybridSupplierService
from lcsc_digikey_plugin.converters.easyeda_converter import EasyEDA2KiCadConverter
from lcsc_digikey_plugin.library.library_manager import LibraryManager
from lcsc_digikey_plugin.bom.bom_manager import BomManager
from lcsc_digikey_plugin.gui.preview_canvas import SymbolPreviewCanvas, FootprintPreviewCanvas


class BomRowEditDialog(wx.Dialog):
    """Modal dialog for editing a BOM row's MPN, LCSC #, DigiKey #, Manufacturer, and Unit Price."""

    def __init__(self, parent, row_data: Dict[str, Any]):
        super().__init__(parent, title=f"BOM Satırı Düzenle: {row_data.get('designators', '')}", size=(460, 340))
        self.row_data = row_data
        self._build_ui()
        self.CentreOnParent()

    def _build_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(rows=6, cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)

        def add_field(label: str, val: str):
            lbl = wx.StaticText(self, label=label)
            txt = wx.TextCtrl(self, value=str(val or ""))
            grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(txt, 1, wx.EXPAND)
            return txt

        self.txt_mpn = add_field("MPN (Üretici Parça No):", self.row_data.get("mpn", ""))
        self.txt_mfg = add_field("Üretici (Manufacturer):", self.row_data.get("manufacturer", ""))
        self.txt_lcsc = add_field("LCSC Parça No (Cxxxx):", self.row_data.get("lcsc_part", ""))
        self.txt_dk = add_field("DigiKey Parça No:", self.row_data.get("digikey_part", ""))
        self.txt_price = add_field("Birim Fiyat ($):", f"{float(self.row_data.get('unit_price') or 0.0):.4f}")
        self.txt_cat = add_field("Kategori:", self.row_data.get("category", ""))

        vbox.Add(grid, 1, wx.ALL | wx.EXPAND, 14)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(vbox)

    def apply_changes(self):
        self.row_data["mpn"] = self.txt_mpn.GetValue().strip()
        self.row_data["manufacturer"] = self.txt_mfg.GetValue().strip()
        self.row_data["lcsc_part"] = self.txt_lcsc.GetValue().strip()
        self.row_data["digikey_part"] = self.txt_dk.GetValue().strip()
        self.row_data["category"] = self.txt_cat.GetValue().strip()
        try:
            self.row_data["unit_price"] = float(self.txt_price.GetValue().strip() or 0.0)
        except Exception:
            pass


class MainImporterDialog(wx.Dialog):
    """Main multi-tabbed dialog for KiCad 10 LCSC & DigiKey Component Importer & Smart BOM Manager."""

    def __init__(self, parent=None, board=None, project_dir: Optional[str] = None):
        super().__init__(
            parent,
            title="BDPartSearchTools - Komponent Kütüphane ve Akıllı BOM Yöneticisi (by Berkay Değirmenci)",
            size=(1180, 780),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX,
        )
        self.board = board
        self.config = ConfigManager()
        self.project_dir = project_dir or self._detect_project_dir()

        self.supplier_service = HybridSupplierService(self.config)
        self.converter = EasyEDA2KiCadConverter()
        self.library_manager = LibraryManager(self.config, self.supplier_service.lcsc)
        self.bom_manager = BomManager(self.config, self.supplier_service)

        self.search_results: List[Dict[str, Any]] = []
        self.selected_part: Optional[Dict[str, Any]] = None
        self.selected_cad: Optional[Dict[str, Any]] = None
        self.bom_rows: List[Dict[str, Any]] = []
        self._search_seq: int = 0

        self._build_ui()
        self.Centre()

        # Preload BOM if a project/board is open
        if self.board is not None or self.project_dir:
            self._load_bom_from_project()

    def _detect_project_dir(self) -> Optional[str]:
        # 1. From pcbnew board if launched inside PCB Editor
        if self.board is not None:
            try:
                bf = str(self.board.GetFileName() or "")
                if bf:
                    return os.path.dirname(os.path.abspath(bf))
            except Exception:
                pass

        # 2. From Eeschema (Schematic Editor) config & lock files
        try:
            import json
            import glob
            cfg_dir = self.config._get_kicad_config_dir()
            eeschema_path = os.path.join(cfg_dir, "eeschema.json")
            if os.path.exists(eeschema_path):
                with open(eeschema_path, "r", encoding="utf-8") as f:
                    ee_cfg = json.load(f)
                hist = (ee_cfg.get("system") or {}).get("file_history") or []
                # Prefer a schematic directory that currently has an active KiCad .lck file
                for sch_file in hist:
                    if sch_file and os.path.exists(sch_file):
                        d = os.path.dirname(os.path.abspath(sch_file))
                        if glob.glob(os.path.join(d, "~*.lck")) or glob.glob(os.path.join(d, "*.lck")):
                            return d
                # Fallback to most recently opened schematic in Eeschema
                for sch_file in hist:
                    if sch_file and os.path.exists(sch_file):
                        return os.path.dirname(os.path.abspath(sch_file))
        except Exception:
            pass
        return None

    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(self)
        self.tab_search = wx.Panel(self.notebook)
        self.tab_bom = wx.Panel(self.notebook)
        self.tab_settings = wx.Panel(self.notebook)

        self._build_search_tab(self.tab_search)
        self._build_bom_tab(self.tab_bom)
        self._build_settings_tab(self.tab_settings)

        self.notebook.AddPage(self.tab_search, "🔍 1. Komponent Ara ve Kütüphaneye Ekle (LCSC & DigiKey)")
        self.notebook.AddPage(self.tab_bom, "📊 2. Akıllı BOM, Fiyat ve Stok Çıktısı")
        self.notebook.AddPage(self.tab_settings, "⚙️ 3. Kütüphane ve API Ayarları")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 6)

        # Bottom status bar
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_status = wx.StaticText(
            self,
            label="Hazır. LCSC parça kodu (örn. C2040), DigiKey kodu veya MPN (örn. STM32F103C8T6, PESD2CAN) aratabilirsiniz.",
        )
        self.gauge = wx.Gauge(self, range=100, size=(180, 16))
        self.gauge.Hide()
        btn_close = wx.Button(self, wx.ID_CLOSE, "Kapat")
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK) if self.IsModal() else self.Close())

        status_sizer.Add(self.lbl_status, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        status_sizer.Add(self.gauge, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        status_sizer.Add(btn_close, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        main_sizer.Add(status_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 4)
        self.SetSizer(main_sizer)

    # =========================================================================
    # TAB 1: SEARCH & IMPORT TO KICAD LIBRARY
    # =========================================================================

    def _build_search_tab(self, panel: wx.Panel):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Top Search Bar
        search_box = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "LCSC / EasyEDA & DigiKey Komponent Arama")
        self.txt_query = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER, size=(340, -1))
        self.txt_query.SetHint("Örn: C2040, RP2040, STM32G431, 10k 0402, PESD2CAN...")
        self.txt_query.Bind(wx.EVT_TEXT_ENTER, self._on_search_clicked)

        self.choice_source = wx.Choice(
            panel,
            choices=[
                "LCSC + DigiKey (Hibrit)",
                "Sadece LCSC / EasyEDA",
                "Sadece DigiKey API",
            ],
        )
        self.choice_source.SetSelection(0)

        self.btn_search = wx.Button(panel, label="🔍 Ara")
        self.btn_search.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_search.Bind(wx.EVT_BUTTON, self._on_search_clicked)
        self.btn_search.SetDefault()

        self.btn_clear_search = wx.Button(panel, label="✖ Temizle", size=(76, -1))
        self.btn_clear_search.Bind(wx.EVT_BUTTON, self._on_clear_search_clicked)

        search_box.Add(wx.StaticText(panel, label="Arama / Parça No:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        search_box.Add(self.txt_query, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        search_box.Add(self.btn_clear_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        search_box.Add(wx.StaticText(panel, label="Kaynak:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        search_box.Add(self.choice_source, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        search_box.Add(self.btn_search, 0, wx.ALIGN_CENTER_VERTICAL)

        vbox.Add(search_box, 0, wx.EXPAND | wx.ALL, 6)

        # Results ListCtrl
        self.list_results = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        cols = [
            ("Kaynak", 95),
            ("MPN (Parça No)", 155),
            ("Üretici", 120),
            ("Kategori", 130),
            ("Paket / Footprint", 120),
            ("LCSC #", 85),
            ("DigiKey #", 115),
            ("Birim Fiyat ($)", 95),
            ("Stok", 80),
            ("Açıklama", 240),
        ]
        for idx, (col_title, width) in enumerate(cols):
            self.list_results.InsertColumn(idx, col_title, width=width)
        self.list_results.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_selected)
        vbox.Add(self.list_results, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        # Bottom Split: Left = 2D Canvases (Symbol + Footprint), Right = Editable Import & BOM Properties
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 2D Preview Canvases
        preview_box = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "Canlı CAD Önizleme (Şematik Sembol & PCB Footprint)")
        self.sym_canvas = SymbolPreviewCanvas(panel)
        self.fp_canvas = FootprintPreviewCanvas(panel)
        self.sym_canvas.SetMinSize((260, 230))
        self.fp_canvas.SetMinSize((260, 230))
        preview_box.Add(self.sym_canvas, 1, wx.EXPAND | wx.ALL, 3)
        preview_box.Add(self.fp_canvas, 1, wx.EXPAND | wx.ALL, 3)
        bottom_sizer.Add(preview_box, 5, wx.EXPAND | wx.RIGHT, 6)

        # Import Details & Custom BOM Fields Box
        import_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Kütüphane ve BOM Alanları (İçe Aktarmadan Önce Düzenlenebilir)")
        fg = wx.FlexGridSizer(rows=5, cols=4, vgap=6, hgap=8)
        fg.AddGrowableCol(1, 1)
        fg.AddGrowableCol(3, 1)

        self.choice_category = wx.Choice(panel, choices=DEFAULT_CATEGORIES)
        self.choice_category.SetSelection(0)
        self.choice_category.Bind(wx.EVT_CHOICE, self._on_category_changed)

        self.txt_target_lib = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.txt_sym_name = wx.TextCtrl(panel)
        self.txt_ref_prefix = wx.TextCtrl(panel, value="U")
        self.txt_fp_name = wx.TextCtrl(panel)
        self.txt_pkg = wx.TextCtrl(panel)
        self.txt_lcsc_code = wx.TextCtrl(panel)
        self.txt_dk_code = wx.TextCtrl(panel)
        self.txt_unit_price = wx.TextCtrl(panel)
        self.txt_mfg = wx.TextCtrl(panel)

        def add_fg_pair(lbl1, ctrl1, lbl2, ctrl2):
            fg.Add(wx.StaticText(panel, label=lbl1), 0, wx.ALIGN_CENTER_VERTICAL)
            fg.Add(ctrl1, 1, wx.EXPAND)
            fg.Add(wx.StaticText(panel, label=lbl2), 0, wx.ALIGN_CENTER_VERTICAL)
            fg.Add(ctrl2, 1, wx.EXPAND)

        add_fg_pair("Kategori:", self.choice_category, "Hedef Kütüphane:", self.txt_target_lib)
        add_fg_pair("Sembol Adı (MPN):", self.txt_sym_name, "Ref Prefix:", self.txt_ref_prefix)
        add_fg_pair("Footprint Adı:", self.txt_fp_name, "Paket:", self.txt_pkg)
        add_fg_pair("LCSC Parça No:", self.txt_lcsc_code, "DigiKey Parça No:", self.txt_dk_code)
        add_fg_pair("Birim Fiyat ($):", self.txt_unit_price, "Üretici:", self.txt_mfg)

        import_box.Add(fg, 0, wx.EXPAND | wx.ALL, 4)

        # Checkboxes for what to import
        chk_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_step = wx.CheckBox(panel, label="3D STEP Modeli (.step)")
        self.chk_wrl = wx.CheckBox(panel, label="3D WRL Modeli (.wrl)")
        self.chk_step.SetValue(bool(self.config.settings.get("download_3d_step", True)))
        self.chk_wrl.SetValue(bool(self.config.settings.get("download_3d_wrl", False)))
        chk_sizer.Add(self.chk_step, 0, wx.RIGHT, 12)
        chk_sizer.Add(self.chk_wrl, 0, wx.RIGHT, 12)
        import_box.Add(chk_sizer, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 4)

        # Action Buttons
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_import = wx.Button(panel, label="📥 KiCad Kütüphanesine İçe Aktar (Sembol + Footprint + 3D)")
        self.btn_import.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_import.SetBackgroundColour(wx.Colour(38, 125, 62))
        self.btn_import.SetForegroundColour(wx.Colour(255, 255, 255))
        self.btn_import.Enable(False)
        self.btn_import.Bind(wx.EVT_BUTTON, self._on_import_clicked)

        self.btn_datasheet = wx.Button(panel, label="📄 Datasheet")
        self.btn_datasheet.Enable(False)
        self.btn_datasheet.Bind(wx.EVT_BUTTON, self._on_open_datasheet)

        self.btn_web = wx.Button(panel, label="🌐 LCSC / DigiKey Sayfası")
        self.btn_web.Enable(False)
        self.btn_web.Bind(wx.EVT_BUTTON, self._on_open_supplier_url)

        btn_row.Add(self.btn_import, 1, wx.EXPAND | wx.RIGHT, 6)
        btn_row.Add(self.btn_datasheet, 0, wx.RIGHT, 4)
        btn_row.Add(self.btn_web, 0)
        import_box.Add(btn_row, 0, wx.EXPAND | wx.ALL, 4)

        bottom_sizer.Add(import_box, 6, wx.EXPAND)
        vbox.Add(bottom_sizer, 0, wx.EXPAND | wx.ALL, 6)

        self._update_target_lib_label()
        panel.SetSizer(vbox)

    def _on_category_changed(self, event):
        cat = self.choice_category.GetStringSelection()
        self.txt_ref_prefix.SetValue(ConfigManager.get_reference_prefix(cat))
        self._update_target_lib_label()

    def _update_target_lib_label(self):
        cat = self.choice_category.GetStringSelection() or "Misc_Components"
        lib_name = self.library_manager.get_library_name_for_category(cat)
        self.txt_target_lib.SetValue(f"{lib_name} (.kicad_sym & .pretty)")

    def _set_busy(self, busy: bool, message: str = ""):
        if message:
            self.lbl_status.SetLabel(message)
        if busy:
            self.gauge.Show()
            self.gauge.Pulse()
        else:
            self.gauge.Hide()
        self.btn_search.Enable(True)
        self.Layout()

    def _on_clear_search_clicked(self, event):
        self.txt_query.SetValue("")
        self.txt_query.SetFocus()

    def _on_search_clicked(self, event):
        query = self.txt_query.GetValue().strip()
        if not query:
            wx.MessageBox("Lütfen aramak istediğiniz parça numarasını veya anahtar kelimeyi girin.", "Uyarı", wx.OK | wx.ICON_INFORMATION)
            return

        sel_idx = self.choice_source.GetSelection()
        mode = "hybrid" if sel_idx == 0 else ("lcsc" if sel_idx == 1 else "digikey")

        if mode == "digikey" and not self.supplier_service.digikey.is_configured:
            wx.MessageBox(
                "Sadece DigiKey araması seçtiniz ancak DigiKey API anahtarları henüz girilmemiş.\n"
                "3. Sekmeden (Ayarlar) DigiKey Client ID & Secret girebilir veya 'LCSC + DigiKey (Hibrit)' modunu kullanabilirsiniz.",
                "DigiKey API Bilgisi",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self._search_seq += 1
        current_seq = self._search_seq
        self.selected_part = None
        self.selected_cad = None
        self.btn_import.Enable(False)
        self.sym_canvas.set_geometry(None, "Aranıyor...")
        self.fp_canvas.set_geometry(None, "Aranıyor...", False)

        self._set_busy(True, f"'{query}' aranıyor (LCSC / EasyEDA & DigiKey)...")
        self.list_results.DeleteAllItems()
        self.search_results = []

        def worker():
            try:
                results = self.supplier_service.search(query, mode=mode)
            except Exception as ex:
                print(f"[MainImporterDialog] Search thread error: {ex}")
                results = []
            wx.CallAfter(self._on_search_finished, results, query, current_seq)

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_finished(self, results: List[Dict[str, Any]], query: str, seq: int = 0):
        if seq and seq != self._search_seq:
            return
        try:
            self.search_results = results or []
            self.list_results.DeleteAllItems()

            for i, item in enumerate(self.search_results):
                idx = self.list_results.InsertItem(i, str(item.get("source", "")))
                self.list_results.SetItem(idx, 1, str(item.get("mpn", "")))
                self.list_results.SetItem(idx, 2, str(item.get("manufacturer", "")))
                self.list_results.SetItem(idx, 3, str(item.get("category", "")))
                self.list_results.SetItem(idx, 4, str(item.get("package", "")))
                self.list_results.SetItem(idx, 5, str(item.get("lcsc_part", "")))
                self.list_results.SetItem(idx, 6, str(item.get("digikey_part", "")))
                try:
                    up = float(item.get("unit_price") or 0.0)
                except Exception:
                    up = 0.0
                self.list_results.SetItem(idx, 7, f"${up:.4f}" if up > 0 else "-")
                self.list_results.SetItem(idx, 8, str(item.get("stock", 0)))
                self.list_results.SetItem(idx, 9, str(item.get("description", "")))

            self._set_busy(False, f"'{query}' için {len(self.search_results)} sonuç bulundu.")
            if self.search_results:
                self.list_results.Select(0)
            else:
                self.sym_canvas.set_geometry(None, "Sonuç Yok")
                self.fp_canvas.set_geometry(None, "Sonuç Yok", False)
        except Exception as ex:
            self._set_busy(False, f"Arama sonuçları işlenirken hata: {ex}")

    def _on_result_selected(self, event):
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.search_results):
            return

        part = self.search_results[idx]
        self.selected_part = part
        self.selected_cad = None

        # Populate editable fields immediately
        cat = part.get("category") or "Misc_Components"
        if cat in DEFAULT_CATEGORIES:
            self.choice_category.SetStringSelection(cat)
        self._update_target_lib_label()

        self.txt_sym_name.SetValue(str(part.get("mpn") or part.get("lcsc_part") or ""))
        self.txt_ref_prefix.SetValue(ConfigManager.get_reference_prefix(cat))
        self.txt_fp_name.SetValue(str(part.get("package") or ""))
        self.txt_pkg.SetValue(str(part.get("package") or ""))
        self.txt_lcsc_code.SetValue(str(part.get("lcsc_part") or ""))
        self.txt_dk_code.SetValue(str(part.get("digikey_part") or ""))
        try:
            up = float(part.get("unit_price") or 0.0)
        except Exception:
            up = 0.0
        self.txt_unit_price.SetValue(f"{up:.4f}" if up > 0 else "")
        self.txt_mfg.SetValue(str(part.get("manufacturer") or ""))

        self.btn_datasheet.Enable(bool(part.get("datasheet")))
        self.btn_web.Enable(bool(part.get("supplier_url") or part.get("digikey_url")))
        self.btn_import.Enable(False)

        self._set_busy(True, f"{part.get('mpn')} için Şematik Sembol, Footprint ve 3D model verisi çekiliyor...")

        def worker():
            try:
                cad = self.supplier_service.resolve_cad_for_part(part)
            except Exception as ex:
                print(f"[MainImporterDialog] CAD resolve error: {ex}")
                cad = None
            wx.CallAfter(self._on_cad_loaded, part, cad)

        threading.Thread(target=worker, daemon=True).start()

    def _on_cad_loaded(self, part: Dict[str, Any], cad: Optional[Dict[str, Any]]):
        if part is not self.selected_part:
            return
        try:
            self.selected_cad = cad

            if not cad:
                self.sym_canvas.set_geometry(None, "CAD Bulunamadı")
                self.fp_canvas.set_geometry(None, "CAD Bulunamadı", False)
                self._set_busy(False, f"{part.get('mpn')} için EasyEDA/LCSC CAD modeli bulunamadı.")
                return

            meta = cad.get("metadata", {})
            if meta.get("prefix"):
                self.txt_ref_prefix.SetValue(meta["prefix"])
            if cad.get("footprint_name"):
                self.txt_fp_name.SetValue(cad["footprint_name"])
            if not self.txt_lcsc_code.GetValue().strip() and cad.get("lcsc_part"):
                self.txt_lcsc_code.SetValue(cad["lcsc_part"])
            if not self.txt_mfg.GetValue().strip() and meta.get("manufacturer"):
                self.txt_mfg.SetValue(meta["manufacturer"])

            sym_geom = self.converter.parse_symbol_geometry(cad.get("symbol_data") or {})
            fp_geom = self.converter.parse_footprint_geometry(cad.get("footprint_data") or {})
            has_3d = bool(cad.get("model_3d") and cad["model_3d"].get("uuid"))

            self.sym_canvas.set_geometry(sym_geom, part.get("mpn", ""))
            self.fp_canvas.set_geometry(fp_geom, cad.get("footprint_name", ""), has_3d=has_3d)
            self.btn_import.Enable(True)
            self.btn_datasheet.Enable(bool(part.get("datasheet") or meta.get("datasheet")))

            self._set_busy(
                False,
                f"CAD hazır: {len(sym_geom.get('pins', []))} pin sembol, {len(fp_geom.get('pads', []))} pad footprint"
                + (", 3D STEP modeli mevcut." if has_3d else "."),
            )
        except Exception as ex:
            self._set_busy(False, f"CAD önizleme hatası: {ex}")

    def _on_import_clicked(self, event):
        if not self.selected_part or not self.selected_cad:
            return

        # Sync user edits from UI controls into part_info
        part_to_import = dict(self.selected_part)
        part_to_import["category"] = self.choice_category.GetStringSelection() or "Misc_Components"
        part_to_import["mpn"] = self.txt_sym_name.GetValue().strip() or part_to_import.get("mpn", "Component")
        part_to_import["reference_prefix"] = self.txt_ref_prefix.GetValue().strip() or "U"
        part_to_import["footprint_name"] = self.txt_fp_name.GetValue().strip()
        part_to_import["package"] = self.txt_pkg.GetValue().strip()
        part_to_import["lcsc_part"] = self.txt_lcsc_code.GetValue().strip()
        part_to_import["digikey_part"] = self.txt_dk_code.GetValue().strip()
        part_to_import["manufacturer"] = self.txt_mfg.GetValue().strip()
        try:
            up_val = float(self.txt_unit_price.GetValue().strip() or 0.0)
            part_to_import["unit_price"] = up_val
        except Exception:
            pass

        self.config.settings["download_3d_step"] = self.chk_step.GetValue()
        self.config.settings["download_3d_wrl"] = self.chk_wrl.GetValue()

        cad_data = self.selected_cad
        self._set_busy(True, f"'{part_to_import['mpn']}' kütüphaneye aktarılıyor ve 3D model indiriliyor...")
        self.btn_import.Enable(False)

        def worker():
            try:
                res = self.library_manager.import_component(
                    part_info=part_to_import,
                    cad_data=cad_data,
                    project_dir=self.project_dir,
                )
                wx.CallAfter(self._on_import_completed, res, None)
            except Exception as ex:
                wx.CallAfter(self._on_import_completed, None, str(ex))

        threading.Thread(target=worker, daemon=True).start()

    def _on_import_completed(self, result: Optional[Dict[str, Any]], error: Optional[str]):
        self.btn_import.Enable(True)
        if error or not result:
            self._set_busy(False, f"Hata: {error}")
            wx.MessageBox(f"İçe aktarma sırasında hata oluştu:\n{error}", "Hata", wx.OK | wx.ICON_ERROR)
            return

        sym_ref = result.get("symbol_ref", "")
        fp_ref = result.get("footprint_ref", "")
        d3d = result.get("downloaded_3d_files") or []
        self._set_busy(False, f"Başarıyla eklendi: Sembol [{sym_ref}] | Footprint [{fp_ref}]")

        msg_lines = [
            f"✅ Komponent KiCad 10 kütüphanenize başarıyla eklendi!\n",
            f"• Kategori Kütüphanesi: {result.get('lib_name')}",
            f"• Şematik Sembolü: {sym_ref}",
            f"• PCB Footprint: {fp_ref}",
            f"• Sembol Dosyası: {result.get('sym_file_path')}",
            f"• Footprint Dosyası: {result.get('fp_file_path')}",
            f"• İndirilen 3D Modeller ({len(d3d)} adet): {', '.join(os.path.basename(p) for p in d3d) if d3d else 'Yok'}",
            "",
            "💡 BOM Alanları (MPN, LCSC_Part, DigiKey_Part, Unit_Price, Stock, Datasheet, Supplier_URL) sembolün içine otomatik gömüldü!",
            "Şematik Editöründe (Eeschema) 'A' tuşuna basarak doğrudan şematiğinize ekleyebilirsiniz.",
        ]
        wx.MessageBox("\n".join(msg_lines), "Kütüphaneye Eklendi", wx.OK | wx.ICON_INFORMATION)

    def _on_open_datasheet(self, event):
        if not self.selected_part:
            return
        url = self.selected_part.get("datasheet") or ((self.selected_cad or {}).get("metadata") or {}).get("datasheet")
        if url:
            webbrowser.open(url)

    def _on_open_supplier_url(self, event):
        if not self.selected_part:
            return
        url = self.selected_part.get("supplier_url") or self.selected_part.get("digikey_url")
        if url:
            webbrowser.open(url)

    # =========================================================================
    # TAB 2: SMART BOM, LIVE PRICE & STOCK MANAGER
    # =========================================================================

    def _build_bom_tab(self, panel: wx.Panel):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Top Controls
        top_bar = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "Proje BOM Kaynağı ve Canlı Fiyat/Stok Güncelleme")

        btn_reload = wx.Button(panel, label="🔄 Aktif Projeden Yükle (Şematik + PCB)")
        btn_reload.Bind(wx.EVT_BUTTON, lambda e: self._load_bom_from_project())

        btn_pick_dir = wx.Button(panel, label="📂 Proje Klasörü Seç...")
        btn_pick_dir.Bind(wx.EVT_BUTTON, self._on_pick_project_dir)

        self.spin_boards = wx.SpinCtrl(panel, value="1", min=1, max=100000, size=(75, -1))
        self.spin_boards.Bind(wx.EVT_SPINCTRL, lambda e: self._refresh_bom_table_view())

        self.btn_live_price = wx.Button(panel, label="⚡ Canlı Fiyat, Stok ve Parça Numaralarını Çek (LCSC / DigiKey)")
        self.btn_live_price.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_live_price.SetBackgroundColour(wx.Colour(0, 102, 180))
        self.btn_live_price.SetForegroundColour(wx.Colour(255, 255, 255))
        self.btn_live_price.Bind(wx.EVT_BUTTON, self._on_refresh_live_bom_pricing)

        top_bar.Add(btn_reload, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        top_bar.Add(btn_pick_dir, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        top_bar.Add(wx.StaticText(panel, label="Üretilecek Kart Adedi (PCB Sayısı):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        top_bar.Add(self.spin_boards, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        top_bar.Add(self.btn_live_price, 1, wx.ALIGN_CENTER_VERTICAL)

        vbox.Add(top_bar, 0, wx.EXPAND | wx.ALL, 6)

        # BOM Table
        self.list_bom = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        bom_cols = [
            ("#", 38),
            ("Designators (Ref)", 130),
            ("Adet (1 PCB)", 85),
            ("Toplam Adet", 85),
            ("Value", 110),
            ("Paket / Footprint", 125),
            ("Üretici", 110),
            ("MPN (Parça No)", 145),
            ("LCSC #", 85),
            ("DigiKey #", 115),
            ("Birim Fiyat ($)", 95),
            ("1 PCB Tutarı ($)", 105),
            ("Toplam Tutar ($)", 110),
            ("Stok", 80),
            ("Kategori", 120),
        ]
        for idx, (col_title, width) in enumerate(bom_cols):
            self.list_bom.InsertColumn(idx, col_title, width=width)
        self.list_bom.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_bom_row_double_clicked)

        vbox.Add(self.list_bom, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        # Summary & Export Bar
        bottom_bar = wx.StaticBoxSizer(wx.HORIZONTAL, panel, "Maliyet Özeti ve BOM Dışa Aktarma (Çift tıklayarak satır düzenleyebilirsiniz)")
        self.lbl_bom_summary = wx.StaticText(
            panel,
            label="Toplam: 0 Benzersiz Parça | 1 PCB Maliyeti: $0.0000 | Toplam Parti Maliyeti: $0.0000",
        )
        self.lbl_bom_summary.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        self.choice_bom_fmt = wx.Choice(
            panel,
            choices=[
                "Genel Mühendislik BOM (MPN, LCSC #, DigiKey #, Fiyat, Stok, Linkler)",
                "JLCPCB / LCSC PCBA (Dizgi) Uyumlu BOM CSV",
                "DigiKey Toplu Sipariş (Bulk Upload) Uyumlu CSV",
            ],
        )
        self.choice_bom_fmt.SetSelection(0)

        btn_export_bom = wx.Button(panel, label="💾 BOM CSV Olarak Dışa Aktar...")
        btn_export_bom.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        btn_export_bom.Bind(wx.EVT_BUTTON, self._on_export_bom_clicked)

        bottom_bar.Add(self.lbl_bom_summary, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        bottom_bar.Add(wx.StaticText(panel, label="Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        bottom_bar.Add(self.choice_bom_fmt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bottom_bar.Add(btn_export_bom, 0, wx.ALIGN_CENTER_VERTICAL)

        vbox.Add(bottom_bar, 0, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(vbox)

    def _load_bom_from_project(self):
        self.bom_rows = self.bom_manager.extract_project_bom(board=self.board, project_dir=self.project_dir)
        self._refresh_bom_table_view()
        src_info = self.project_dir or ("Aktif PCB" if self.board else "Proje seçilmedi")
        self.lbl_status.SetLabel(f"BOM yüklendi ({len(self.bom_rows)} kalem) — Kaynak: {src_info}")

    def _on_pick_project_dir(self, event):
        dlg = wx.DirDialog(self, "KiCad Proje Klasörünü Seçin (.kicad_sch / .kicad_pcb içeren klasör)", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.project_dir = dlg.GetPath()
            self._load_bom_from_project()
        dlg.Destroy()

    def _refresh_bom_table_view(self):
        board_count = max(1, int(self.spin_boards.GetValue() or 1))
        summary = self.bom_manager.recalculate_totals(self.bom_rows, board_count)

        self.list_bom.DeleteAllItems()
        for i, r in enumerate(self.bom_rows):
            idx = self.list_bom.InsertItem(i, str(i + 1))
            self.list_bom.SetItem(idx, 1, str(r.get("designators", "")))
            self.list_bom.SetItem(idx, 2, str(r.get("qty_per_board", 1)))
            self.list_bom.SetItem(idx, 3, str(r.get("total_qty", 1)))
            self.list_bom.SetItem(idx, 4, str(r.get("value", "")))
            self.list_bom.SetItem(idx, 5, str(r.get("footprint") or r.get("package", "")))
            self.list_bom.SetItem(idx, 6, str(r.get("manufacturer", "")))
            self.list_bom.SetItem(idx, 7, str(r.get("mpn", "")))
            self.list_bom.SetItem(idx, 8, str(r.get("lcsc_part", "")))
            self.list_bom.SetItem(idx, 9, str(r.get("digikey_part", "")))

            up = float(r.get("unit_price") or 0.0)
            ext1 = float(r.get("ext_price_1_board") or 0.0)
            extb = float(r.get("ext_price_batch") or 0.0)

            self.list_bom.SetItem(idx, 10, f"${up:.4f}" if up > 0 else "-")
            self.list_bom.SetItem(idx, 11, f"${ext1:.4f}" if up > 0 else "-")
            self.list_bom.SetItem(idx, 12, f"${extb:.4f}" if up > 0 else "-")
            self.list_bom.SetItem(idx, 13, str(r.get("stock", "")))
            self.list_bom.SetItem(idx, 14, str(r.get("category", "")))

        self.lbl_bom_summary.SetLabel(
            f"Toplam: {summary['unique_parts']} Benzersiz Kalem ({summary['total_placements_per_board']} Dizgi/Kart) | "
            f"1 PCB Maliyeti: ${summary['single_board_cost']:.4f} | "
            f"{board_count} PCB Toplam Maliyet: ${summary['batch_total_cost']:.4f}"
        )

    def _on_bom_row_double_clicked(self, event):
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.bom_rows):
            return
        row = self.bom_rows[idx]
        dlg = BomRowEditDialog(self, row)
        if dlg.ShowModal() == wx.ID_OK:
            dlg.apply_changes()
            self.config.save_component_to_db(row)
            self._refresh_bom_table_view()
        dlg.Destroy()

    def _on_refresh_live_bom_pricing(self, event):
        if not self.bom_rows:
            wx.MessageBox("Önce projeden BOM yükleyin veya bir proje klasörü seçin.", "Bilgi", wx.OK | wx.ICON_INFORMATION)
            return

        board_count = max(1, int(self.spin_boards.GetValue() or 1))
        self.btn_live_price.Enable(False)
        self._set_busy(True, "LCSC ve DigiKey üzerinden canlı fiyat, stok ve parça numaraları güncelleniyor...")

        def progress_cb(curr, total, name):
            wx.CallAfter(self.lbl_status.SetLabel, f"Fiyat & Stok güncelleniyor ({curr}/{total}): {name}...")

        def worker():
            self.bom_manager.refresh_live_pricing_and_stock(self.bom_rows, board_count=board_count, progress_cb=progress_cb)
            wx.CallAfter(self._on_live_bom_pricing_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_live_bom_pricing_done(self):
        self.btn_live_price.Enable(True)
        self._refresh_bom_table_view()
        self._set_busy(False, "Tüm BOM kalemleri için canlı fiyat, stok ve parça numaraları güncellendi!")

    def _on_export_bom_clicked(self, event):
        if not self.bom_rows:
            wx.MessageBox("Dışa aktarılacak BOM verisi yok.", "Uyarı", wx.OK | wx.ICON_WARNING)
            return

        sel = self.choice_bom_fmt.GetSelection()
        fmt = "engineering" if sel == 0 else ("jlcpcb" if sel == 1 else "digikey")
        board_count = max(1, int(self.spin_boards.GetValue() or 1))

        default_dir = self.project_dir or os.path.expanduser("~")
        default_file = f"BOM_{fmt.upper()}_{board_count}PCB.csv"

        dlg = wx.FileDialog(
            self,
            "BOM CSV Dosyasını Kaydet",
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard="CSV Dosyası (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        if dlg.ShowModal() == wx.ID_OK:
            target_path = dlg.GetPath()
            try:
                self.bom_manager.export_bom_csv(self.bom_rows, target_path, fmt=fmt, board_count=board_count)
                self.lbl_status.SetLabel(f"BOM başarıyla kaydedildi: {target_path}")
                wx.MessageBox(
                    f"BOM dosyası başarıyla oluşturuldu:\n{target_path}",
                    "BOM Dışa Aktarıldı",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as ex:
                wx.MessageBox(f"BOM kaydedilirken hata oluştu:\n{ex}", "Hata", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()

    # =========================================================================
    # TAB 3: SETTINGS (LIBRARY PATHS & DIGIKEY API KEYS)
    # =========================================================================

    def _build_settings_tab(self, panel: wx.Panel):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Library Settings Box
        lib_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Kütüphane Kayıt Yeri ve Kategori Organizasyonu")
        fg1 = wx.FlexGridSizer(rows=5, cols=2, vgap=10, hgap=12)
        fg1.AddGrowableCol(1, 1)

        self.rb_scope_global = wx.RadioButton(panel, label="Global Kütüphane (Tüm KiCad projelerinde ortak kullanılır)", style=wx.RB_GROUP)
        self.rb_scope_project = wx.RadioButton(panel, label="Aktif Proje Klasörü (${KIPRJMOD}/Libraries altında taşınır)")
        is_proj = self.config.settings.get("library_scope") == "project"
        self.rb_scope_project.SetValue(is_proj)
        self.rb_scope_global.SetValue(not is_proj)

        scope_row = wx.BoxSizer(wx.HORIZONTAL)
        scope_row.Add(self.rb_scope_global, 0, wx.RIGHT, 18)
        scope_row.Add(self.rb_scope_project, 0)

        fg1.Add(wx.StaticText(panel, label="Kütüphane Kapsamı:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg1.Add(scope_row, 1, wx.EXPAND)

        dir_row = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_global_dir = wx.TextCtrl(panel, value=str(self.config.settings.get("global_library_dir", "")))
        btn_browse_global = wx.Button(panel, label="Gözat...")
        btn_browse_global.Bind(wx.EVT_BUTTON, self._on_browse_global_lib_dir)
        dir_row.Add(self.txt_global_dir, 1, wx.EXPAND | wx.RIGHT, 6)
        dir_row.Add(btn_browse_global, 0)

        fg1.Add(wx.StaticText(panel, label="Global Kütüphane Klasörü:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg1.Add(dir_row, 1, wx.EXPAND)

        self.txt_lib_prefix = wx.TextCtrl(panel, value=str(self.config.settings.get("library_prefix", "ARI_")))
        fg1.Add(wx.StaticText(panel, label="Kütüphane Ön Eki (Örn. ARI_):"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg1.Add(self.txt_lib_prefix, 1, wx.EXPAND)

        self.chk_by_category = wx.CheckBox(
            panel,
            label="Her komponent kategorisi için ayrı dosya oluştur (Örn: ARI_Resistors.kicad_sym, ARI_ICs_MCUs.kicad_sym)",
        )
        self.chk_by_category.SetValue(bool(self.config.settings.get("organize_by_category", True)))
        fg1.Add(wx.StaticText(panel, label="Dosya Organizasyonu:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg1.Add(self.chk_by_category, 1, wx.EXPAND)

        self.chk_auto_reg = wx.CheckBox(
            panel,
            label="Yeni kütüphaneleri KiCad 10 sym-lib-table ve fp-lib-table dosyalarına otomatik kaydet",
        )
        self.chk_auto_reg.SetValue(bool(self.config.settings.get("auto_register_lib_tables", True)))
        fg1.Add(wx.StaticText(panel, label="Tablo Entegrasyonu:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg1.Add(self.chk_auto_reg, 1, wx.EXPAND)

        lib_box.Add(fg1, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(lib_box, 0, wx.EXPAND | wx.ALL, 8)

        # DigiKey API Settings Box
        dk_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "DigiKey Product Information API v4 Ayarları (developer.digikey.com)")
        fg2 = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=12)
        fg2.AddGrowableCol(1, 1)

        self.txt_dk_client_id = wx.TextCtrl(panel, value=str(self.config.settings.get("digikey_client_id", "")))
        self.txt_dk_client_secret = wx.TextCtrl(
            panel,
            value=str(self.config.settings.get("digikey_client_secret", "")),
            style=wx.TE_PASSWORD,
        )
        self.chk_dk_sandbox = wx.CheckBox(panel, label="DigiKey Sandbox Ortamını Kullan (Production için işaretini kaldırın)")
        self.chk_dk_sandbox.SetValue(bool(self.config.settings.get("digikey_sandbox", False)))

        fg2.Add(wx.StaticText(panel, label="DigiKey Client ID:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg2.Add(self.txt_dk_client_id, 1, wx.EXPAND)
        fg2.Add(wx.StaticText(panel, label="DigiKey Client Secret:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg2.Add(self.txt_dk_client_secret, 1, wx.EXPAND)
        fg2.Add(wx.StaticText(panel, label="API Modu:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg2.Add(self.chk_dk_sandbox, 1, wx.EXPAND)

        dk_btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_test_dk = wx.Button(panel, label="🔑 DigiKey API Bağlantısını Test Et")
        btn_test_dk.Bind(wx.EVT_BUTTON, self._on_test_digikey_api)
        btn_open_dk_dev = wx.Button(panel, label="🌐 DigiKey Developer Portalını Aç")
        btn_open_dk_dev.Bind(wx.EVT_BUTTON, lambda e: webbrowser.open("https://developer.digikey.com/"))
        dk_btn_row.Add(btn_test_dk, 0, wx.RIGHT, 8)
        dk_btn_row.Add(btn_open_dk_dev, 0)

        fg2.Add(wx.StaticText(panel, label="Test / Kayıt:"), 0, wx.ALIGN_CENTER_VERTICAL)
        fg2.Add(dk_btn_row, 1, wx.EXPAND)

        dk_box.Add(fg2, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(dk_box, 0, wx.EXPAND | wx.ALL, 8)

        # Save Settings Button
        btn_save = wx.Button(panel, label="💾 Ayarları Kaydet")
        btn_save.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        btn_save.Bind(wx.EVT_BUTTON, self._on_save_settings)
        vbox.Add(btn_save, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vbox)

    def _on_browse_global_lib_dir(self, event):
        dlg = wx.DirDialog(self, "Global Kütüphane Klasörünü Seçin", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.txt_global_dir.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_save_settings(self, event):
        self.config.settings["library_scope"] = "project" if self.rb_scope_project.GetValue() else "global"
        self.config.settings["global_library_dir"] = self.txt_global_dir.GetValue().strip()
        self.config.settings["library_prefix"] = self.txt_lib_prefix.GetValue().strip()
        self.config.settings["organize_by_category"] = self.chk_by_category.GetValue()
        self.config.settings["auto_register_lib_tables"] = self.chk_auto_reg.GetValue()
        self.config.settings["digikey_client_id"] = self.txt_dk_client_id.GetValue().strip()
        self.config.settings["digikey_client_secret"] = self.txt_dk_client_secret.GetValue().strip()
        self.config.settings["digikey_sandbox"] = self.chk_dk_sandbox.GetValue()

        self.config.save_settings()
        self._update_target_lib_label()
        self.lbl_status.SetLabel("Ayarlar başarıyla kaydedildi.")
        wx.MessageBox("Ayarlarınız başarıyla kaydedildi!", "Bilgi", wx.OK | wx.ICON_INFORMATION)

    def _on_test_digikey_api(self, event):
        self.config.settings["digikey_client_id"] = self.txt_dk_client_id.GetValue().strip()
        self.config.settings["digikey_client_secret"] = self.txt_dk_client_secret.GetValue().strip()
        self.config.settings["digikey_sandbox"] = self.chk_dk_sandbox.GetValue()

        if not self.supplier_service.digikey.is_configured:
            wx.MessageBox("Lütfen önce DigiKey Client ID ve Client Secret alanlarını doldurun.", "Uyarı", wx.OK | wx.ICON_WARNING)
            return

        token = self.supplier_service.digikey._get_token()
        if token:
            wx.MessageBox("✅ DigiKey OAuth2 API bağlantısı başarılı! Token alındı.", "Başarılı", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox(
                "❌ DigiKey API token alınamadı.\nLütfen Client ID, Client Secret ve Sandbox/Production seçimini kontrol edin.",
                "Bağlantı Hatası",
                wx.OK | wx.ICON_ERROR,
            )
