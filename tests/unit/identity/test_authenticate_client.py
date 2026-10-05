import uuid

import pytest

from candronex.identity.api import AuthenticationFailed
from candronex.identity.application.authenticate_client import (
    ClientAuthenticationService,
)
from candronex.identity.domain.b2b_client import (
    ApiCredential,
    B2BClient,
    ClientStatus,
    CredentialStatus,
    hash_token,
)
from candronex.shared.ids import ClientId
from tests.unit.fakes import InMemoryIdentityUnitOfWork, RecordingAuditLog


def _service(audit=None):
    clients = [
        B2BClient(ClientId("CUSTOMER-001"), "Inspectra", ClientStatus.ACTIVE),
        B2BClient(ClientId("CUSTOMER-003"), "Suspendu", ClientStatus.SUSPENDED),
    ]
    credentials = [
        ApiCredential(
            uuid.uuid4(), ClientId("CUSTOMER-001"), hash_token("good"), CredentialStatus.ACTIVE
        ),
        ApiCredential(
            uuid.uuid4(), ClientId("CUSTOMER-001"), hash_token("revoked"), CredentialStatus.REVOKED
        ),
        ApiCredential(
            uuid.uuid4(), ClientId("CUSTOMER-003"), hash_token("suspended"), CredentialStatus.ACTIVE
        ),
    ]
    return ClientAuthenticationService(
        lambda: InMemoryIdentityUnitOfWork(credentials, clients), audit or RecordingAuditLog()
    )


def test_un_jeton_valide_identifie_le_client():
    assert _service().authenticate("good") == ClientId("CUSTOMER-001")


def test_les_jetons_absents_inconnus_revoques_ou_de_client_suspendu_sont_refuses_et_consignes():
    audit = RecordingAuditLog()
    service = _service(audit)
    for token in ["", "unknown", "revoked", "suspended"]:
        with pytest.raises(AuthenticationFailed):
            service.authenticate(token, "corr-1")
    assert audit.actions == ["ACCESS_DENIED"] * 4
    assert all(r.correlation_id == "corr-1" for r in audit.records)
    assert "revoked" not in repr(audit.records)  # le jeton n'est jamais consigné


def test_seul_le_hachage_du_jeton_est_conserve():
    assert hash_token("good") != "good"
    assert len(hash_token("good")) == 64
