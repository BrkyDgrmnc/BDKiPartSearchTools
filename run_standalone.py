"""
Entrypoint for KiCad 10 IPC API Plugin (Schematic Editor, Symbol Editor, PCB Editor, Project Manager)
and Eeschema BOM Tool / Standalone Launcher.
"""

import os
import sys

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import wx
from plugin.gui.main_dialog import MainImporterDialog


def main():
    project_dir = None
    if len(sys.argv) > 1:
        arg_path = sys.argv[1].strip('"').strip()
        if os.path.isdir(arg_path):
            project_dir = os.path.abspath(arg_path)
        elif os.path.isfile(arg_path):
            project_dir = os.path.dirname(os.path.abspath(arg_path))

    app = wx.App(False)
    dlg = MainImporterDialog(parent=None, board=None, project_dir=project_dir)
    dlg.ShowModal()
    dlg.Destroy()
    app.MainLoop()


if __name__ == "__main__":
    main()
