from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.database.base import Base
from core.services import storage_service as storage_module


def _database_url() -> str:
    return f"sqlite:///{storage_module.storage_service.database_path}"


DATABASE_URL = _database_url()

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


def reconfigure_database_engine(*, force: bool = False) -> None:
    """Obnoví engine podle aktuálního ``storage_service`` (po reloadu / změně cesty)."""
    global DATABASE_URL, engine, SessionLocal

    desired = _database_url()
    if DATABASE_URL == desired and not force:
        return

    engine.dispose()
    DATABASE_URL = desired
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
    storage_module.storage_service.ensure_structure()
    reconfigure_database_engine()
    Base.metadata.create_all(bind=engine)


def get_session():
    # Vždy čti aktuální singleton storage (po importlib.reload v testech).
    reconfigure_database_engine()
    return SessionLocal()


@contextmanager
def open_session(session: Session | None = None) -> Iterator[tuple[Session, bool]]:
    """Vrátí (session, owns). Vlastní session se při chybě rollbackne a vždy zavře."""
    owns = session is None
    current = get_session() if owns else session
    try:
        yield current, owns
    except Exception:
        if owns:
            current.rollback()
        raise
    finally:
        if owns:
            current.close()


@contextmanager
def transaction() -> Iterator[Session]:
    """Jedna transakce. Commit až po úspěšném bloku, jinak rollback celého bloku."""
    reconfigure_database_engine()
    current = SessionLocal()
    try:
        yield current
        current.commit()
    except Exception:
        current.rollback()
        raise
    finally:
        current.close()


def dispose_database_engine() -> None:
    """
    Uvolní všechna připojení SQLAlchemy engine.

    Volat před atomickou obnovou workspace (přejmenování databázového souboru).
    """
    engine.dispose()
