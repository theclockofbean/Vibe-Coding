"""Patch qdrant_store.py to wrap HTTPException as QdrantStoreError."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/rag/qdrant_store.py")
content = target.read_text(encoding="utf-8")

if "from http.client import HTTPException" not in content:
    content = content.replace(
        "import json\n",
        "import json\nfrom http.client import HTTPException\n",
    )

old = '''        except URLError as exc:
            raise QdrantStoreError(
                f"Qdrant connection error for {method} {path}: {exc}"
            ) from exc

        if not raw_body:
'''

new = '''        except URLError as exc:
            raise QdrantStoreError(
                f"Qdrant connection error for {method} {path}: {exc}"
            ) from exc
        except HTTPException as exc:
            raise QdrantStoreError(
                f"Qdrant HTTP protocol error for {method} {path}: {exc}"
            ) from exc

        if not raw_body:
'''

if old not in content:
    raise RuntimeError("target exception block not found")

content = content.replace(old, new)

target.write_text(content, encoding="utf-8")

print("patched qdrant_store.py HTTPException handling")