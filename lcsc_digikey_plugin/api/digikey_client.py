"""
DigiKey Product Information API v4 Client + Hybrid CAD Resolver
Supports OAuth2 Client Credentials flow for DigiKey API v4 (Production & Sandbox)
and cross-references MPN with EasyEDA/LCSC for CAD symbols, footprints, and 3D models.
"""

import time
import urllib.parse
import requests
from typing import Dict, Any, List, Optional, Tuple
from lcsc_digikey_plugin.config import ConfigManager


class DigiKeyClient:
    """Client for DigiKey Product Information API v4."""

    PROD_BASE = "https://api.digikey.com"
    SANDBOX_BASE = "https://sandbox-api.digikey.com"

    def __init__(self, config: ConfigManager, timeout: int = 12):
        self.config = config
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0
        self.last_error: str = ""

    @property
    def is_configured(self) -> bool:
        cid = (self.config.settings.get("digikey_client_id") or "").strip()
        sec = (self.config.settings.get("digikey_client_secret") or "").strip()
        return bool(cid and sec)

    @property
    def base_url(self) -> str:
        if self.config.settings.get("digikey_sandbox", False):
            return self.SANDBOX_BASE
        return self.PROD_BASE

    def _get_token(self) -> Optional[str]:
        if not self.is_configured:
            return None
        if self._access_token and time.time() < self._token_expiry - 30:
            return self._access_token

        cid = self.config.settings.get("digikey_client_id", "").strip()
        sec = self.config.settings.get("digikey_client_secret", "").strip()

        # Try selected environment first; if 401 Invalid clientId, auto-fallback to the other environment
        bases = [self.base_url, self.SANDBOX_BASE if self.base_url == self.PROD_BASE else self.PROD_BASE]
        for b_url in bases:
            url = f"{b_url}/v1/oauth2/token"
            try:
                resp = requests.post(
                    url,
                    data={
                        "client_id": cid,
                        "client_secret": sec,
                        "grant_type": "client_credentials",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._access_token = data.get("access_token")
                    expires_in = int(data.get("expires_in") or 1799)
                    self._token_expiry = time.time() + expires_in
                    if b_url != self.base_url:
                        self.config.settings["digikey_sandbox"] = (b_url == self.SANDBOX_BASE)
                    return self._access_token
                else:
                    self.last_error = f"OAuth2 Token Hatası ({resp.status_code}): {resp.text[:160]}"
            except Exception as e:
                self.last_error = f"OAuth2 Bağlantı Hatası: {e}"
                print(f"[DigiKeyClient] OAuth token error: {e}")
        return None

    def _headers(self) -> Optional[Dict[str, str]]:
        token = self._get_token()
        if not token:
            return None
        cid = self.config.settings.get("digikey_client_id", "").strip()
        return {
            "Authorization": f"Bearer {token}",
            "X-DIGIKEY-Client-Id": cid,
            "X-DIGIKEY-Locale-Site": self.config.settings.get("digikey_locale_site", "US"),
            "X-DIGIKEY-Locale-Language": self.config.settings.get("digikey_locale_language", "en"),
            "X-DIGIKEY-Locale-Currency": self.config.settings.get("digikey_locale_currency", "USD"),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def search_keyword(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches DigiKey API v4 (with v3 fallback) by keyword or part number."""
        self.last_error = ""
        headers = self._headers()
        if not headers:
            return []

        url = f"{self.base_url}/products/v4/search/keyword"
        payload = {
            "Keywords": keyword.strip(),
            "Limit": limit,
            "Offset": 0,
        }
        results = []
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("Products") or []
                for prod in products:
                    parsed = self._parse_v4_product(prod)
                    if parsed:
                        results.append(parsed)
                return results

            # Fallback to v3 Product Information API if user subscribed to v3 instead of v4
            v3_url = f"{self.base_url}/Search/v3/Products/Keyword"
            v3_resp = requests.post(
                v3_url,
                json={"Keywords": keyword.strip(), "RecordCount": limit, "RecordStartPosition": 0},
                headers=headers,
                timeout=self.timeout,
            )
            if v3_resp.status_code == 200:
                v3_data = v3_resp.json()
                for prod in (v3_data.get("Products") or []):
                    parsed = self._parse_v4_product(prod)
                    if parsed:
                        results.append(parsed)
                return results

            if resp.status_code in (401, 403):
                self.last_error = (
                    "DigiKey API Yetki Hatası (403 Forbidden - Product Information API aktif değil). "
                    "Lütfen developer.digikey.com üzerinde uygulamanızda (Production App) "
                    "'Product Information V4' API iznini aktif edin."
                )
            else:
                self.last_error = f"DigiKey Arama Hatası (HTTP {resp.status_code})"
        except Exception as e:
            self.last_error = f"DigiKey İstek Hatası: {e}"
            print(f"[DigiKeyClient] Keyword search error: {e}")
        return results

    def test_api_access(self) -> Tuple[bool, str]:
        """Tests both OAuth2 token generation AND Product Information API v4/v3 search authorization."""
        self._access_token = None
        self._token_expiry = 0.0
        token = self._get_token()
        if not token:
            return False, (
                "❌ DigiKey OAuth2 Token alınamadı!\n\n"
                "Lütfen Client ID ve Client Secret değerlerinin doğru olduğundan emin olun."
            )

        env_name = "Sandbox" if self.config.settings.get("digikey_sandbox", False) else "Production"
        headers = self._headers()
        url = f"{self.base_url}/products/v4/search/keyword"
        try:
            resp = requests.post(url, json={"Keywords": "STM32", "Limit": 1, "Offset": 0}, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                return True, f"✅ DigiKey {env_name} API bağlantısı ve 'Product Information v4' ürün arama yetkisi başarılı!"

            v3_resp = requests.post(
                f"{self.base_url}/Search/v3/Products/Keyword",
                json={"Keywords": "STM32", "RecordCount": 1},
                headers=headers,
                timeout=self.timeout,
            )
            if v3_resp.status_code == 200:
                return True, f"✅ DigiKey {env_name} API bağlantısı ve 'Product Information v3' ürün arama yetkisi başarılı!"

            if resp.status_code in (401, 403):
                return False, (
                    f"⚠️ OAuth2 Token alındı ({env_name}), ANCAK ürün arama isteği reddedildi (HTTP {resp.status_code} Forbidden)!\n\n"
                    "Bunun sebebi developer.digikey.com üzerindeki uygulamanızda 'Product Information' API aboneliğinin kapalı olması veya Sandbox kısıtlamasıdır.\n\n"
                    "Çözüm:\n"
                    "1. https://developer.digikey.com adresinde 'Organizations -> Production Apps' bölümüne girin.\n"
                    "2. Ücretsiz bir 'Production App' oluşturun (veya mevcut uygulamanızı düzenleyin).\n"
                    "3. Uygulama içindeki API listesinden 'Product Information (v4)' seçeneğini AKTİF (Enabled/Subscribed) yapıp kaydedin.\n"
                    "4. Production App'in Client ID ve Secret bilgilerini buraya girip 'Sandbox' kutucuğunun işaretini kaldırın."
                )
            return False, f"❌ DigiKey Arama Testi Hatası (HTTP {resp.status_code}):\n{resp.text[:250]}"
        except Exception as e:
            return False, f"❌ Bağlantı hatası: {e}"

    def get_product_details(self, part_number: str) -> Optional[Dict[str, Any]]:
        """Fetches exact product details from DigiKey API v4 by DigiKey P/N or MPN."""
        headers = self._headers()
        if not headers:
            return None
        encoded = urllib.parse.quote(part_number.strip(), safe="")
        url = f"{self.base_url}/products/v4/search/{encoded}/productdetails"
        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                prod = data.get("Product") or data
                return self._parse_v4_product(prod)
        except Exception as e:
            print(f"[DigiKeyClient] Product details error: {e}")
        return None

    def _parse_v4_product(self, prod: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not prod:
            return None

        mpn = (prod.get("ManufacturerProductNumber") or prod.get("ManufacturerPartNumber") or "").strip()
        mfg_obj = prod.get("Manufacturer") or {}
        manufacturer = (mfg_obj.get("Name") or "").strip() if isinstance(mfg_obj, dict) else str(mfg_obj)

        desc_obj = prod.get("Description") or {}
        if isinstance(desc_obj, dict):
            description = (desc_obj.get("DetailedDescription") or desc_obj.get("ProductDescription") or "").strip()
        else:
            description = str(desc_obj)

        cat_obj = prod.get("Category") or {}
        raw_cat = (cat_obj.get("Name") or "").strip() if isinstance(cat_obj, dict) else ""

        datasheet = (prod.get("DatasheetUrl") or prod.get("PrimaryDatasheet") or "").strip()
        product_url = (prod.get("ProductUrl") or "").strip()
        stock = int(prod.get("QuantityAvailable") or 0)

        # Extract DigiKey Part Number and Pricing from ProductVariations (v4 structure)
        dk_part = ""
        price_tiers = []
        unit_price = float(prod.get("UnitPrice") or 0.0)

        variations = prod.get("ProductVariations") or []
        for var in variations:
            v_dk = (var.get("DigiKeyProductNumber") or "").strip()
            if v_dk and not dk_part:
                dk_part = v_dk
            pricing = var.get("StandardPricing") or []
            if pricing and not price_tiers:
                for p in pricing:
                    try:
                        brk = int(p.get("BreakQuantity") or 1)
                        up = float(p.get("UnitPrice") or 0.0)
                        price_tiers.append({"min_qty": brk, "max_qty": -1, "price": up})
                    except Exception:
                        pass

        if not dk_part:
            dk_part = (prod.get("DigiKeyPartNumber") or prod.get("DigiKeyProductNumber") or "").strip()

        price_tiers.sort(key=lambda x: x["min_qty"])
        if price_tiers and unit_price <= 0.0:
            unit_price = price_tiers[0]["price"]

        # Extract Package / Case from Parameters
        package = ""
        attributes = {}
        for param in (prod.get("Parameters") or []):
            p_name = (param.get("ParameterText") or param.get("Parameter") or "").strip()
            p_val = (param.get("ValueText") or param.get("Value") or "").strip()
            if p_name and p_val:
                attributes[p_name] = p_val
                if p_name.lower() in ("package / case", "supplier device package") and not package:
                    package = p_val

        category = ConfigManager.detect_category(raw_cat, description, mpn)
        if not product_url and mpn:
            product_url = self.build_digikey_search_url(mpn)

        return {
            "source": "DigiKey",
            "lcsc_part": "",
            "digikey_part": dk_part,
            "mpn": mpn,
            "manufacturer": manufacturer,
            "category": category,
            "raw_category": raw_cat,
            "package": package,
            "description": description,
            "datasheet": datasheet,
            "stock": stock,
            "lcsc_stock": 0,
            "digikey_stock": stock,
            "unit_price": unit_price,
            "lcsc_price": 0.0,
            "digikey_price": unit_price,
            "price_tiers": price_tiers,
            "part_type": "DigiKey",
            "supplier_url": product_url,
            "digikey_url": product_url,
            "attributes": attributes,
        }

    @staticmethod
    def build_digikey_search_url(mpn_or_dk: str) -> str:
        q = urllib.parse.quote((mpn_or_dk or "").strip())
        return f"https://www.digikey.com/en/products/result?keywords={q}"
