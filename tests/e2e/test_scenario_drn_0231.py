"""Scénario de référence de bout en bout, par l'API, sur l'environnement Docker Compose.

Prérequis : `docker compose up -d` (ou CANDRONEX_BASE_URL vers une instance démarrée).
Les identifiants du drone sont générés à chaque exécution pour que le test soit rejouable
sans réinitialiser la base; le déroulement est celui du scénario DRN-0231.
"""

from __future__ import annotations

import os
import random
import time
import uuid

import pytest

requests = pytest.importorskip("requests")

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("CANDRONEX_BASE_URL", "http://localhost:8000")
CLIENT_1 = {"Authorization": "Bearer demo-token-inspectra"}
CLIENT_2 = {"Authorization": "Bearer demo-token-other"}
TERMINAL = {"COMPLETED", "FAILED"}


@pytest.fixture(scope="module", autouse=True)
def environment_is_up():
    try:
        requests.get(f"{BASE_URL}/health", timeout=3)
    except requests.RequestException:
        pytest.skip(f"Environnement non démarré à {BASE_URL} (docker compose up -d).")


def _new_drone() -> dict:
    n = random.randint(10_000, 99_999)
    return {
        "droneId": f"DRN-{n}",
        "imsi": f"9997000000{n:05d}",
        "sim": {"type": "ESIM", "iccid": f"89997000000000{n:05d}"},
    }


def _order_body(drone_id: str) -> dict:
    return {
        "items": [
            {"action": "add", "droneId": drone_id, "serviceType": "C2"},
            {"action": "add", "droneId": drone_id, "serviceType": "IMAGERY"},
        ]
    }


def test_sante_et_authentification():
    health = requests.get(f"{BASE_URL}/health", timeout=5)
    assert health.status_code == 200
    assert health.json() == {"status": "UP", "database": "UP"}

    refused = requests.post(f"{BASE_URL}/drones", json=_new_drone(), timeout=5)
    assert refused.status_code == 401
    assert refused.headers["content-type"].startswith("application/problem+json")


def test_scenario_complet():
    drone = _new_drone()

    # UC-02 : enregistrer le drone
    created = requests.post(f"{BASE_URL}/drones", json=drone, headers=CLIENT_1, timeout=5)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "ACTIVE"
    assert drone["imsi"] not in created.text and drone["sim"]["iccid"] not in created.text
    assert "X-Correlation-Id" in created.headers

    duplicate = requests.post(f"{BASE_URL}/drones", json=drone, headers=CLIENT_1, timeout=5)
    assert duplicate.status_code == 409

    invalid = requests.post(
        f"{BASE_URL}/drones", json={**drone, "imsi": "123"}, headers=CLIENT_1, timeout=5
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_INPUT"

    # UC-04 : commander C2 + Imagerie
    key = {"Idempotency-Key": str(uuid.uuid4())}
    order = requests.post(
        f"{BASE_URL}/service-orders",
        json=_order_body(drone["droneId"]),
        headers={**CLIENT_1, **key},
        timeout=5,
    )
    assert order.status_code == 201, order.text
    order_json = order.json()
    assert [i["serviceType"] for i in order_json["items"]] == ["C2", "IMAGERY"]
    assert order.headers["Location"] == f"/service-orders/{order_json['id']}"

    # Rejeu identique : même commande, aucune création
    replay = requests.post(
        f"{BASE_URL}/service-orders",
        json=_order_body(drone["droneId"]),
        headers={**CLIENT_1, **key},
        timeout=5,
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == order_json["id"]

    # Même clé, contenu différent
    reused = requests.post(
        f"{BASE_URL}/service-orders",
        json={"items": _order_body(drone["droneId"])["items"][:1]},
        headers={**CLIENT_1, **key},
        timeout=5,
    )
    assert reused.status_code == 422
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    # Isolation entre clients
    other = requests.get(
        f"{BASE_URL}/service-orders/{order_json['id']}", headers=CLIENT_2, timeout=5
    )
    assert other.status_code == 404
    foreign_drone = requests.post(
        f"{BASE_URL}/service-orders",
        json=_order_body("DRN-0500"),
        headers={**CLIENT_1, "Idempotency-Key": str(uuid.uuid4())},
        timeout=5,
    )
    assert foreign_drone.status_code == 422
    assert foreign_drone.json()["code"] == "DRONE_NOT_ELIGIBLE"

    # Suivi jusqu'à l'état final (simulation)
    deadline = time.time() + 60
    while time.time() < deadline:
        current = requests.get(
            f"{BASE_URL}/service-orders/{order_json['id']}", headers=CLIENT_1, timeout=5
        ).json()
        if current["state"] in TERMINAL:
            break
        time.sleep(1)
    assert current["state"] in TERMINAL
    assert all(item["state"] in TERMINAL for item in current["items"])
