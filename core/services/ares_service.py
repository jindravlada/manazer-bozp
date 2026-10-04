import json

try:
    import requests
except ImportError:
    requests = None

from core.http_safe import safe_https_get
from core.services.cz_nace_service import cz_nace_service

ARES_ALLOWED_HOSTS = frozenset({"ares.gov.cz"})
ARES_TIMEOUT_SECONDS = 10
ARES_MAX_RESPONSE_BYTES = 1_048_576


class AresService:
    BASE_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty"

    def _normalize_ico(self, ico: str) -> str | None:
        digits = "".join(ch for ch in str(ico or "") if ch.isdigit())
        if not digits:
            if str(ico or "").strip():
                raise ValueError("IČO smí obsahovat pouze číslice.")
            return None
        if len(digits) > 8:
            raise ValueError("IČO smí obsahovat nejvýše 8 číslic.")
        return digits

    def find_by_ico(self, ico: str) -> dict | None:
        if requests is None:
            raise RuntimeError("Knihovna requests není nainstalovaná.")

        normalized = self._normalize_ico(ico)
        if not normalized:
            return None

        result = safe_https_get(
            f"{self.BASE_URL}/{normalized}",
            allowed_hosts=ARES_ALLOWED_HOSTS,
            timeout=ARES_TIMEOUT_SECONDS,
            max_bytes=ARES_MAX_RESPONSE_BYTES,
            headers={"Accept": "application/json"},
        )

        if result.status_code != 200:
            return None

        try:
            data = json.loads(result.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None

        address = data.get("sidlo", {})
        if not isinstance(address, dict):
            address = {}
        address_text = self._format_address(address)

        nace_codes = data.get("czNace", [])
        if not isinstance(nace_codes, list):
            nace_codes = []
        raw_codes = [str(code).strip() for code in nace_codes if str(code).strip()]

        nace_display_list = cz_nace_service.get_displays(raw_codes)
        main_code = raw_codes[0] if raw_codes else ""

        return {
            "ico": data.get("ico", normalized),
            "name": data.get("obchodniJmeno", ""),
            "address": address_text,
            "nace_codes": raw_codes,
            "nace_code": main_code,
            "nace_list": nace_display_list,
            "nace": nace_display_list[0] if nace_display_list else "",
        }

    def _format_address(self, address: dict) -> str:
        street = address.get("nazevUlice") or ""
        house_number = address.get("cisloDomovni") or ""
        orientation_number = address.get("cisloOrientacni") or ""
        municipality = address.get("nazevObce") or ""
        zip_code = address.get("psc") or ""

        number = str(house_number)
        if orientation_number:
            number = f"{number}/{orientation_number}" if number else str(orientation_number)

        street_line = " ".join(part for part in [street, number] if part)
        city_line = " ".join(part for part in [str(zip_code), municipality] if part)

        return ", ".join(part for part in [street_line, city_line] if part)


ares_service = AresService()
