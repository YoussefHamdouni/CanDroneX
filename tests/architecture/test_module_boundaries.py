"""Règles de frontières entre modules et entre couches (§4.2, §5.3, ADR-001).

Ce test analyse les imports du code source sans l'exécuter : il ne dépend d'aucune
bibliothèque externe. Les mêmes règles sont aussi déclarées pour import-linter
(`lint-imports`, voir pyproject.toml).
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "candronex"
BUSINESS_MODULES = {"identity", "fleet", "catalog", "ordering", "audit"}
TECHNICAL_PACKAGES = {
    "sqlalchemy",
    "fastapi",
    "pydantic",
    "starlette",
    "alembic",
    "psycopg",
    "uvicorn",
}
COMPOSITION_ROOT = {"container.py", "main.py"}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _files():
    for path in SRC.rglob("*.py"):
        relative = path.relative_to(SRC)
        if relative.parts[0] in COMPOSITION_ROOT:
            continue
        yield path, relative


def _module_of(relative: Path) -> str:
    return relative.parts[0].removesuffix(".py")


def _layer_of(relative: Path) -> str | None:
    return relative.parts[1] if len(relative.parts) > 2 else None


def test_le_domaine_et_l_application_ne_dependent_d_aucune_technologie():
    violations = []
    for path, relative in _files():
        if _layer_of(relative) in {"domain", "application"}:
            for name in _imports(path):
                if name.split(".")[0] in TECHNICAL_PACKAGES:
                    violations.append(f"{relative} importe {name}")
    assert not violations, violations


def test_le_domaine_n_importe_que_le_noyau_partage_et_son_propre_domaine():
    violations = []
    for path, relative in _files():
        if _layer_of(relative) != "domain":
            continue
        own = f"candronex.{_module_of(relative)}.domain"
        for name in _imports(path):
            if name.startswith("candronex.") and not (
                name.startswith(own) or name.startswith("candronex.shared")
            ):
                violations.append(f"{relative} importe {name}")
    assert not violations, violations


def test_un_module_n_accede_qu_a_l_interface_publiee_des_autres():
    violations = []
    for path, relative in _files():
        source = _module_of(relative)
        for name in _imports(path):
            parts = name.split(".")
            if parts[0] != "candronex" or len(parts) < 2:
                continue
            target = parts[1]
            if target in BUSINESS_MODULES and target != source:
                if len(parts) < 3 or parts[2] != "api":
                    violations.append(f"{relative} importe {name}")
    assert not violations, violations


def test_la_plateforme_et_le_noyau_ne_dependent_d_aucun_module_metier():
    violations = []
    for path, relative in _files():
        if _module_of(relative) in {"platform", "shared"}:
            for name in _imports(path):
                parts = name.split(".")
                if parts[0] == "candronex" and len(parts) > 1 and parts[1] in BUSINESS_MODULES:
                    violations.append(f"{relative} importe {name}")
    assert not violations, violations


def test_aucun_cycle_de_dependance_entre_modules():
    graph: dict[str, set[str]] = defaultdict(set)
    for path, relative in _files():
        source = _module_of(relative)
        for name in _imports(path):
            parts = name.split(".")
            if parts[0] == "candronex" and len(parts) > 1 and parts[1] != source:
                graph[source].add(parts[1])

    visiting, done = set(), set()

    def visit(node: str, trail: list[str]) -> None:
        if node in done:
            return
        assert node not in visiting, f"cycle : {' -> '.join(trail + [node])}"
        visiting.add(node)
        for neighbour in graph.get(node, ()):
            visit(neighbour, trail + [node])
        visiting.discard(node)
        done.add(node)

    for module in list(graph):
        visit(module, [])


def test_l_imsi_ne_sort_pas_du_module_fleet():
    """Aucun autre module ne manipule l'objet valeur Imsi (Loi 25, LPRPDE)."""
    violations = []
    for path, relative in _files():
        if _module_of(relative) != "fleet" and "Imsi" in path.read_text(encoding="utf-8"):
            violations.append(str(relative))
    assert not violations, violations
