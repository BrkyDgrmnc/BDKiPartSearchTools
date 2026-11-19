"""
Unified Hybrid Supplier Service (LCSC / EasyEDA + DigiKey)
Combines parametric search, cross-referencing MPNs between LCSC and DigiKey,
and resolving CAD models (Symbol, Footprint, 3D STEP/WRL) for any component.
"""

from typing import Dict, Any, List, Optional
from lcsc_digikey_plugin.config import ConfigManager
from lcsc_digikey_plugin.api.lcsc_easyeda_client import LcscEasyEdaClient
from lcsc_digikey_plugin.api.digikey_client import DigiKeyClient
from lcsc_digikey_plugin.api.wurth_client import WurthClient


class HybridSupplierService:
    """Orchestrates LCSC/EasyEDA, DigiKey, and Würth Elektronik searches, cross-referencing, and CAD resolution."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.lcsc = LcscEasyEdaClient()
        self.digikey = DigiKeyClient(config)
        self.wurth = WurthClient(config)

    def search(self, query: str, mode: str = "hybrid") -> List[Dict[str, Any]]:
        """
        mode: "lcsc" | "digikey" | "wurth" | "hybrid"
        Returns unified list of component dicts.
        """
        query = (query or "").strip()
        if not query:
            return []

        lcsc_results: List[Dict[str, Any]] = []
        dk_results: List[Dict[str, Any]] = []
        wurth_results: List[Dict[str, Any]] = []

        if mode in ("lcsc", "hybrid"):
            lcsc_results = self.lcsc.search_components(query)

        if mode in ("digikey", "hybrid") and self.digikey.is_configured:
            dk_results = self.digikey.search_keyword(query)

        if mode in ("wurth", "hybrid"):
            wurth_results = self.wurth.search_components(query)

        if mode == "lcsc":
            for item in lcsc_results:
                if not item.get("digikey_url") and item.get("mpn"):
                    item["digikey_url"] = self.digikey.build_digikey_search_url(item["mpn"])
            return lcsc_results

        if mode == "digikey":
            # Return pure DigiKey search results without LCSC enrichment
            return dk_results

        if mode == "wurth":
            for item in wurth_results:
                if not item.get("digikey_url") and item.get("mpn"):
                    item["digikey_url"] = self.digikey.build_digikey_search_url(item["mpn"])
            return wurth_results

        # Hybrid mode: merge by MPN (case-insensitive)
        merged: List[Dict[str, Any]] = []
        mpn_map: Dict[str, Dict[str, Any]] = {}

        for item in lcsc_results:
            mpn_key = (item.get("mpn") or "").strip().upper()
            if not item.get("digikey_url") and item.get("mpn"):
                item["digikey_url"] = self.digikey.build_digikey_search_url(item["mpn"])
            merged.append(item)
            if mpn_key:
                mpn_map[mpn_key] = item

        for dk_item in dk_results:
            mpn_key = (dk_item.get("mpn") or "").strip().upper()
            if mpn_key and mpn_key in mpn_map:
                target = mpn_map[mpn_key]
                target["source"] = "LCSC + DigiKey"
                target["digikey_part"] = dk_item.get("digikey_part", "")
                target["digikey_price"] = dk_item.get("digikey_price", 0.0)
                target["digikey_stock"] = dk_item.get("digikey_stock", 0)
                target["digikey_url"] = dk_item.get("digikey_url", "")
                if not target.get("datasheet") and dk_item.get("datasheet"):
                    target["datasheet"] = dk_item["datasheet"]
                if not target.get("description") and dk_item.get("description"):
                    target["description"] = dk_item["description"]
            else:
                self._enrich_digikey_with_lcsc(dk_item)
                merged.append(dk_item)

        for w_item in wurth_results:
            mpn_key = (w_item.get("mpn") or "").strip().upper()
            if mpn_key and mpn_key in mpn_map:
                target = mpn_map[mpn_key]
                target["source"] += " + Würth"
                target["_is_wurth"] = True
                target["_wurth_item"] = w_item.get("_wurth_item")
                if not target.get("datasheet") and w_item.get("datasheet"):
                    target["datasheet"] = w_item["datasheet"]
            else:
                if not w_item.get("digikey_url") and w_item.get("mpn"):
                    w_item["digikey_url"] = self.digikey.build_digikey_search_url(w_item["mpn"])
                merged.append(w_item)
                if mpn_key:
                    mpn_map[mpn_key] = w_item

        return merged

    def _enrich_digikey_with_lcsc(self, dk_item: Dict[str, Any]) -> None:
        mpn = (dk_item.get("mpn") or "").strip()
        if not mpn or dk_item.get("lcsc_part"):
            return
        matches = self.lcsc.search_components(mpn, page_size=5)
        for m in matches:
            if (m.get("mpn") or "").strip().upper() == mpn.upper():
                dk_item["lcsc_part"] = m.get("lcsc_part", "")
                dk_item["lcsc_price"] = m.get("lcsc_price", 0.0)
                dk_item["lcsc_stock"] = m.get("lcsc_stock", 0)
                dk_item["source"] = "DigiKey + LCSC CAD"
                break
        if not dk_item.get("lcsc_part") and matches:
            # Take top match if MPN is a prefix match
            top = matches[0]
            if mpn.upper() in (top.get("mpn") or "").upper() or (top.get("mpn") or "").upper() in mpn.upper():
                dk_item["lcsc_part"] = top.get("lcsc_part", "")
                dk_item["lcsc_price"] = top.get("lcsc_price", 0.0)
                dk_item["lcsc_stock"] = top.get("lcsc_stock", 0)
                dk_item["source"] = "DigiKey + LCSC CAD"

    def _find_lcsc_cad_id_by_mpn(self, mpn: str) -> str:
        """Finds an EasyEDA/LCSC part ID by MPN solely for 2D/3D CAD resolution without altering part fields."""
        mpn = (mpn or "").strip()
        if not mpn:
            return ""
        matches = self.lcsc.search_components(mpn, page_size=5)
        for m in matches:
            if (m.get("mpn") or "").strip().upper() == mpn.upper():
                return (m.get("lcsc_part") or "").strip()
        if matches:
            top = matches[0]
            top_mpn = (top.get("mpn") or "").strip().upper()
            if top_mpn and (mpn.upper() in top_mpn or top_mpn in mpn.upper()):
                return (top.get("lcsc_part") or "").strip()
        return ""

    def resolve_cad_for_part(self, part_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Ensures CAD data (symbol_data, footprint_data, model_3d) is loaded for a selected part.
        Supports Würth Elektronik native CAD, EasyEDA/LCSC, and DigiKey.
        """
        if part_info.get("_cad_data"):
            return part_info["_cad_data"]

        # Handle Würth Elektronik native CAD models
        if part_info.get("_is_wurth"):
            cad = self.wurth.fetch_cad_data(part_info)
            if cad:
                part_info["_cad_data"] = cad
                if not part_info.get("digikey_url") and part_info.get("mpn"):
                    part_info["digikey_url"] = self.digikey.build_digikey_search_url(part_info["mpn"])
                return cad

        is_pure_digikey = part_info.get("source") == "DigiKey"
        lcsc_id = (part_info.get("lcsc_part") or "").strip()
        if not lcsc_id and part_info.get("mpn"):
            if is_pure_digikey:
                lcsc_id = self._find_lcsc_cad_id_by_mpn(part_info["mpn"])
            else:
                self._enrich_digikey_with_lcsc(part_info)
                lcsc_id = (part_info.get("lcsc_part") or "").strip()

        if not lcsc_id:
            return None

        cad = self.lcsc.fetch_cad_data(lcsc_id)
        if cad:
            part_info["_cad_data"] = cad
            meta = cad.get("metadata", {})
            if not part_info.get("package") and meta.get("package"):
                part_info["package"] = meta["package"]
            if not part_info.get("manufacturer") and meta.get("manufacturer"):
                part_info["manufacturer"] = meta["manufacturer"]
            if not part_info.get("datasheet") and meta.get("datasheet"):
                part_info["datasheet"] = meta["datasheet"]
            if not is_pure_digikey:
                if not part_info.get("unit_price") and meta.get("unit_price"):
                    part_info["unit_price"] = meta["unit_price"]
                    part_info["lcsc_price"] = meta["unit_price"]
                if not part_info.get("stock") and meta.get("stock"):
                    part_info["stock"] = meta["stock"]
                    part_info["lcsc_stock"] = meta["stock"]
            if not part_info.get("digikey_url") and part_info.get("mpn"):
                part_info["digikey_url"] = self.digikey.build_digikey_search_url(part_info["mpn"])
        return cad

    @staticmethod
    def get_unit_price_for_qty(price_tiers: List[Dict[str, Any]], fallback_price: float, qty: int) -> float:
        """Calculates effective unit price for a given order quantity from tiered breaks."""
        if not price_tiers:
            return float(fallback_price or 0.0)
        qty = max(1, int(qty))
        applicable_price = float(price_tiers[0].get("price") or fallback_price or 0.0)
        for tier in sorted(price_tiers, key=lambda t: int(t.get("min_qty") or 1)):
            min_q = int(tier.get("min_qty") or 1)
            if qty >= min_q:
                applicable_price = float(tier.get("price") or applicable_price)
        return applicable_price
