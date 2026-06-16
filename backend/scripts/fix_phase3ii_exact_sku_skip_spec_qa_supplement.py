"""Filter unrelated spec_qa supplements for exact SKU grounded answers."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
RENDERER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/rendering/grounded_renderer.py"


HELPERS: Final[str] = '''
def _should_skip_supplemental_rag_for_exact_sku(
    render_input: GroundedRenderInput,
) -> bool:
    """Return whether exact SKU facts should suppress supplemental RAG chunks."""

    answer_text = _optional_text(render_input.answer_text) or ""

    return (
        render_input.selected_module == "spec"
        and "查到 SKU" in answer_text
    )


def _is_spec_qa_supplemental_source(
    value: dict[str, Any],
) -> bool:
    """Return whether source/chunk is a spec QA supplemental item."""

    identifiers = [
        _optional_text(value.get("reference_id")),
        _optional_text(value.get("chunk_id")),
        _optional_text(value.get("doc_id")),
    ]

    return any(
        identifier is not None and identifier.startswith("spec_qa_")
        for identifier in identifiers
    )
'''


OLD_EVIDENCE_FUNC: Final[str] = '''def _build_evidence_lines(
    *,
    render_input: GroundedRenderInput,
    max_items: int,
) -> list[str]:
    """Build supplementary evidence lines from safe RAG chunks."""

    lines: list[str] = []

    for chunk in render_input.retrieved_chunks:
        if chunk.get("allow_answer_reference") is False:
            continue

        summary = _optional_text(chunk.get("summary"))
        content = _optional_text(chunk.get("content"))

        line = summary or content

        if line is None:
            continue

        lines.append(_trim_text(line, max_length=90))

        if len(lines) >= max_items:
            break

    return lines
'''


NEW_EVIDENCE_FUNC: Final[str] = '''def _build_evidence_lines(
    *,
    render_input: GroundedRenderInput,
    max_items: int,
) -> list[str]:
    """Build supplementary evidence lines from safe RAG chunks."""

    lines: list[str] = []
    skip_spec_qa = _should_skip_supplemental_rag_for_exact_sku(render_input)

    for chunk in render_input.retrieved_chunks:
        if chunk.get("allow_answer_reference") is False:
            continue

        if skip_spec_qa and _is_spec_qa_supplemental_source(chunk):
            continue

        summary = _optional_text(chunk.get("summary"))
        content = _optional_text(chunk.get("content"))

        line = summary or content

        if line is None:
            continue

        lines.append(_trim_text(line, max_length=90))

        if len(lines) >= max_items:
            break

    return lines
'''


OLD_SOURCES_FUNC: Final[str] = '''def _build_response_sources(
    render_input: GroundedRenderInput,
) -> list[dict[str, Any]]:
    """Build normalized response sources."""

    sources: list[dict[str, Any]] = []

    for reference in render_input.source_references:
        source = _source_from_reference(reference)

        if source is not None:
            sources.append(source)

    for chunk in render_input.retrieved_chunks:
        chunk_source = _source_from_chunk(chunk)

        if chunk_source is not None:
            sources.append(chunk_source)

    if render_input.business_rules:
        sources.append(
            make_response_source(
                reference_id="render_business_rules",
                source_type="business_rule",
                source_name="GroundedRenderer",
                used_for="business_boundary",
                metadata={
                    "rule_count": len(render_input.business_rules),
                    "rules": list(DEFAULT_RENDER_BUSINESS_RULES),
                },
            )
        )

    return _deduplicate_sources(sources)
'''


NEW_SOURCES_FUNC: Final[str] = '''def _build_response_sources(
    render_input: GroundedRenderInput,
) -> list[dict[str, Any]]:
    """Build normalized response sources."""

    sources: list[dict[str, Any]] = []
    skip_spec_qa = _should_skip_supplemental_rag_for_exact_sku(render_input)

    for reference in render_input.source_references:
        if skip_spec_qa and _is_spec_qa_supplemental_source(reference):
            continue

        source = _source_from_reference(reference)

        if source is not None:
            sources.append(source)

    for chunk in render_input.retrieved_chunks:
        if skip_spec_qa and _is_spec_qa_supplemental_source(chunk):
            continue

        chunk_source = _source_from_chunk(chunk)

        if chunk_source is not None:
            sources.append(chunk_source)

    if render_input.business_rules:
        sources.append(
            make_response_source(
                reference_id="render_business_rules",
                source_type="business_rule",
                source_name="GroundedRenderer",
                used_for="business_boundary",
                metadata={
                    "rule_count": len(render_input.business_rules),
                    "rules": list(DEFAULT_RENDER_BUSINESS_RULES),
                },
            )
        )

    return _deduplicate_sources(sources)
'''


def main() -> int:
    """Patch renderer."""

    print("=" * 80)
    print("fixing Phase 3-I-I exact SKU spec_qa supplemental filtering")

    errors: list[str] = []
    changes: list[str] = []

    if not RENDERER_FILE.exists():
        errors.append(f"missing renderer file: {RENDERER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = RENDERER_FILE.read_text(encoding="utf-8")
    original = content

    if "def _should_skip_supplemental_rag_for_exact_sku(" not in content:
        anchor = "\ndef _build_evidence_lines("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, HELPERS + "\n" + anchor, 1)
            changes.append("inserted exact SKU supplemental filtering helpers")
    else:
        changes.append("exact SKU supplemental filtering helpers already present")

    if OLD_EVIDENCE_FUNC in content:
        content = content.replace(OLD_EVIDENCE_FUNC, NEW_EVIDENCE_FUNC, 1)
        changes.append("patched evidence line filtering")
    elif "skip_spec_qa = _should_skip_supplemental_rag_for_exact_sku" in content:
        changes.append("evidence line filtering already patched")
    else:
        errors.append("_build_evidence_lines anchor not found")

    if OLD_SOURCES_FUNC in content:
        content = content.replace(OLD_SOURCES_FUNC, NEW_SOURCES_FUNC, 1)
        changes.append("patched response source filtering")
    elif "for reference in render_input.source_references:" in content and "_is_spec_qa_supplemental_source(reference)" in content:
        changes.append("response source filtering already patched")
    else:
        errors.append("_build_response_sources anchor not found")

    if content != original and not errors:
        RENDERER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I exact SKU spec_qa supplemental filtering failed")
        return 1

    print("Phase 3-I-I exact SKU spec_qa supplemental filtering completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())