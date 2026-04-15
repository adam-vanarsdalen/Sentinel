from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.request_context import get_request_id, get_tenant_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = get_request_id() or getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        tenant_id = get_tenant_id() or getattr(record, "tenant_id", None)
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
