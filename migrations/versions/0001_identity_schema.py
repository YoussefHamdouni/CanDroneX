"""Schéma du module Identity & Access.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS identity;

CREATE TABLE identity.b2b_client (
    client_id   VARCHAR(64)  PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    status      VARCHAR(16)  NOT NULL CONSTRAINT ck_b2b_client_status CHECK (status IN ('ACTIVE', 'SUSPENDED')),
    created_at  TIMESTAMPTZ  NOT NULL
);

CREATE TABLE identity.api_credential (
    id          UUID         PRIMARY KEY,
    client_id   VARCHAR(64)  NOT NULL REFERENCES identity.b2b_client (client_id),
    token_hash  CHAR(64)     NOT NULL CONSTRAINT uq_api_credential_token_hash UNIQUE,
    status      VARCHAR(16)  NOT NULL CONSTRAINT ck_api_credential_status CHECK (status IN ('ACTIVE', 'REVOKED')),
    created_at  TIMESTAMPTZ  NOT NULL
);
"""

DOWNGRADE = "DROP SCHEMA identity CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
