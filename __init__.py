"""
KiCad 10 LCSC & DigiKey Component Importer & Smart BOM Plugin
Root Entry Point for KiCad ActionPlugin
"""

import os
import sys

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# Only register ActionPlugin when loaded inside a running KiCad Pcbnew GUI session
if "pcbnew" in sys.modules or os.path.basename(sys.executable).lower() in ("kicad.exe", "pcbnew.exe"):
    try:
        from .lcsc_digikey_plugin.action_plugin import LcscDigiKeyImporterActionPlugin
        LcscDigiKeyImporterActionPlugin().register()
    except ImportError:
        try:
            from lcsc_digikey_plugin.action_plugin import LcscDigiKeyImporterActionPlugin
            LcscDigiKeyImporterActionPlugin().register()
        except Exception as e:
            sys.stderr.write(f"[KiCad LCSC-DigiKey Plugin] Registration error: {e}\n")
    except Exception as e:
        sys.stderr.write(f"[KiCad LCSC-DigiKey Plugin] Registration error: {e}\n")
