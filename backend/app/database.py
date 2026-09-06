from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_db() -> Session:
    """Dependency that provides a SQLAlchemy session.

    FastAPI uses this as ``Depends(get_db)`` to obtain a DB session.
    The caller is responsible for closing the session (FastAPI's
    ``try / finally`` pattern handles this automatically when used
    as a dependency).
    """
    db = Session(engine)
    return db
