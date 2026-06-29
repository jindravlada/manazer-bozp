from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.vysetrovani_mu.constants import (
    DEFAULT_EVENT_CHARACTER,
    DEFAULT_MU_STATUS,
    DEFAULT_SOURCE_TYPE,
)


class MuInvestigation(Base):
    __tablename__ = "mu_investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    number: Mapped[str] = mapped_column(String(30), default="")
    title: Mapped[str] = mapped_column(String(250), default="")
    event_character: Mapped[str] = mapped_column(String(80), default=DEFAULT_EVENT_CHARACTER, nullable=False)

    source_type: Mapped[str] = mapped_column(String(30), default=DEFAULT_SOURCE_TYPE, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_label: Mapped[str] = mapped_column(String(250), default="")

    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=DEFAULT_MU_STATUS, nullable=False)

    lead_thp_worker_id: Mapped[int | None] = mapped_column("lead_person_id", Integer, nullable=True)
    lead_thp_worker_name: Mapped[str] = mapped_column("lead_person_name", String(150), default="")

    short_description: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    ohledani_mista_json: Mapped[str] = mapped_column(Text, default="")
    zajisteni_dukazu_json: Mapped[str] = mapped_column(Text, default="")
    svedci_json: Mapped[str] = mapped_column(Text, default="")
    casova_osa_json: Mapped[str] = mapped_column(Text, default="")

    oznameni_kdo: Mapped[str] = mapped_column(String(200), default="")
    oznameni_komu: Mapped[str] = mapped_column(String(200), default="")
    oznameni_datum = mapped_column(Date, nullable=True)
    oznameni_cas: Mapped[str] = mapped_column(String(20), default="")
    oznameni_bezodkladne: Mapped[str] = mapped_column(String(10), default="")
    oznameni_duvod_pozde: Mapped[str] = mapped_column(Text, default="")
    oznameni_popis: Mapped[str] = mapped_column(Text, default="")

    opatreni_prvni_pomoc: Mapped[str] = mapped_column(String(10), default="")
    opatreni_zzs: Mapped[str] = mapped_column(String(10), default="")
    opatreni_zastavena_cinnost: Mapped[str] = mapped_column(String(10), default="")
    opatreni_zajisteno_misto: Mapped[str] = mapped_column(String(10), default="")
    opatreni_zabraneno_manipulaci: Mapped[str] = mapped_column(String(10), default="")
    opatreni_informovan_nadrizeny: Mapped[str] = mapped_column(String(10), default="")
    opatreni_informovan_bozp: Mapped[str] = mapped_column(String(10), default="")
    oznameni_bozp_datum = mapped_column(Date, nullable=True)
    oznameni_bozp_cas: Mapped[str] = mapped_column(String(20), default="")
    opatreni_informovany_dalsi: Mapped[str] = mapped_column(String(10), default="")

    dalsi_postup: Mapped[str] = mapped_column(String(250), default="")
    dalsi_postup_jiny: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
