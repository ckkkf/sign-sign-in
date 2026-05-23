<script setup lang="ts">
defineProps<{
  label: string;
}>();
</script>

<template>
  <span class="section-label">{{ label }}</span>
</template>
