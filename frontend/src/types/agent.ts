export type AgentModule = "spec" | "price" | "logistics" | "quality" | "general";

export type AnswerStrategyMode =
  | "single_primary"
  | "primary_with_boundary_note"
  | "handoff_required"
  | "split_required"
  | "safety_blocked";

export type AgentQueryRequest = {
  message: string;
  channel?: "local_debug" | "wechat" | "taobao" | "alibaba";
  user_id?: string;
  conversation_id?: string;
  limit?: number;
};

export type RawAgentQueryResponse = Record<string, unknown>;

export type AgentQueryResponse = {
  final_response: string;
  selected_module?: AgentModule | string;
  answer_primary_module?: string;
  answer_candidate_modules?: string[];
  answer_strategy_mode?: AnswerStrategyMode | string;
  handoff_required?: boolean;
  needs_handoff?: boolean;
  answer_handoff_required?: boolean;
  answer_safety_blocked?: boolean;
  render_safety_blocked?: boolean;
  render_mode?: string;
  response_warnings?: string[];
  risk_flags?: string[];
  retrieved_chunk_count?: number;
  used_llm_output?: boolean;
  latency_ms?: number;
  response_sources?: string[];
  sources?: string[];
  session_id?: string;
  conversation_id?: string | number;
  handoff_ticket_id?: string | number | null;
  handoff_ticket_no?: string | null;
  metadata?: Record<string, unknown>;
  raw: RawAgentQueryResponse;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  response?: AgentQueryResponse;
};
