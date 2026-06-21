<template>
  <section class="metric">
    <p class="label">{{ label }}</p>
    <p class="mt-2 text-2xl font-semibold text-slate-950">{{ value }}</p>
    <p v-if="hint" class="mt-1 text-xs text-slate-500">{{ hint }}</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  value: string | number;
  hint?: string;
}>();
</script>
