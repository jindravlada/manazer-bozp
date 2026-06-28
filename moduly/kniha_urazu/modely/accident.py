from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Accident(Base):
    """
    Kniha úrazů 3.0 – evidenční část podle KÚ 2.5.

    Poznámka:
    Pole employee_first_name / employee_last_name / description atd. zůstávají
    kvůli kompatibilitě s první testovací verzí tabulky accidents.
    UI používá nové pole jmeno_prijmeni a české názvy.
    """

    __tablename__ = "accidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    number: Mapped[str] = mapped_column(String(30), default="")
    year: Mapped[int] = mapped_column(Integer, default=lambda: date.today().year)

    # Legacy pole z prvního základu KÚ 3.0 – neodstraňovat bez migrace DB
    employee_first_name: Mapped[str] = mapped_column(String(100), default="")
    employee_last_name: Mapped[str] = mapped_column(String(100), default="")
    employee_personal_number: Mapped[str] = mapped_column(String(50), default="")
    injury_type: Mapped[str] = mapped_column(String(250), default="")
    injured_body_part: Mapped[str] = mapped_column(String(250), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    measures_summary: Mapped[str] = mapped_column(Text, default="")

    # Podatel / zaměstnavatel
    datum_zapisu: Mapped[date | None] = mapped_column(Date, nullable=True)
    podatel_jmeno: Mapped[str] = mapped_column(String(150), default="")
    podatel_email: Mapped[str] = mapped_column(String(150), default="")
    podatel_telefon: Mapped[str] = mapped_column(String(80), default="")
    podatel_pracovni_zarazeni: Mapped[str] = mapped_column(String(150), default="")
    zamestnavatel_nazev: Mapped[str] = mapped_column(String(250), default="")
    zamestnavatel_ico: Mapped[str] = mapped_column(String(20), default="")
    zamestnavatel_adresa: Mapped[str] = mapped_column(Text, default="")
    vrchni_dozor: Mapped[str] = mapped_column(String(150), default="")
    hlavni_cinnost_zamestnavatele: Mapped[str] = mapped_column(String(250), default="")

    # Další zaměstnavatel
    dalsi_zamestnavatel_typ: Mapped[str] = mapped_column(String(150), default="")
    dalsi_zamestnavatel_nazev: Mapped[str] = mapped_column(String(250), default="")
    dalsi_zamestnavatel_ico: Mapped[str] = mapped_column(String(20), default="")
    dalsi_zamestnavatel_adresa: Mapped[str] = mapped_column(Text, default="")
    dalsi_zamestnavatel_cinnost: Mapped[str] = mapped_column(String(250), default="")
    dalsi_zamestnavatel_poznamka: Mapped[str] = mapped_column(Text, default="")

    # Zaměstnanec
    jmeno_prijmeni: Mapped[str] = mapped_column(String(200), default="")
    pohlavi: Mapped[str] = mapped_column(String(20), default="")
    datum_narozeni: Mapped[date | None] = mapped_column(Date, nullable=True)
    osobni_cislo: Mapped[str] = mapped_column(String(50), default="")
    statni_obcanstvi: Mapped[str] = mapped_column(String(100), default="Česko")
    adresa_pobytu: Mapped[str] = mapped_column(Text, default="")
    adresa_dorucovani: Mapped[str] = mapped_column(Text, default="")
    telefon_email: Mapped[str] = mapped_column(String(200), default="")
    zdravotni_pojistovna: Mapped[str] = mapped_column(String(150), default="")
    vztah_k_zamestnavateli: Mapped[str] = mapped_column(String(250), default="")
    vztah_k_zamestnavateli_detail: Mapped[str] = mapped_column(Text, default="")
    den_vzniku_pravniho_vztahu: Mapped[date | None] = mapped_column(Date, nullable=True)
    druh_vykonavane_prace: Mapped[str] = mapped_column(String(250), default="")
    cz_isco_kod: Mapped[str] = mapped_column(String(50), default="")
    cz_isco_nazev: Mapped[str] = mapped_column(String(250), default="")
    dpn_od: Mapped[date | None] = mapped_column(Date, nullable=True)
    dpn_do: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Úraz
    druh_urazu: Mapped[str] = mapped_column(String(80), default="")
    podezreni_trestny_cin: Mapped[str] = mapped_column(String(20), default="")
    accident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accident_time: Mapped[str] = mapped_column(String(10), default="")
    druh_zraneni: Mapped[str] = mapped_column(Text, default="")
    zranena_cast_tela: Mapped[str] = mapped_column(Text, default="")
    hromadny_uraz: Mapped[str] = mapped_column(String(20), default="")
    celkovy_pocet_zranenych: Mapped[int] = mapped_column(Integer, default=1)
    cinnost_pri_urazu: Mapped[str] = mapped_column(String(250), default="")
    misto_urazu: Mapped[str] = mapped_column(Text, default="")
    popis_urazoveho_deje: Mapped[str] = mapped_column(Text, default="")
    druh_a_rozsah_zraneni: Mapped[str] = mapped_column(Text, default="")

    # Pracoviště
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")
    pracoviste: Mapped[str] = mapped_column(String(250), default="")
    charakteristika_pracoviste: Mapped[str] = mapped_column(Text, default="")
    zdroj_urazu: Mapped[str] = mapped_column(Text, default="")
    pricina_urazu: Mapped[str] = mapped_column(Text, default="")
    uraz_pracoviste_zamestnavatele: Mapped[str] = mapped_column(String(20), default="")
    subjekt_registrovan: Mapped[str] = mapped_column(String(20), default="")
    ico_subjektu: Mapped[str] = mapped_column(String(20), default="")
    adresa_sidla_subjektu: Mapped[str] = mapped_column(Text, default="")
    ekonomicka_cinnost_subjektu: Mapped[str] = mapped_column(String(250), default="")
    ekonomicka_cinnost_pracoviste: Mapped[str] = mapped_column(String(250), default="")
    adresa_pracoviste: Mapped[str] = mapped_column(Text, default="")
    okres_pracoviste: Mapped[str] = mapped_column(String(120), default="")
    popis_pracoviste: Mapped[str] = mapped_column(Text, default="")

    # Další údaje
    kontrola_alkohol: Mapped[str] = mapped_column(String(20), default="")
    kontrola_alkohol_duvod_neprovedeni: Mapped[str] = mapped_column(Text, default="")
    vysledek_kontroly_alkohol: Mapped[str] = mapped_column(String(50), default="")
    mnozstvi_alkohol: Mapped[str] = mapped_column(String(50), default="")
    kontrola_navykove_latky: Mapped[str] = mapped_column(String(20), default="")
    kontrola_navykove_latky_duvod_neprovedeni: Mapped[str] = mapped_column(Text, default="")
    vysledek_kontroly_navykove_latky: Mapped[str] = mapped_column(String(50), default="")
    navykove_latky_popis: Mapped[str] = mapped_column(Text, default="")
    porusene_predpisy: Mapped[str] = mapped_column(Text, default="")
    opatreni: Mapped[str] = mapped_column(Text, default="")

    # Svědci / podpisy
    svedci: Mapped[str] = mapped_column(Text, default="")
    vyjadreni_svedku: Mapped[str] = mapped_column(Text, default="")
    vyjadreni_oo: Mapped[str] = mapped_column(Text, default="")
    zapsal_jmeno: Mapped[str] = mapped_column(String(150), default="")
    zapsal_pracovni_zarazeni: Mapped[str] = mapped_column(String(150), default="")
    poznamka: Mapped[str] = mapped_column(Text, default="")

    investigation_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def employee_name(self) -> str:
        return self.jmeno_prijmeni.strip() or " ".join(
            part for part in [self.employee_last_name, self.employee_first_name] if part
        ).strip()

    @property
    def status(self) -> str:
        return "Uzavřeno" if self.closed else "Rozpracováno"
