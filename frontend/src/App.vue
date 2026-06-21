<template>
  <div class="min-h-screen bg-slate-100">
    <header class="border-b border-slate-200 bg-white">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div>
          <p class="text-xs font-semibold uppercase tracking-normal text-slate-500">
            AI Knowledge Agent
          </p>
          <h1 class="text-lg font-semibold text-slate-950">调试演示台</h1>
        </div>
        <nav class="flex gap-1 rounded-lg bg-slate-100 p-1">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-white hover:text-slate-950"
            active-class="bg-white text-slate-950 shadow-sm"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-7xl px-4 py-5">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
const navItems = [
  { to: "/", label: "对话调试" },
  { to: "/evaluation", label: "评测报告" },
  { to: "/handoff", label: "人工接管" },
];
</script>
