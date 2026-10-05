"""Schéma du module Ordering.

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS ordering;

CREATE TABLE ordering.service_order (
    id                   UUID          PRIMARY KEY,
    client_id            VARCHAR(64)   NOT NULL,
    idempotency_key      VARCHAR(255)  NOT NULL,
    request_fingerprint  CHAR(64)      NOT NULL,
    correlation_id       VARCHAR(128)  NOT NULL,
    status               VARCHAR(16)   NOT NULL CONSTRAINT ck_service_order_status
                                       CHECK (status IN ('RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    version              INTEGER       NOT NULL,
    created_at           TIMESTAMPTZ   NOT NULL,
    updated_at           TIMESTAMPTZ   NOT NULL,
    CONSTRAINT uq_service_order_client_idempotency_key UNIQUE (client_id, idempotency_key)
);

CREATE TABLE ordering.service_order_item (
    id               UUID          PRIMARY KEY,
    order_id         UUID          NOT NULL REFERENCES ordering.service_order (id) ON DELETE CASCADE,
    position         INTEGER       NOT NULL,
    action           VARCHAR(16)   NOT NULL CONSTRAINT ck_service_order_item_action CHECK (action IN ('add')),
    drone_id         VARCHAR(32)   NOT NULL,  -- référence vers Fleet, sans clé étrangère (ADR-002)
    service_type     VARCHAR(32)   NOT NULL,
    status           VARCHAR(16)   NOT NULL CONSTRAINT ck_service_order_item_status
                                   CHECK (status IN ('RECEIVED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'COMPENSATED')),
    failure_code     VARCHAR(64),
    failure_message  VARCHAR(500),
    CONSTRAINT uq_service_order_item_drone_service UNIQUE (order_id, drone_id, service_type),
    CONSTRAINT uq_service_order_item_position UNIQUE (order_id, position),
    CONSTRAINT ck_service_order_item_failure CHECK ((status = 'FAILED') = (failure_code IS NOT NULL))
);

CREATE TABLE ordering.order_item_characteristic (
    item_id     UUID          NOT NULL REFERENCES ordering.service_order_item (id) ON DELETE CASCADE,
    name        VARCHAR(64)   NOT NULL,
    value_text  VARCHAR(100)  NOT NULL,
    value_type  VARCHAR(8)    NOT NULL CONSTRAINT ck_order_item_characteristic_value_type CHECK (value_type IN ('int', 'str')),
    position    INTEGER       NOT NULL,
    PRIMARY KEY (item_id, name)
);
"""

DOWNGRADE = "DROP SCHEMA ordering CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
