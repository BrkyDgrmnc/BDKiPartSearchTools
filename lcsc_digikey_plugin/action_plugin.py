"""
KiCad 10 ActionPlugin Registration for BDPartSearchTools (by Berkay Değirmenci)
"""

import os

try:
    import pcbnew
    import wx
    from lcsc_digikey_plugin.gui.main_dialog import MainImporterDialog

    class LcscDigiKeyImporterActionPlugin(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "BDKiPartSearchTools"
            self.category = "Library & BOM Tools"
            self.description = (
                "BDKiPartSearchTools (by Berkay Değirmenci) - Komponent arama, şematik sembol (.kicad_sym), "
                "footprint (.kicad_mod) ve 3D model (.step/.wrl) kütüphane aktarıcı ve fiyatlı BOM yöneticisi."
            )
            self.show_toolbar_button = True

            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path = os.path.join(base_dir, "icon.png")
            if os.path.exists(icon_path):
                self.icon_file_name = icon_path
                self.dark_icon_file_name = icon_path

        def Run(self):
            board = pcbnew.GetBoard()
            dlg = MainImporterDialog(parent=None, board=board)
            dlg.ShowModal()
            dlg.Destroy()

except ImportError:
    pass
