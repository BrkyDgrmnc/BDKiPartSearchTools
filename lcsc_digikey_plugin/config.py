"""
KiCad 10 LCSC & DigiKey Component Importer & Smart BOM Plugin
Configuration & Settings Manager
"""

import os
import json
from typing import Dict, Any, List

DEFAULT_CATEGORIES = [
    "Resistors",
    "Capacitors",
    "Inductors_Ferrites",
    "Diodes_Protection",
    "Transistors_FETs",
    "ICs_MCUs",
    "Power_Regulators",
    "Connectors",
    "Crystals_Oscillators",
    "Sensors_Modules",
    "Switches_Relays",
    "LEDs_Opto",
    "Fuses_Passives",
    "Misc_Components",
]

CATEGORY_KEYWORDS = {
    "Resistors": ["resistor", "chip resistor", "potentiometer", "varistor", "ntc", "ptc", "thermistor"],
    "Capacitors": ["capacitor", "mlcc", "tantalum", "electrolytic", "supercapacitor"],
    "Inductors_Ferrites": ["inductor", "ferrite", "bead", "choke", "coil", "transformer", "coupled inductor"],
    "Diodes_Protection": ["diode", "tvs", "zener", "schottky", "rectifier", "esd", "surge"],
    "Transistors_FETs": ["mosfet", "transistor", "bjt", "igbt", "jfet", "darlington", "fet"],
    "Power_Regulators": ["ldo", "buck", "boost", "dc-dc", "regulator", "voltage reference", "pmic", "battery management", "power switch", "charge pump"],
    "Connectors": ["connector", "header", "socket", "usb", "terminal", "plug", "jack", "fpc", "ffc", "rj45", "sma"],
    "Crystals_Oscillators": ["crystal", "oscillator", "resonator", "tcxo", "vcxo"],
    "Sensors_Modules": ["sensor", "imu", "accelerometer", "gyroscope", "temperature", "humidity", "pressure", "hall", "inclinometer", "rf module", "gnss", "gps"],
    "Switches_Relays": ["switch", "tactile", "pushbutton", "dip switch", "slide switch", "relay"],
    "LEDs_Opto": ["led", "optocoupler", "photodiode", "phototransistor", "infrared", "display", "7-segment"],
    "Fuses_Passives": ["fuse", "ptc resettable", "circuit breaker", "filter", "balun", "attenuator"],
    "ICs_MCUs": [
        "microcontroller", "mcu", "mpu", "fpga", "cpld", "memory", "eeprom", "flash", "sram",
        "amplifier", "opamp", "operational amplifier", "comparator", "adc", "dac", "interface",
        "rs485", "can", "uart", "transceiver", "logic", "gate", "buffer", "multiplexer", "shift register",
        "driver", "clock", "timer", "audio", "ic", "processor"
    ],
}

CATEGORY_PREFIX_MAP = {
    "Resistors": "R",
    "Capacitors": "C",
    "Inductors_Ferrites": "L",
    "Diodes_Protection": "D",
    "Transistors_FETs": "Q",
    "ICs_MCUs": "U",
    "Power_Regulators": "U",
    "Connectors": "J",
    "Crystals_Oscillators": "Y",
    "Sensors_Modules": "U",
    "Switches_Relays": "SW",
    "LEDs_Opto": "D",
    "Fuses_Passives": "F",
    "Misc_Components": "U",
}


class ConfigManager:
    """Manages plugin settings, library paths, DigiKey API keys, and local component cache."""

    def __init__(self):
        self.plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.data_dir = os.path.join(self.plugin_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)

        self.settings_path = os.path.join(self.data_dir, "settings.json")
        self.cache_path = os.path.join(self.data_dir, "component_cache.json")
        self.settings = self._load_settings()
        self.component_db = self._load_cache()

    def _get_default_global_lib_dir(self) -> str:
        """Determines the best default global library directory on the user's machine."""
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "KiCad", "10.0", "libraries", "BDKi_Library")
        pcb_ws = r"E:\PCB_Workspace\PCB_Library\BDKi_Library"
        if os.path.exists(r"E:\PCB_Workspace\PCB_Library"):
            return pcb_ws
        return docs_dir

    def _get_kicad_config_dir(self) -> str:
        """Returns KiCad 10.0 AppData Roaming configuration directory."""
        appdata = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
        for ver in ["10.0", "9.0", "8.0"]:
            candidate = os.path.join(appdata, "kicad", ver)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(appdata, "kicad", "10.0")

    def _load_settings(self) -> Dict[str, Any]:
        defaults = {
            "library_scope": "global",  # "global" or "project"
            "global_library_dir": self._get_default_global_lib_dir(),
            "project_library_subdir": "Libraries",
            "library_prefix": "BDKi_",  # e.g. BDKi_Resistors.kicad_sym
            "organize_by_category": True,
            "single_library_name": "Custom_Components",
            "download_3d_step": True,
            "download_3d_wrl": False,
            "auto_register_lib_tables": True,
            "overwrite_existing_footprint": True,
            "overwrite_existing_symbol": True,
            "digikey_client_id": "",
            "digikey_client_secret": "",
            "digikey_sandbox": False,
            "digikey_locale_site": "TR",
            "digikey_locale_currency": "USD",
            "digikey_locale_language": "en",
            "default_bom_format": "engineering",  # "engineering", "jlcpcb", "digikey"
            "ui_language": "auto",  # "auto", "tr", "en"
            "kicad_config_dir": self._get_kicad_config_dir(),
        }
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("library_prefix") == "ARI_":
                    loaded["library_prefix"] = "BDKi_"
                if str(loaded.get("global_library_dir", "")).endswith("LC_DK_Library"):
                    loaded["global_library_dir"] = self._get_default_global_lib_dir()
                defaults.update(loaded)
            except Exception:
                pass
        return defaults

    def save_settings(self) -> None:
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_component_to_db(self, part_info: Dict[str, Any]) -> None:
        """Caches imported component metadata for fast offline BOM enrichment."""
        mpn = (part_info.get("mpn") or "").strip()
        lcsc = (part_info.get("lcsc_part") or "").strip()
        dk = (part_info.get("digikey_part") or "").strip()

        record = {
            "mpn": mpn,
            "manufacturer": part_info.get("manufacturer", ""),
            "lcsc_part": lcsc,
            "digikey_part": dk,
            "category": part_info.get("category", "Misc_Components"),
            "package": part_info.get("package", ""),
            "description": part_info.get("description", ""),
            "datasheet": part_info.get("datasheet", ""),
            "unit_price": part_info.get("unit_price", 0.0),
            "lcsc_price": part_info.get("lcsc_price", 0.0),
            "digikey_price": part_info.get("digikey_price", 0.0),
            "price_tiers": part_info.get("price_tiers", []),
            "stock": part_info.get("stock", 0),
            "lcsc_stock": part_info.get("lcsc_stock", 0),
            "digikey_stock": part_info.get("digikey_stock", 0),
            "part_type": part_info.get("part_type", ""),
            "supplier_url": part_info.get("supplier_url", ""),
            "digikey_url": part_info.get("digikey_url", ""),
            "symbol_lib": part_info.get("symbol_lib", ""),
            "footprint_ref": part_info.get("footprint_ref", ""),
        }

        if mpn:
            self.component_db[f"MPN:{mpn.upper()}"] = record
        if lcsc:
            self.component_db[f"LCSC:{lcsc.upper()}"] = record
        if dk:
            self.component_db[f"DK:{dk.upper()}"] = record

        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.component_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving component DB: {e}")

    def lookup_cached_part(self, mpn: str = "", lcsc: str = "", digikey: str = "") -> Dict[str, Any]:
        if lcsc and f"LCSC:{lcsc.strip().upper()}" in self.component_db:
            return self.component_db[f"LCSC:{lcsc.strip().upper()}"]
        if digikey and f"DK:{digikey.strip().upper()}" in self.component_db:
            return self.component_db[f"DK:{digikey.strip().upper()}"]
        if mpn and f"MPN:{mpn.strip().upper()}" in self.component_db:
            return self.component_db[f"MPN:{mpn.strip().upper()}"]
        return {}

    @staticmethod
    def detect_category(raw_category: str, description: str = "", mpn: str = "") -> str:
        """Maps raw supplier category / description into one of our clean library categories."""
        combined = f"{raw_category} {description} {mpn}".lower()
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    return cat
        return "Misc_Components"

    @staticmethod
    def get_reference_prefix(category: str, raw_prefix: str = "") -> str:
        if raw_prefix:
            clean = raw_prefix.replace("?", "").strip()
            if clean:
                return clean
        return CATEGORY_PREFIX_MAP.get(category, "U")
