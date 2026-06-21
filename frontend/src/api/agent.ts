import { http } from "@/api/http";
import type {
  AgentQueryRequest,
  AgentQueryResponse,
  RawAgentQueryResponse,
} from "@/types/agent";
import {
  boolFromUnknown,
  numberFromUnknown,
  stringFromUnknown,
  toStringList,
} from "@/utils/format";

type BackendAgentQueryRequest = {
  text: string;
  source_channel: string;
  user_id?: string;
  session_id?: string;
  limit: number;
};

export async function queryAgent(
  request: AgentQueryRequest,
): Promise<AgentQueryResponse> {
  const started = performance.now();
  const payload: BackendAgentQueryRequest = {
    text: request.message,
    source_channel: request.channel ?? "local_debug",
    user_id: request.user_id,
    session_id: request.conversation_id,
    limit: request.limit ?? 5,
  };

  const response = await http.post<RawAgentQueryResponse>("/api/v1/agent/query", payload);
  return normalizeAgentResponse(response.data, Math.round(performance.now() - started));
}

export function normalizeAgentResponse(
  raw: RawAgentQueryResponse,
  fallbackLatencyMs?: number,
): AgentQueryResponse {
  const metadata = asRecord(raw.metadata);
  const answerText =
    stringFromUnknown(raw.final_response) ||
    stringFromUnknown(raw.answer_text) ||
    stringFromUnknown(raw.response) ||
    "";
  const sources = [
    ...toStringList(raw.response_sources),
    ...toStringList(raw.sources),
    ...extractSourceReferences(raw.source_references),
  ];

  return {
    final_response: answerText,
    selected_module: stringFromUnknown(raw.selected_module),
    answer_primary_module:
      stringFromUnknown(raw.answer_primary_module) ||
      stringFromUnknown(metadata.answer_primary_module),
    answer_candidate_modules: [
      ...toStringList(raw.answer_candidate_modules),
      ...toStringList(metadata.answer_candidate_modules),
    ],
    answer_strategy_mode:
      stringFromUnknown(raw.answer_strategy_mode) ||
      stringFromUnknown(metadata.answer_strategy_mode),
    handoff_required: boolFromUnknown(raw.handoff_required),
    needs_handoff: boolFromUnknown(raw.needs_handoff),
    answer_handoff_required:
      boolFromUnknown(raw.answer_handoff_required) ??
      boolFromUnknown(metadata.answer_handoff_required),
    answer_safety_blocked:
      boolFromUnknown(raw.answer_safety_blocked) ??
      boolFromUnknown(metadata.answer_safety_blocked),
    render_safety_blocked:
      boolFromUnknown(raw.render_safety_blocked) ??
      boolFromUnknown(metadata.render_safety_blocked),
    render_mode: stringFromUnknown(raw.render_mode) || stringFromUnknown(metadata.render_mode),
    response_warnings: [
      ...toStringList(raw.response_warnings),
      ...toStringList(raw.warnings),
    ],
    risk_flags: [
      ...toStringList(raw.risk_flags),
      ...toStringList(raw.risk_reasons),
      ...toStringList(metadata.risk_flags),
    ],
    retrieved_chunk_count:
      numberFromUnknown(raw.retrieved_chunk_count) ??
      numberFromUnknown(metadata.retrieved_chunk_count) ??
      toStringList(raw.retrieved_chunks).length,
    used_llm_output:
      boolFromUnknown(raw.used_llm_output) ?? boolFromUnknown(metadata.used_llm_output),
    latency_ms:
      numberFromUnknown(raw.latency_ms) ??
      numberFromUnknown(metadata.latency_ms) ??
      fallbackLatencyMs,
    response_sources: sources,
    sources,
    session_id: stringFromUnknown(raw.session_id),
    conversation_id: stringFromUnknown(raw.conversation_id),
    handoff_ticket_id: stringFromUnknown(raw.handoff_ticket_id),
    handoff_ticket_no: stringFromUnknown(raw.handoff_ticket_no),
    metadata,
    raw,
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return {};
}

function extractSourceReferences(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (typeof item === "string") {
        return item;
      }

      if (item && typeof item === "object") {
        const ref = item as Record<string, unknown>;
        return (
          stringFromUnknown(ref.source_id) ||
          stringFromUnknown(ref.source_name) ||
          stringFromUnknown(ref.id)
        );
      }

      return undefined;
    })
    .filter((item): item is string => Boolean(item));
}
