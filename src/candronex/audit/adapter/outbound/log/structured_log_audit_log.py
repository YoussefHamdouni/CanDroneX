"""Phase 1 : l'audit passe par la journalisation structurée.

Une table en ajout seul la remplacera avec UC-12, sans changer l'interface AuditLog.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from candronex.audit.api import AuditRecord

log = logging.getLogger("candronex.audit")


class StructuredLogAuditLog:
    def record(self, record: AuditRecord) -> None:
        log.info(
            "[audit] %s",
            record.action,
            extra={
                "fields": {
                    "audit": {
                        "action": record.action,
                        "actorId": record.actor_id,
                        "resourceType": record.resource_type,
                        "resourceId": record.resource_id,
                        "correlationId": record.correlation_id,
                        "recordedAt": datetime.now(timezone.utc).isoformat(),
                        "details": dict(record.details),
                    }
                }
            },
        )
