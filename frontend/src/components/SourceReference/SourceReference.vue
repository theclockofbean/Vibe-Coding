<template>
  <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
    <p class="label">sources</p>
    <div v-if="sources.length" class="mt-2 flex flex-wrap gap-2">
      <span
        v-for="source in sources"
        :key="source"
        class="rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200"
      >
        {{ source }}
      </span>
    </div>
    <p v-else class="mt-2 text-sm text-slate-500">-</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  sources: string[];
}>();
</script>
