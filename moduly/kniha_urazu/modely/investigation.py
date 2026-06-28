from datetime import datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AccidentInvestigation(Base):
    __tablename__ = "accident_investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accident_id: Mapped[int] = mapped_column(Integer, index=True, unique=True)

    # Oznámení
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

    # Zajištění důkazů
    zajisteni_dukazu_json: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
