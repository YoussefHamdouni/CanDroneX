# CanDroneX — Phase 1 (monolithe modulaire)

Plateforme B2B qui permet à des exploitants de drones d'enregistrer leurs drones et de
commander les services de connectivité 5G dont ils ont besoin (C2 / URLLC et Imagerie / eMBB).

Ce dépôt contient le prototype de la Phase 1 du projet LOG430 : un monolithe modulaire en
Python (FastAPI, SQLAlchemy, PostgreSQL, Alembic), démarré par Docker Compose. Il implémente
**UC-02** (enregistrer un drone) et **UC-04** (commander les services d'un drone). L'activation
réelle sur le réseau 5G (UC-06) est hors périmètre : le cycle de vie des éléments de commande
est **simulé**, sans aucun appel réseau.

## Démarrer

```bash
cp .env.example .env          # une seule fois
docker compose up --build
```

Cette commande construit l'image, démarre PostgreSQL, applique les migrations (schéma et
données de démonstration) et sert l'API sur <http://localhost:8000>.
La documentation interactive de l'API est disponible sur <http://localhost:8000/docs>.

| Action | Commande |
| --- | --- |
| Arrêter | `docker compose down` |
| Réinitialiser les données | `docker compose down -v` puis `docker compose up --build` |
| Suivre les journaux | `docker compose logs -f app` |

## Vérifier le démarrage

```bash
docker compose ps                        # app et db : running (healthy)
curl http://localhost:8000/health        # {"status":"UP","database":"UP"}
curl -i -X POST http://localhost:8000/drones   # 401 : l'authentification est active
```

## Données de démonstration

| Donnée | Valeur |
| --- | --- |
| Client 1 | `CUSTOMER-001`, Inspectra Drone Services — jeton `demo-token-inspectra` |
| Client 2 | `CUSTOMER-002`, exploitant fictif — jeton `demo-token-other` |
| Drone du client 2 | `DRN-0500` (sert à démontrer l'isolation entre clients) |
| Catalogue | `C2` (sst 2, sd 000001, dnn c2, 5QI 7, ARP 2, 20/20 Mbps) et `IMAGERY` (sst 1, sd 000002, dnn imagery, 5QI 9, ARP 8, 500/100 Mbps) |

Les jetons sont stockés hachés; leur valeur en clair n'est donnée ici que pour la démonstration.
Les IMSI utilisent le PLMN d'essai 999-70.

## Scénario de référence DRN-0231

```bash
TOKEN="Authorization: Bearer demo-token-inspectra"

# 1. Enregistrer le drone (UC-02) -> 201
curl -s -X POST http://localhost:8000/drones -H "$TOKEN" -H "Content-Type: application/json" \
  -d '{"droneId":"DRN-0231","imsi":"999700000010231","sim":{"type":"ESIM","iccid":"8999700000000102310"}}'

# 2. Commander C2 + Imagerie (UC-04) -> 201, éléments RECEIVED
curl -s -X POST http://localhost:8000/service-orders -H "$TOKEN" -H "Content-Type: application/json" \
  -H "Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7" \
  -d '{"items":[{"action":"add","droneId":"DRN-0231","serviceType":"C2"},{"action":"add","droneId":"DRN-0231","serviceType":"IMAGERY"}]}'

# 3. Rejouer exactement la même requête -> 200, même commande, rien n'est créé

# 4. Suivre la commande -> IN_PROGRESS, puis COMPLETED après le délai de simulation
curl -s http://localhost:8000/service-orders/<id> -H "$TOKEN"
```

Pour démontrer un échec, mettez `SIMULATION_FAILING_SERVICE_TYPES=IMAGERY` dans `.env`, puis
`docker compose up -d` : la commande suivante aura le C2 `COMPLETED`, l'imagerie `FAILED`
(cause `SIMULATED_FAILURE`) et l'état global `FAILED`.

## Points d'entrée

| Méthode | Chemin | Intention |
| --- | --- | --- |
| POST | `/drones` | Enregistrer un drone et son identité réseau (UC-02) |
| POST | `/service-orders` | Créer une commande; en-tête `Idempotency-Key` obligatoire (UC-04) |
| GET | `/service-orders/{orderId}` | Consulter une commande et l'état de chacun de ses éléments |
| GET | `/health` | Vérifier l'application et la base |

Toutes les erreurs suivent le format Problem Details (RFC 9457) avec un `code` stable et le
`correlationId` de la requête.

## Tests

Tout se lance **dans le conteneur `app`**, une fois l'environnement démarré : onglet *Exec*
du conteneur dans Docker Desktop, ou `docker compose exec app sh` depuis un terminal.

```bash
pytest                      # tous les tests : unitaires, architecture, intégration, bout en bout
pytest tests/unit           # règles métier, sans base de données
pytest tests/integration    # dépôts sur une base de test séparée (candronex_test), créée puis supprimée
pytest tests/e2e            # scénario DRN-0231 par l'API en cours d'exécution
lint-imports                # contrats d'architecture déclarés dans pyproject.toml
```

Les tests d'intégration n'utilisent jamais la base de l'application : ils créent une base
`candronex_test` sur le même serveur PostgreSQL, y appliquent les migrations, puis la suppriment.

Sans Docker Compose, sur le poste : `pip install -e ".[dev]"` puis `pytest`. Les tests
d'intégration démarrent alors un PostgreSQL éphémère avec testcontainers (Docker requis).

## Intégration et livraison continues

Le workflow GitHub Actions `.github/workflows/ci.yml` s'exécute à chaque pull request et à
chaque push sur `main` :

1. **Tests unitaires et architecture** : `pytest tests/unit tests/architecture` et `lint-imports`.
2. **Tests dans le conteneur** : `docker compose up --build --wait`, puis `pytest` et
   `lint-imports` dans le conteneur `app`, comme sur un poste.
3. **Publication de l'image** (sur `main` seulement, si tout réussit) :
   `ghcr.io/<propriétaire>/<dépôt>:latest` et `:<sha du commit>`.

Pour qu'un échec bloque la fusion, activer une règle de protection de la branche `main`
(Settings → Branches) qui exige la réussite des deux premiers jobs.

## Organisation du code

```text
src/candronex/
├── shared/      noyau partagé : ClientId, DroneId, CorrelationId, familles d'erreurs
├── platform/    technique transversale : configuration, journaux JSON, base, web
├── identity/    identification des clients B2B
├── fleet/       drones et identité réseau (seul détenteur de l'IMSI et de l'ICCID)
├── catalog/     spécifications des services
├── ordering/    commandes, idempotence, cycle de vie simulé
├── audit/       consignation des opérations importantes
├── container.py racine de composition (ports -> adaptateurs)
└── main.py      application FastAPI
```

Chaque module suit la même structure : `api.py` (interface publiée, seul point d'accès pour
les autres modules), `domain/` (Python standard, sans dépendance technique), `application/`
(cas d'utilisation et ports) et `adapter/inbound` / `adapter/outbound` (REST, SQLAlchemy,
simulation).
