from pathlib import Path

file_path = Path(r"../backend/app/agent/rag/document_loader.py")

code = file_path.read_text(encoding="utf-8")

old_block = """if isinstance(row, dict):
                explicit_text = _normalize_text(row.get("text"))
                text = explicit_text or _dict_to_text(row)
                row_metadata = row"""

new_block = """if isinstance(row, dict):
                from app.agent.rag.embedding_schema import build_embedding_text
                text = build_embedding_text(row)
                row_metadata = row"""

if old_block in code:
    code = code.replace(old_block, new_block)
    print("PATCH OK")
else:
    print("PATTERN NOT FOUND - maybe already patched")

file_path.write_text(code, encoding="utf-8")