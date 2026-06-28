try:
    import requests
except ImportError:
    requests = None

from core.services.cz_nace_service import cz_nace_service


class AresService:
    BASE_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty"

    def find_by_ico(self, ico: str) -> dict | None:
        if requests is None:
            raise RuntimeError("Knihovna requests není nainstalovaná.")

        ico = "".join(ch for ch in ico if ch.isdigit())
        if not ico:
            return None

        response = requests.get(f"{self.BASE_URL}/{ico}", timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()

        address = data.get("sidlo", {})
        address_text = self._format_address(address)

        nace_codes = data.get("czNace", [])
        if not isinstance(nace_codes, list):
            nace_codes = []

        nace_display_list = cz_nace_service.get_displays(nace_codes)

        return {
            "ico": data.get("ico", ico),
            "name": data.get("obchodniJmeno", ""),
            "address": address_text,
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
