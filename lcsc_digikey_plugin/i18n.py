"""
Internationalization (i18n) Engine for BDKiPartSearchTools
Supports Turkish (tr) and English (en) with automatic KiCad language detection.
"""

import os
import json
import locale
from typing import Dict, Any, Optional

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # Window and Tabs
    "app_title": {
        "tr": "BDKiPartSearchTools — LCSC / EasyEDA & DigiKey Kütüphane ve BOM Yöneticisi (KiCad 10)",
        "en": "BDKiPartSearchTools — LCSC / EasyEDA & DigiKey Library & BOM Manager (KiCad 10)",
    },
    "tab_search": {
        "tr": "🔍 Komponent Arama & CAD İçe Aktarma",
        "en": "🔍 Component Search & CAD Importer",
    },
    "tab_bom": {
        "tr": "📋 Akıllı BOM & Canlı Fiyat/Stok Yöneticisi",
        "en": "📋 Smart BOM & Live Price/Stock Manager",
    },
    "tab_settings": {
        "tr": "⚙️ Ayarlar",
        "en": "⚙️ Settings",
    },

    # Language Switcher
    "lang_label": {
        "tr": "Dil / Language:",
        "en": "Language / Dil:",
    },
    "lang_auto": {
        "tr": "Otomatik (KiCad Dili)",
        "en": "Auto (KiCad Language)",
    },
    "lang_tr": {
        "tr": "Türkçe",
        "en": "Türkçe",
    },
    "lang_en": {
        "tr": "English",
        "en": "English",
    },

    # Tab 1: Search & Importer
    "search_lbl": {
        "tr": "Arama / Parça No:",
        "en": "Search / Part #:",
    },
    "search_placeholder": {
        "tr": "Örn: STM32F103C8T6, C8734, 10k 0402, LM358, USB-C...",
        "en": "E.g. STM32F103C8T6, C8734, 10k 0402, LM358, USB-C...",
    },
    "btn_clear": {
        "tr": "✖ Temizle",
        "en": "✖ Clear",
    },
    "source_lbl": {
        "tr": "Kaynak:",
        "en": "Source:",
    },
    "source_hybrid": {
        "tr": "LCSC + DigiKey + Würth (Hibrit)",
        "en": "LCSC + DigiKey + Würth (Hybrid)",
    },
    "source_lcsc": {
        "tr": "Sadece LCSC / EasyEDA",
        "en": "LCSC / EasyEDA Only",
    },
    "source_digikey": {
        "tr": "Sadece DigiKey API",
        "en": "DigiKey API Only",
    },
    "source_wurth": {
        "tr": "Sadece Würth Elektronik",
        "en": "Würth Elektronik Only",
    },
    "btn_search": {
        "tr": "🔍 Ara",
        "en": "🔍 Search",
    },

    # Columns
    "col_source": {"tr": "Kaynak", "en": "Source"},
    "col_mpn": {"tr": "MPN (Parça No)", "en": "MPN (Part #)"},
    "col_mfg": {"tr": "Üretici", "en": "Manufacturer"},
    "col_cat": {"tr": "Kategori", "en": "Category"},
    "col_pkg": {"tr": "Paket / Footprint", "en": "Package / Footprint"},
    "col_lcsc": {"tr": "LCSC #", "en": "LCSC #"},
    "col_dk": {"tr": "DigiKey #", "en": "DigiKey #"},
    "col_price": {"tr": "Birim Fiyat ($)", "en": "Unit Price ($)"},
    "col_stock": {"tr": "Stok", "en": "Stock"},
    "col_desc": {"tr": "Açıklama", "en": "Description"},

    # Canvases
    "preview_box": {
        "tr": "Canlı CAD Önizleme (Şematik Sembol & PCB Footprint)",
        "en": "Live CAD Preview (Schematic Symbol & PCB Footprint)",
    },
    "searching": {"tr": "Aranıyor...", "en": "Searching..."},
    "no_result": {"tr": "Sonuç Yok", "en": "No Results"},
    "cad_not_found": {"tr": "CAD Bulunamadı", "en": "CAD Not Found"},

    # Edit & Import Box
    "import_box": {
        "tr": "Kütüphane ve Sembol Alanları (İçe Aktarmadan Önce Düzenlenebilir)",
        "en": "Library & Symbol Properties (Editable Before Import)",
    },
    "lbl_category": {"tr": "Kategori:", "en": "Category:"},
    "lbl_target_lib": {"tr": "Hedef Kütüphane:", "en": "Target Library:"},
    "lbl_sym_name": {"tr": "Sembol Adı (MPN):", "en": "Symbol Name (MPN):"},
    "lbl_ref_prefix": {"tr": "Ref Prefix:", "en": "Ref Prefix:"},
    "lbl_fp_name": {"tr": "Footprint Adı:", "en": "Footprint Name:"},
    "lbl_pkg": {"tr": "Paket:", "en": "Package:"},
    "lbl_lcsc_code": {"tr": "LCSC Parça No:", "en": "LCSC Part #:"},
    "lbl_dk_code": {"tr": "DigiKey Parça No:", "en": "DigiKey Part #:"},
    "lbl_unit_price": {"tr": "Birim Fiyat ($):", "en": "Unit Price ($):"},
    "lbl_mfg": {"tr": "Üretici:", "en": "Manufacturer:"},

    "chk_step": {"tr": "3D STEP Modeli (.step)", "en": "3D STEP Model (.step)"},
    "chk_wrl": {"tr": "3D WRL Modeli (.wrl)", "en": "3D WRL Model (.wrl)"},

    "btn_import": {
        "tr": "📥 KiCad Kütüphanesine İçe Aktar (Sembol + Footprint + 3D)",
        "en": "📥 Import to KiCad Library (Symbol + Footprint + 3D)",
    },
    "btn_datasheet": {"tr": "📄 Datasheet", "en": "📄 Datasheet"},
    "btn_web": {"tr": "🌐 LCSC / DigiKey Sayfası", "en": "🌐 Supplier Web Page"},

    # Messages
    "warn_empty_query": {
        "tr": "Lütfen aramak istediğiniz parça numarasını veya anahtar kelimeyi girin.",
        "en": "Please enter a part number or keyword to search.",
    },
    "warn_dk_not_configured": {
        "tr": "Sadece DigiKey araması seçtiniz ancak DigiKey API anahtarları henüz girilmemiş.\n3. Sekmeden (Ayarlar) DigiKey Client ID & Secret girebilir veya 'LCSC + DigiKey (Hibrit)' modunu kullanabilirsiniz.",
        "en": "You selected DigiKey Only, but DigiKey API credentials are not set.\nPlease configure Client ID & Secret in Settings (Tab 3) or use Hybrid / LCSC mode.",
    },
    "status_found": {
        "tr": "'{query}' için {count} sonuç bulundu.",
        "en": "Found {count} results for '{query}'.",
    },
    "status_importing": {
        "tr": "'{mpn}' kütüphaneye aktarılıyor ve 3D model indiriliyor...",
        "en": "Importing '{mpn}' into library and downloading 3D model...",
    },
    "status_success": {
        "tr": "Başarıyla eklendi: Sembol [{sym}] | Footprint [{fp}]",
        "en": "Successfully imported: Symbol [{sym}] | Footprint [{fp}]",
    },
    "import_success_title": {"tr": "Kütüphaneye Eklendi", "en": "Import Successful"},
    "import_success_msg": {
        "tr": "✅ Komponent KiCad 10 kütüphanenize başarıyla eklendi!\n\n"
              "• Kategori Kütüphanesi: {lib}\n"
              "• Şematik Sembolü: {sym}\n"
              "• PCB Footprint: {fp}\n"
              "• Sembol Dosyası: {sym_file}\n"
              "• Footprint Dosyası: {fp_file}\n"
              "• İndirilen 3D Modeller ({model_count} adet): {models}\n\n"
              "💡 Mühendislik ve Tedarikçi Alanları (MPN, Manufacturer, LCSC_Part, DigiKey_Part, Datasheet, Supplier_URL) sembolün içine gömüldü!\n"
              "Tedarikçi kuralları gereği dinamik Fiyat & Stok bilgileri şematik yerine 2. Sekmedeki BOM canlı sorguda gösterilir.\n"
              "Şematik Editöründe (Eeschema) 'A' tuşuna basarak doğrudan şematiğinize ekleyebilirsiniz.",
        "en": "✅ Component successfully added to your KiCad 10 library!\n\n"
              "• Category Library: {lib}\n"
              "• Schematic Symbol: {sym}\n"
              "• PCB Footprint: {fp}\n"
              "• Symbol File: {sym_file}\n"
              "• Footprint File: {fp_file}\n"
              "• Downloaded 3D Models ({model_count}): {models}\n\n"
              "💡 Engineering metadata (MPN, Manufacturer, LCSC_Part, DigiKey_Part, Datasheet, Supplier_URL) embedded into symbol.\n"
              "Dynamic Price & Stock are checked live in the Smart BOM tab to comply with supplier terms.\n"
              "Press 'A' in Schematic Editor (Eeschema) to place it directly into your design.",
    },

    # Tab 2: Smart BOM
    "bom_top_box": {
        "tr": "Proje BOM Kaynağı ve Canlı Fiyat/Stok Güncelleme",
        "en": "Project BOM Source & Live Price/Stock Refresh",
    },
    "btn_load_sch": {"tr": "📂 Şematikten Çek (.kicad_sch)", "en": "📂 Load from Schematic (.kicad_sch)"},
    "btn_load_pcb": {"tr": "📂 PCB'den Çek (.kicad_pcb)", "en": "📂 Load from PCB (.kicad_pcb)"},
    "btn_refresh_prices": {
        "tr": "🔄 LCSC & DigiKey Canlı Fiyat/Stok Güncelle",
        "en": "🔄 Refresh Live LCSC & DigiKey Prices/Stock",
    },
    "lbl_order_qty": {"tr": "Sipariş Adedi:", "en": "Order Qty:"},
    "lbl_export_fmt": {"tr": "Dışa Aktarma Formatı:", "en": "Export Format:"},
    "btn_export_csv": {"tr": "💾 BOM Listesini CSV Olarak Dışa Aktar", "en": "💾 Export BOM as CSV"},

    "bom_col_ref": {"tr": "Referanslar", "en": "References"},
    "bom_col_qty": {"tr": "Adet", "en": "Qty"},
    "bom_col_val": {"tr": "Değer", "en": "Value"},
    "bom_col_fp": {"tr": "Footprint", "en": "Footprint"},
    "bom_col_mpn": {"tr": "MPN", "en": "MPN"},
    "bom_col_mfg": {"tr": "Üretici", "en": "Manufacturer"},
    "bom_col_lcsc_code": {"tr": "LCSC Parça #", "en": "LCSC Part #"},
    "bom_col_lcsc_price": {"tr": "LCSC Fiyat ($)", "en": "LCSC Price ($)"},
    "bom_col_lcsc_stock": {"tr": "LCSC Stok", "en": "LCSC Stock"},
    "bom_col_dk_code": {"tr": "DigiKey Parça #", "en": "DigiKey Part #"},
    "bom_col_dk_price": {"tr": "DigiKey Fiyat ($)", "en": "DigiKey Price ($)"},
    "bom_col_dk_stock": {"tr": "DigiKey Stok", "en": "DigiKey Stock"},
    "bom_col_total": {"tr": "Toplam Tutar ($)", "en": "Line Total ($)"},
    "bom_summary": {
        "tr": "Toplam: {count} Benzersiz Komponent ({total_items} Adet) | Toplam Proje Maliyeti: ${cost:.2f}",
        "en": "Total: {count} Unique Components ({total_items} Parts) | Total Project Cost: ${cost:.2f}",
    },

    # Tab 3: Settings
    "settings_lib_box": {
        "tr": "Kütüphane Depolama ve Kapsam Ayarları",
        "en": "Library Storage & Scope Settings",
    },
    "settings_wurth_box": {
        "tr": "Würth Elektronik Resmi Kütüphane Ayarları (kicad-wurth-library)",
        "en": "Würth Elektronik Official Library Settings (kicad-wurth-library)",
    },
    "lbl_wurth_path": {
        "tr": "Würth Kütüphane Yolu:",
        "en": "Würth Library Path:",
    },
    "lbl_scope": {"tr": "Kütüphane Kapsamı:", "en": "Library Scope:"},
    "scope_global": {"tr": "Global (Tüm KiCad projelerinde ortak)", "en": "Global (Shared across all KiCad projects)"},
    "scope_project": {"tr": "Proje Bazlı (${KIPRJMOD}/Libraries)", "en": "Project Specific (${KIPRJMOD}/Libraries)"},
    "lbl_global_path": {"tr": "Global Kütüphane Yolu:", "en": "Global Library Path:"},
    "btn_browse": {"tr": "Gözat...", "en": "Browse..."},
    "lbl_prefix": {"tr": "Kütüphane İsim Öneki:", "en": "Library Name Prefix:"},
    "chk_organize": {"tr": "Komponentleri 14 Kategoriye Göre Grupla", "en": "Group Components into 14 Categories"},
    "chk_auto_reg": {"tr": "sym-lib-table ve fp-lib-table Dosyalarına Otomatik Kaydet", "en": "Auto-register in sym-lib-table & fp-lib-table"},
    "chk_overwrite": {"tr": "Varolan Sembol ve Footprint'lerin Üzerine Yaz", "en": "Overwrite Existing Symbols & Footprints"},

    "settings_dk_box": {
        "tr": "DigiKey API v4 / v3 OAuth2 Kimlik Bilgileri",
        "en": "DigiKey API v4 / v3 OAuth2 Credentials",
    },
    "lbl_dk_id": {"tr": "Client ID:", "en": "Client ID:"},
    "lbl_dk_secret": {"tr": "Client Secret:", "en": "Client Secret:"},
    "lbl_dk_env": {"tr": "API Ortamı:", "en": "API Environment:"},
    "dk_env_prod": {"tr": "Production (Resmi Canlı - Önerilen)", "en": "Production (Official Live - Recommended)"},
    "dk_env_sandbox": {"tr": "Sandbox (Test Ortamı)", "en": "Sandbox (Testing Environment)"},
    "btn_test_dk": {"tr": "⚡ DigiKey API Bağlantısını Test Et", "en": "⚡ Test DigiKey API Connection"},
    "btn_save_settings": {"tr": "💾 Ayarları Kaydet", "en": "💾 Save Settings"},
    "settings_saved": {"tr": "Ayarlar başarıyla kaydedildi!", "en": "Settings successfully saved!"},
}


class I18n:
    """Manages active UI language and string lookups."""
    _current_lang = "en"

    @classmethod
    def detect_kicad_language(cls, kicad_config_dir: Optional[str] = None) -> str:
        """
        Detects KiCad's configured language from kicad_common.json or system locale.
        Returns 'tr' for Turkish, 'en' for English.
        """
        try:
            cfg_dir = kicad_config_dir
            if not cfg_dir:
                appdata = os.environ.get("APPDATA", "")
                for ver in ["10.0", "9.0", "8.0"]:
                    cand = os.path.join(appdata, "kicad", ver)
                    if os.path.exists(cand):
                        cfg_dir = cand
                        break
            if cfg_dir:
                common_path = os.path.join(cfg_dir, "kicad_common.json")
                if os.path.exists(common_path):
                    with open(common_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    kicad_lang = str(data.get("system", {}).get("language", "")).strip().lower()
                    if "turk" in kicad_lang or "türk" in kicad_lang or kicad_lang == "tr":
                        return "tr"
                    if "eng" in kicad_lang or kicad_lang == "en":
                        return "en"
        except Exception:
            pass

        # Fallback to system locale
        try:
            loc = locale.getdefaultlocale()[0] or ""
            if loc.lower().startswith("tr"):
                return "tr"
        except Exception:
            pass

        return "en"

    @classmethod
    def init(cls, user_pref: str = "auto", kicad_config_dir: Optional[str] = None) -> str:
        """Initializes current language based on preference ('auto', 'tr', 'en')."""
        pref = (user_pref or "auto").strip().lower()
        if pref in ("tr", "turkish", "türkçe"):
            cls._current_lang = "tr"
        elif pref in ("en", "english"):
            cls._current_lang = "en"
        else:
            cls._current_lang = cls.detect_kicad_language(kicad_config_dir)
        return cls._current_lang

    @classmethod
    def get_current_lang(cls) -> str:
        return cls._current_lang

    @classmethod
    def set_lang(cls, lang: str):
        if lang in ("tr", "en"):
            cls._current_lang = lang

    @classmethod
    def t(cls, key: str, default: Optional[str] = None, **kwargs) -> str:
        """Translates a key into the active language, formatting with kwargs."""
        entry = TRANSLATIONS.get(key)
        if not entry:
            res = default if default is not None else key
        else:
            res = entry.get(cls._current_lang) or entry.get("en") or entry.get("tr") or default or key
        if kwargs:
            try:
                res = res.format(**kwargs)
            except Exception:
                pass
        return res


def _(key: str, default: Optional[str] = None, **kwargs) -> str:
    """Convenient alias for I18n.t()"""
    return I18n.t(key, default=default, **kwargs)
