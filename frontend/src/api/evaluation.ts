import { http } from "@/api/http";
import type { EvaluationReport } from "@/types/evaluation";

export async function getLatestEvaluationReport(): Promise<EvaluationReport> {
  try {
    const response = await http.get<EvaluationReport>("/api/v1/evaluation/latest");
    return response.data;
  } catch {
    const response = await http.get<EvaluationReport>(
      "/mock/phase3ii_real_llm_50_case_eval_report.json",
    );
    return response.data;
  }
}
