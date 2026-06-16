# ruff: noqa: E402,I001
"""Inspect ProductRepository contract for Phase 3-I-I 50-case evaluation."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


CANDIDATE_MODULES: Final[tuple[str, ...]] = (
    "app.products.repository",
    "app.product.repository",
    "app.repositories.product_repository",
    "app.repositories.products",
    "app.agent.repositories.product_repository",
    "app.agent.product_repository",
    "app.agent.workflow",
)

CANDIDATE_CLASS_NAMES: Final[tuple[str, ...]] = (
    "ProductRepository",
    "InMemoryProductRepository",
    "PostgresProductRepository",
    "SQLAlchemyProductRepository",
    "DatabaseProductRepository",
)

CANDIDATE_FACTORY_NAMES: Final[tuple[str, ...]] = (
    "build_product_repository",
    "get_product_repository",
    "create_product_repository",
)


def main() -> int:
    """Inspect product repository contract."""

    print("=" * 80)
    print("inspecting Phase 3-I-I workflow repository contract")

    errors: list[str] = []

    module_results = inspect_candidate_modules()
    project_search_result = search_project_for_repository_symbols()
    constructor_result = inspect_repository_constructors(module_results)
    factory_result = inspect_repository_factories(module_results)

    result = {
        "module_results": module_results,
        "project_search_result": project_search_result,
        "constructor_result": constructor_result,
        "factory_result": factory_result,
        "errors": errors,
    }

    pprint(result)

    if not constructor_result["classes"] and not factory_result["factories"]:
        errors.append("no ProductRepository class or factory found")

    if errors:
        result["errors"] = errors
        pprint(result)
        print("Phase 3-I-I workflow repository contract inspection failed")
        return 1

    print("Phase 3-I-I workflow repository contract inspection passed")
    return 0


def inspect_candidate_modules() -> list[dict[str, Any]]:
    """Import candidate modules and inspect public symbols."""

    results: list[dict[str, Any]] = []

    for module_name in CANDIDATE_MODULES:
        module_result: dict[str, Any] = {
            "module": module_name,
            "imported": False,
            "error": None,
            "file": None,
            "candidate_classes": [],
            "candidate_factories": [],
        }

        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            module_result["error"] = f"{type(exc).__name__}: {exc}"
            results.append(module_result)
            continue

        module_result["imported"] = True
        module_file = getattr(module, "__file__", None)

        if isinstance(module_file, str):
            module_result["file"] = str(Path(module_file).relative_to(BACKEND_ROOT))

        module_result["candidate_classes"] = [
            name
            for name in CANDIDATE_CLASS_NAMES
            if hasattr(module, name)
        ]
        module_result["candidate_factories"] = [
            name
            for name in CANDIDATE_FACTORY_NAMES
            if hasattr(module, name)
        ]

        results.append(module_result)

    return results


def inspect_repository_constructors(
    module_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Inspect found repository class constructors."""

    classes: list[dict[str, Any]] = []

    for module_result in module_results:
        if not module_result["imported"]:
            continue

        module = importlib.import_module(str(module_result["module"]))

        for class_name in module_result["candidate_classes"]:
            cls = getattr(module, class_name)

            classes.append(
                {
                    "module": module_result["module"],
                    "class_name": class_name,
                    "signature": str(inspect.signature(cls)),
                    "methods": inspect_public_methods(cls),
                }
            )

    return {
        "classes": classes,
    }


def inspect_repository_factories(
    module_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Inspect found repository factories."""

    factories: list[dict[str, Any]] = []

    for module_result in module_results:
        if not module_result["imported"]:
            continue

        module = importlib.import_module(str(module_result["module"]))

        for factory_name in module_result["candidate_factories"]:
            factory = getattr(module, factory_name)

            factories.append(
                {
                    "module": module_result["module"],
                    "factory_name": factory_name,
                    "signature": str(inspect.signature(factory)),
                }
            )

    return {
        "factories": factories,
    }


def inspect_public_methods(
    cls: object,
) -> list[str]:
    """Inspect public method signatures."""

    methods: list[str] = []

    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue

        if not callable(member):
            continue

        try:
            signature = str(inspect.signature(member))
        except (TypeError, ValueError):
            signature = "(signature unavailable)"

        methods.append(f"{name}{signature}")

    return methods[:30]


def search_project_for_repository_symbols() -> list[dict[str, Any]]:
    """Search source files for ProductRepository symbols."""

    matches: list[dict[str, Any]] = []

    for path in sorted((BACKEND_ROOT / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue

        content = path.read_text(encoding="utf-8")

        if "ProductRepository" not in content:
            continue

        lines: list[str] = []

        for line_number, line in enumerate(content.splitlines(), start=1):
            if "ProductRepository" in line:
                lines.append(f"{line_number}: {line.strip()}")

        matches.append(
            {
                "path": str(path.relative_to(BACKEND_ROOT)),
                "matches": lines[:20],
            }
        )

    return matches


if __name__ == "__main__":
    raise SystemExit(main())