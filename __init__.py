"""
KiCad 10 LCSC & DigiKey Component Importer & Smart BOM Plugin
Root Entry Point for KiCad Scripting Plugins
"""

import os
import sys

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

try:
    from plugin.action_plugin import LcscDigiKeyImporterActionPlugin
    LcscDigiKeyImporterActionPlugin().register()
except Exception as e:
    sys.stderr.write(f"[KiCad LCSC-DigiKey Plugin] Registration error: {e}\n")
