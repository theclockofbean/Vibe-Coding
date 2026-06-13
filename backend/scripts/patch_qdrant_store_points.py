"""Patch qdrant_store.py with point upsert and retrieve methods."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/rag/qdrant_store.py")
content = target.read_text(encoding="utf-8")

if "    def upsert_point(" not in content:
    anchor = "    def _request(\n"
    methods = '''    def upsert_point(
        self,
        *,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Upsert one point into Qdrant collection."""

        _require_non_blank("collection_name", collection_name)
        _require_non_blank("point_id", point_id)

        if not vector:
            raise ValueError("vector must not be empty")

        self._request(
            method="PUT",
            path=f"/collections/{collection_name}/points?wait=true",
            payload={
                "points": [
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": payload,
                    }
                ],
            },
        )

    def get_points(
        self,
        *,
        collection_name: str,
        point_ids: list[str],
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve points by point IDs."""

        _require_non_blank("collection_name", collection_name)

        if not point_ids:
            return []

        payload = self._request(
            method="POST",
            path=f"/collections/{collection_name}/points",
            payload={
                "ids": point_ids,
                "with_payload": with_payload,
                "with_vector": with_vector,
            },
        )

        result = payload.get("result")

        if not isinstance(result, list):
            return []

        return [
            _dict_value(item)
            for item in result
            if isinstance(item, dict)
        ]

'''
    content = content.replace(anchor, methods + anchor)

target.write_text(content, encoding="utf-8")

print("patched qdrant_store.py point methods")