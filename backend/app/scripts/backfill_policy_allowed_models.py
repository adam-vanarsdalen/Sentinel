from __future__ import annotations

from app.db.session import SessionLocal
from app.services.policy_model_sync import backfill_all_tenant_policy_allowed_models


def main() -> None:
    db = SessionLocal()
    try:
        stats = backfill_all_tenant_policy_allowed_models(db)
        print(
            "Backfill complete:",
            f"tenant_policies={stats['updated_policy_rows']}",
            f"active_policy_versions={stats['updated_active_policy_versions']}",
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
