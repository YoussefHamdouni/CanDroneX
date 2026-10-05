"""Schéma du module Catalog.

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE catalog.service_specification (
    service_type  VARCHAR(32)   PRIMARY KEY CONSTRAINT ck_service_specification_type CHECK (service_type ~ '^[A-Z0-9_]{1,32}$'),
    name          VARCHAR(100)  NOT NULL
);

CREATE TABLE catalog.service_characteristic (
    service_type  VARCHAR(32)   NOT NULL REFERENCES catalog.service_specification (service_type),
    name          VARCHAR(64)   NOT NULL,
    value_text    VARCHAR(100)  NOT NULL,
    value_type    VARCHAR(8)    NOT NULL CONSTRAINT ck_service_characteristic_value_type CHECK (value_type IN ('int', 'str')),
    position      INTEGER       NOT NULL,
    PRIMARY KEY (service_type, name)
);
"""

DOWNGRADE = "DROP SCHEMA catalog CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
