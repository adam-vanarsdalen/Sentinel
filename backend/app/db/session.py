from __future__ import annotations

from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import AuditEvent
from app.services.audit_integrity import assert_append_only, assign_hash_chain_for_new_events

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Session, "before_flush")
def _audit_event_before_flush(session: Session, flush_context, instances) -> None:
    assert_append_only(session)
    new_events = [obj for obj in session.new if isinstance(obj, AuditEvent)]
    if new_events:
        assign_hash_chain_for_new_events(session, new_events)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        # Ensure failed transactions don't poison the session for the rest of the request.
        db.rollback()
        raise
    finally:
        db.close()
