import json
from pathlib import Path

from core.utils.czech_sort import czech_sorted


class KnihaUrazuCiselnikService:
    def __init__(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"

    def _load_json(self, filename: str):
        path = self.data_dir / filename
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _items_to_display(self, filename: str) -> list[str]:
        data = self._load_json(filename)
        values = []

        for item in data:
            if isinstance(item, dict):
                value = (
                    item.get("display")
                    or item.get("text")
                    or item.get("nazev")
                    or item.get("name")
                )

                if not value:
                    kod = item.get("kod") or item.get("code") or item.get("id") or ""
                    nazev = item.get("nazev") or item.get("name") or ""
                    value = f"{kod} – {nazev}".strip(" –")
            else:
                value = str(item)

            if value:
                values.append(value)

        return czech_sorted(values)

    def statni_obcanstvi(self) -> list[str]:
        return self._items_to_display("statni_obcanstvi.json")

    def cz_isco(self) -> list[str]:
        return self._items_to_display("cz_isco.json")

    def druh_zraneni(self) -> list[str]:
        return self._items_to_display("suip_druh_zraneni.json")

    def zranena_cast_tela(self) -> list[str]:
        return self._items_to_display("suip_zranena_cast_tela.json")

    def cinnost_pri_urazu(self) -> list[str]:
        return self._items_to_display("suip_cinnost_pri_urazu.json")


    def charakteristika_pracoviste(self) -> list[str]:
        return self._items_to_display("suip_charakteristika_pracoviste.json")

    def zdroj_urazu(self) -> list[str]:
        return self._items_to_display("suip_zdroj_urazu.json")

    def pricina_urazu(self) -> list[str]:
        return self._items_to_display("suip_pricina_urazu.json")

    def okresy(self) -> list[str]:
        values = self._items_to_display("okresy.json")
        if values:
            return values

        return czech_sorted([
            "Benešov", "Beroun", "Blansko", "Brno-město", "Brno-venkov", "Bruntál",
            "Břeclav", "Česká Lípa", "České Budějovice", "Český Krumlov",
            "Děčín", "Domažlice", "Frýdek-Místek", "Havlíčkův Brod",
            "Hodonín", "Hradec Králové", "Cheb", "Chomutov", "Chrudim",
            "Jablonec nad Nisou", "Jeseník", "Jičín", "Jihlava",
            "Jindřichův Hradec", "Karlovy Vary", "Karviná", "Kladno",
            "Klatovy", "Kolín", "Kroměříž", "Kutná Hora", "Liberec",
            "Litoměřice", "Louny", "Mělník", "Mladá Boleslav", "Most",
            "Náchod", "Nový Jičín", "Nymburk", "Olomouc", "Opava",
            "Ostrava-město", "Pardubice", "Pelhřimov", "Písek", "Plzeň-jih",
            "Plzeň-město", "Plzeň-sever", "Praha", "Praha-východ",
            "Praha-západ", "Prachatice", "Prostějov", "Přerov", "Příbram",
            "Rakovník", "Rokycany", "Rychnov nad Kněžnou", "Semily",
            "Sokolov", "Strakonice", "Svitavy", "Šumperk", "Tábor",
            "Tachov", "Teplice", "Trutnov", "Třebíč", "Uherské Hradiště",
            "Ústí nad Labem", "Ústí nad Orlicí", "Vsetín", "Vyškov",
            "Žďár nad Sázavou", "Zlín", "Znojmo",
        ])

    def zdravotni_pojistovny(self) -> list[str]:
        return [
            "",
            "111 – Všeobecná zdravotní pojišťovna České republiky",
            "201 – Vojenská zdravotní pojišťovna České republiky",
            "205 – Česká průmyslová zdravotní pojišťovna",
            "207 – Oborová zdravotní pojišťovna zaměstnanců bank, pojišťoven a stavebnictví",
            "209 – Zaměstnanecká pojišťovna Škoda",
            "211 – Zdravotní pojišťovna ministerstva vnitra České republiky",
            "213 – Revírní bratrská pokladna, zdravotní pojišťovna",
        ]

    def vztahy_k_zamestnavateli(self) -> list[str]:
        return [
            "",
            "V pracovním poměru",
            "Dohoda o provedení práce",
            "Dohoda o pracovní činnosti",
            "Zaměstnavatel, který je fyzickou osobou a sám též pracuje",
            "Fyzická osoba, která provozuje samostatně výdělečnou činnost podle zvláštního právního předpisu",
            "Spolupracující manžel(ka) nebo dítě osoby uvedené v písmenu a) nebo b)",
            "Fyzická nebo právnická osoba, která je zadavatelem stavby nebo jejím zhotovitelem, popřípadě se na zhotovení stavby podílí",
            "Další členové rodiny, kteří jsou zúčastněni na provozu rodinného závodu podle zvláštního právního předpisu",
            "Ostatní",
        ]

    def druhy_urazu(self) -> list[str]:
        return [
            "",
            "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny",
            "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            "smrtelný",
        ]


kniha_urazu_ciselnik_service = KnihaUrazuCiselnikService()
