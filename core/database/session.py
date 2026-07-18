from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.base import Base
from core.services.storage_service import storage_service


DATABASE_URL = f"sqlite:///{storage_service.database_path}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def create_database() -> None:
    storage_service.ensure_structure()
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()


def dispose_database_engine() -> None:
    """
    Uvolní všechna připojení SQLAlchemy engine.

    Volat před atomickou obnovou workspace (přejmenování databázového souboru).
    """
    engine.dispose()
