export type EvaluationSummary = {
  total_cases: number;
  blocker_count: number;
  major_count: number;
  workflow_error_count: number;
  module_accuracy: number;
  risk_gate_pass_rate: number;
  final_response_non_empty_rate: number;
  forbidden_commitment_leak_count: number;
  price_violation_count: number;
  price_compliance_rate: number;
  failed_case_count: number;
  spec_failed_count?: number;
  failed_cases?: EvaluationCase[];
};

export type EvaluationCase = {
  case_id: string;
  query: string;
  category: "spec" | "price" | "logistics" | "quality" | "escalation" | string;
  scenario_type: "core" | "boundary" | "risk" | string;
  expected_module: string;
  selected_module: string;
  answer_strategy_mode?: string;
  handoff_required?: boolean;
  final_response: string;
  final_response_preview?: string;
  passed: boolean;
  failure_reasons: string[];
  latency_ms?: number;
  render_mode?: string;
  used_llm_output?: boolean;
};

export type EvaluationReport = {
  summary: EvaluationSummary;
  results: EvaluationCase[];
  generated_at?: string;
  source?: string;
};
