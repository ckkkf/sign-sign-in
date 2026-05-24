<script setup lang="ts">
defineProps<{
  label: string;
}>();
</script>

<template>
  <div class="section-title-row">
    <span class="section-label">{{ label }}</span>
    <slot />
  </div>
</template>
