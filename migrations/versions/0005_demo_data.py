"""Données de démonstration : clients, jetons, catalogue et un drone du client 2.

Les jetons sont stockés hachés (SHA-256). Leur valeur en clair n'est documentée que
dans le README, à des fins de démonstration. Les IMSI utilisent le PLMN d'essai 999-70.

Revision ID: 0005
"""

import hashlib

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DEMO_TOKENS = {
    "CUSTOMER-001": "demo-token-inspectra",
    "CUSTOMER-002": "demo-token-other",
}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def upgrade_sql() -> str:
    return f"""
INSERT INTO identity.b2b_client (client_id, name, status, created_at) VALUES
    ('CUSTOMER-001', 'Inspectra Drone Services', 'ACTIVE', now()),
    ('CUSTOMER-002', 'Exploitant fictif (démonstration de l''isolation)', 'ACTIVE', now());

INSERT INTO identity.api_credential (id, client_id, token_hash, status, created_at) VALUES
    ('00000000-0000-4000-8000-000000000001', 'CUSTOMER-001', '{_hash(DEMO_TOKENS["CUSTOMER-001"])}', 'ACTIVE', now()),
    ('00000000-0000-4000-8000-000000000002', 'CUSTOMER-002', '{_hash(DEMO_TOKENS["CUSTOMER-002"])}', 'ACTIVE', now());

INSERT INTO catalog.service_specification (service_type, name) VALUES
    ('C2', 'C&C Connectivity'),
    ('IMAGERY', 'Imagery Connectivity');

INSERT INTO catalog.service_characteristic (service_type, name, value_text, value_type, position) VALUES
    ('C2', 'sst',          '2',        'int', 0),
    ('C2', 'sd',           '000001',   'str', 1),
    ('C2', 'dnn',          'c2',       'str', 2),
    ('C2', 'fiveQi',       '7',        'int', 3),
    ('C2', 'arp',          '2',        'int', 4),
    ('C2', 'ambrUplink',   '20 Mbps',  'str', 5),
    ('C2', 'ambrDownlink', '20 Mbps',  'str', 6),
    ('IMAGERY', 'sst',          '1',        'int', 0),
    ('IMAGERY', 'sd',           '000002',   'str', 1),
    ('IMAGERY', 'dnn',          'imagery',  'str', 2),
    ('IMAGERY', 'fiveQi',       '9',        'int', 3),
    ('IMAGERY', 'arp',          '8',        'int', 4),
    ('IMAGERY', 'ambrUplink',   '500 Mbps', 'str', 5),
    ('IMAGERY', 'ambrDownlink', '100 Mbps', 'str', 6);

-- Drone du client 2 : sert à démontrer qu'un autre client ne peut pas le commander.
INSERT INTO fleet.drone (id, client_id, drone_id, imsi, iccid, sim_type, status, registered_at) VALUES
    ('00000000-0000-4000-8000-000000000500', 'CUSTOMER-002', 'DRN-0500',
     '999700000010500', '8999700000000105000', 'ESIM', 'ACTIVE', now());
"""


DOWNGRADE = """
DELETE FROM fleet.drone WHERE id = '00000000-0000-4000-8000-000000000500';
DELETE FROM catalog.service_characteristic WHERE service_type IN ('C2', 'IMAGERY');
DELETE FROM catalog.service_specification WHERE service_type IN ('C2', 'IMAGERY');
DELETE FROM identity.api_credential WHERE client_id IN ('CUSTOMER-001', 'CUSTOMER-002');
DELETE FROM identity.b2b_client WHERE client_id IN ('CUSTOMER-001', 'CUSTOMER-002');
"""


def upgrade() -> None:
    op.execute(upgrade_sql())


def downgrade() -> None:
    op.execute(DOWNGRADE)
