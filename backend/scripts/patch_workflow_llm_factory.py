"""Patch workflow LLMNode to use LLMClientFactory."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

old_import = "    from app.agent.llm.client import RuleBasedLLMClient\n"
new_import = "    from app.agent.llm.factory import build_llm_client_result_from_env\n"

if new_import not in content:
    if old_import not in content:
        raise RuntimeError("RuleBasedLLMClient import line not found")
    content = content.replace(old_import, new_import, 1)

old_call = "    raw_response = RuleBasedLLMClient().generate(request)\n"
new_call = """    client_result = build_llm_client_result_from_env()
    raw_response = client_result.client.generate(request)
"""

if new_call not in content:
    if old_call not in content:
        raise RuntimeError("RuleBasedLLMClient generate call not found")
    content = content.replace(old_call, new_call, 1)

old_return = "    return request.to_dict(), guarded_response.to_dict()\n"
new_return = """    request_dict = request.to_dict()
    request_dict["forbidden_commitments"] = ["<redacted>"]

    response_dict = guarded_response.to_dict()
    response_metadata_raw = response_dict.get("metadata")
    response_metadata = (
        {
            str(key): value
            for key, value in response_metadata_raw.items()
        }
        if isinstance(response_metadata_raw, dict)
        else {}
    )
    response_metadata["llm_factory"] = client_result.metadata
    response_metadata["llm_factory_warnings"] = client_result.warnings
    response_metadata["llm_real_api_enabled"] = client_result.real_api_enabled
    response_dict["metadata"] = response_metadata

    return request_dict, response_dict
"""

if 'request_dict["forbidden_commitments"] = ["<redacted>"]' not in content:
    if old_return not in content:
        raise RuntimeError("LLM helper return line not found")
    content = content.replace(old_return, new_return, 1)

old_metadata_block = '            metadata["llm_fallback_reason"] = None\n'
new_metadata_block = '''            metadata["llm_fallback_reason"] = None

            response_metadata_raw = response.get("metadata")
            response_metadata = (
                {
                    str(key): value
                    for key, value in response_metadata_raw.items()
                }
                if isinstance(response_metadata_raw, dict)
                else {}
            )
            factory_metadata_raw = response_metadata.get("llm_factory")
            factory_metadata = (
                {
                    str(key): value
                    for key, value in factory_metadata_raw.items()
                }
                if isinstance(factory_metadata_raw, dict)
                else {}
            )
            metadata["llm_real_api_enabled"] = response_metadata.get(
                "llm_real_api_enabled",
                False,
            )
            metadata["llm_factory_fallback_reason"] = factory_metadata.get(
                "fallback_reason"
            )
            metadata["llm_factory_warnings"] = response_metadata.get(
                "llm_factory_warnings",
                [],
            )
'''

if 'metadata["llm_real_api_enabled"] = response_metadata.get(' not in content:
    if old_metadata_block not in content:
        raise RuntimeError("llm_fallback_reason metadata anchor not found")
    content = content.replace(old_metadata_block, new_metadata_block, 1)

target.write_text(content, encoding="utf-8")

print("patched workflow LLMNode with LLMClientFactory")