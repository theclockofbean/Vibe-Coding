"""Check LangGraph installation.

This script verifies that langgraph is installed and that the basic StateGraph
API can be imported and compiled.

It does not call an LLM, generate customer-facing answers, promise prices,
promise logistics, promise quality, promise warranty, promise returns/exchanges,
or create business commitments.
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
from typing import Any


def check_package_version() -> bool:
    """Check langgraph package version."""

    print("=" * 80)
    print("checking langgraph package version")

    try:
        version = metadata.version("langgraph")
    except metadata.PackageNotFoundError:
        print("failed: langgraph is not installed")
        print("install command:")
        print("python -m pip install langgraph")
        return False

    print(f"langgraph version: {version}")
    return True


def check_graph_imports() -> bool:
    """Check core LangGraph graph imports."""

    print("=" * 80)
    print("checking langgraph.graph imports")

    try:
        graph_module = importlib.import_module("langgraph.graph")
    except ImportError as exc:
        print("failed: cannot import langgraph.graph")
        print(repr(exc))
        return False

    required_names = [
        "StateGraph",
        "START",
        "END",
    ]

    missing_names = [
        name
        for name in required_names
        if not hasattr(graph_module, name)
    ]

    if missing_names:
        print("failed: missing required graph exports")
        for name in missing_names:
            print(f"- {name}")
        return False

    print("langgraph.graph imports passed")
    return True


def check_minimal_workflow_compile() -> bool:
    """Check a minimal StateGraph can be compiled and invoked."""

    print("=" * 80)
    print("checking minimal StateGraph compile/invoke")

    graph_module = importlib.import_module("langgraph.graph")

    state_graph = graph_module.StateGraph
    start = graph_module.START
    end = graph_module.END

    def passthrough_node(state: dict[str, Any]) -> dict[str, Any]:
        return {
            **state,
            "visited": True,
        }

    try:
        workflow = state_graph(dict)
        workflow.add_node("passthrough", passthrough_node)
        workflow.add_edge(start, "passthrough")
        workflow.add_edge("passthrough", end)

        compiled = workflow.compile()
        result = compiled.invoke(
            {
                "input": "ping",
            }
        )
    except Exception as exc:  # noqa: BLE001
        print("failed: minimal LangGraph workflow failed")
        print(repr(exc))
        return False

    print("minimal workflow result:")
    print(result)

    if result.get("visited") is not True:
        print("failed: minimal workflow did not return expected state")
        return False

    print("minimal StateGraph compile/invoke passed")
    return True


def main() -> int:
    """Run LangGraph installation checks."""

    results = [
        check_package_version(),
        check_graph_imports(),
        check_minimal_workflow_compile(),
    ]

    print("=" * 80)

    if not all(results):
        print("langgraph installation check failed")
        return 1

    print("langgraph installation check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())