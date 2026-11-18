"""
KiCad 10 ActionPlugin Registration for LCSC & DigiKey Component Importer & Smart BOM
"""

import os

try:
    import pcbnew
    import wx
    from plugin.gui.main_dialog import MainImporterDialog

    class LcscDigiKeyImporterActionPlugin(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "LCSC & DigiKey Kütüphane ve BOM Yöneticisi"
            self.category = "Library & BOM Tools"
            self.description = (
                "LCSC / EasyEDA ve DigiKey üzerinden komponent bilgisi, şematik sembol (.kicad_sym), "
                "footprint (.kicad_mod) ve 3D model (.step/.wrl) indirip kütüphaneye ekler; "
                "fiyat, stok ve parça numaralarıyla birlikte mühendislik BOM çıktısı üretir."
            )
            self.show_toolbar_button = True

            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path = os.path.join(base_dir, "icon.png")
            if os.path.exists(icon_path):
                self.icon_file_name = icon_path

        def Run(self):
            board = pcbnew.GetBoard()
            dlg = MainImporterDialog(parent=None, board=board)
            dlg.ShowModal()
            dlg.Destroy()

except ImportError:
    pass
