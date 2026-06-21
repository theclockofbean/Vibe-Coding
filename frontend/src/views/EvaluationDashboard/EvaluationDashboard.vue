<template>
  <div class="space-y-5">
    <section class="grid gap-4 md:grid-cols-5">
      <MetricCard label="blocker" :value="summaryValue('blocker_count')" />
      <MetricCard label="workflow errors" :value="summaryValue('workflow_error_count')" />
      <MetricCard label="risk gate" :value="formatPercent(report?.summary.risk_gate_pass_rate)" />
      <MetricCard
        label="commitment leaks"
        :value="summaryValue('forbidden_commitment_leak_count')"
      />
      <MetricCard
        label="price compliance"
        :value="formatPercent(report?.summary.price_compliance_rate)"
      />
    </section>

    <section class="grid gap-4 md:grid-cols-3">
      <MetricCard
        label="module accuracy"
        :value="formatPercent(report?.summary.module_accuracy)"
      />
      <MetricCard label="failed cases" :value="summaryValue('failed_case_count')" />
      <MetricCard label="major count" :value="summaryValue('major_count')" />
    </section>

    <section class="panel rounded-lg p-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 class="text-base font-semibold text-slate-950">Failed Cases</h2>
          <p class="mt-1 text-sm text-slate-500">
            {{ filteredCases.length }} / {{ cases.length }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <select v-model="category" class="focus-ring rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="">all categories</option>
            <option v-for="item in categories" :key="item" :value="item">{{ item }}</option>
          </select>
          <select v-model="scenario" class="focus-ring rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="">all scenarios</option>
            <option v-for="item in scenarios" :key="item" :value="item">{{ item }}</option>
          </select>
          <select v-model="passed" class="focus-ring rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="">all results</option>
            <option value="false">failed</option>
            <option value="true">passed</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="mt-5 text-sm text-slate-500">加载中...</div>
      <div v-else-if="error" class="mt-5 text-sm text-red-600">{{ error }}</div>
      <div v-else class="mt-5 divide-y divide-slate-200 rounded-lg border border-slate-200">
        <article v-for="item in filteredCases" :key="item.case_id" class="bg-white">
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
            @click="toggleCase(item.case_id)"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-semibold text-slate-950">{{ item.case_id }}</span>
                <IntentBadge :module-name="item.selected_module" />
                <span class="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                  {{ item.category }} / {{ item.scenario_type }}
                </span>
              </div>
              <p class="mt-1 truncate text-sm text-slate-600">
                {{ item.query || item.final_response_preview || item.final_response }}
              </p>
            </div>
            <span
              class="rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset"
              :class="
                item.passed
                  ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                  : 'bg-orange-50 text-orange-700 ring-orange-200'
              "
            >
              {{ item.passed ? "passed" : "failed" }}
            </span>
          </button>
          <div v-if="expanded.has(item.case_id)" class="space-y-3 border-t border-slate-100 px-4 py-4">
            <div>
              <p class="label">failure reasons</p>
              <ul class="mt-2 space-y-1 text-sm text-red-700">
                <li v-for="reason in item.failure_reasons" :key="reason">{{ reason }}</li>
              </ul>
            </div>
            <div>
              <p class="label">final response</p>
              <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                {{ item.final_response || item.final_response_preview || "-" }}
              </p>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { getLatestEvaluationReport } from "@/api/evaluation";
import MetricCard from "@/components/ConfidenceIndicator/MetricCard.vue";
import IntentBadge from "@/components/IntentBadge/IntentBadge.vue";
import type { EvaluationCase, EvaluationReport, EvaluationSummary } from "@/types/evaluation";
import { formatNumber, formatPercent } from "@/utils/format";

const report = ref<EvaluationReport | null>(null);
const loading = ref(false);
const error = ref("");
const category = ref("");
const scenario = ref("");
const passed = ref("");
const expanded = ref(new Set<string>());

const cases = computed(() => report.value?.results ?? []);
const categories = computed(() => unique(cases.value.map((item) => item.category)));
const scenarios = computed(() => unique(cases.value.map((item) => item.scenario_type)));
const filteredCases = computed(() =>
  cases.value.filter((item) => {
    if (category.value && item.category !== category.value) {
      return false;
    }

    if (scenario.value && item.scenario_type !== scenario.value) {
      return false;
    }

    if (passed.value && String(Boolean(item.passed)) !== passed.value) {
      return false;
    }

    return true;
  }),
);

onMounted(async () => {
  loading.value = true;
  try {
    report.value = await getLatestEvaluationReport();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "评测报告加载失败";
  } finally {
    loading.value = false;
  }
});

function summaryValue(key: keyof EvaluationSummary): string {
  const value = report.value?.summary[key];
  return typeof value === "number" ? formatNumber(value) : "-";
}

function toggleCase(caseId: string): void {
  const next = new Set(expanded.value);
  if (next.has(caseId)) {
    next.delete(caseId);
  } else {
    next.add(caseId);
  }

  expanded.value = next;
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort();
}
</script>
