"""Schéma du module Fleet. Seul schéma qui contient l'IMSI et l'ICCID.

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS fleet;

CREATE TABLE fleet.drone (
    id             UUID         PRIMARY KEY,
    client_id      VARCHAR(64)  NOT NULL,  -- référence vers Identity, sans clé étrangère (ADR-002)
    drone_id       VARCHAR(32)  NOT NULL CONSTRAINT ck_drone_drone_id CHECK (drone_id ~ '^[A-Z0-9-]{3,32}$'),
    imsi           VARCHAR(15)  NOT NULL CONSTRAINT ck_drone_imsi CHECK (imsi ~ '^[0-9]{15}$'),
    iccid          VARCHAR(20)  NOT NULL CONSTRAINT ck_drone_iccid CHECK (iccid ~ '^[0-9]{19,20}$'),
    sim_type       VARCHAR(8)   NOT NULL CONSTRAINT ck_drone_sim_type CHECK (sim_type IN ('SIM', 'ESIM')),
    status         VARCHAR(16)  NOT NULL CONSTRAINT ck_drone_status CHECK (status IN ('ACTIVE', 'SUSPENDED', 'RETIRED')),
    registered_at  TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uq_drone_client_drone_id UNIQUE (client_id, drone_id),
    CONSTRAINT uq_drone_imsi UNIQUE (imsi),
    CONSTRAINT uq_drone_iccid UNIQUE (iccid)
);
"""

DOWNGRADE = "DROP SCHEMA fleet CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
