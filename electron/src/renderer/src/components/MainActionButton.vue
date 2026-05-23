<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import { renderIcon } from "../utils/icons";

defineProps<{
  className: string;
  disabled?: boolean;
  icon: unknown;
  label: string;
  loading?: boolean;
}>();

const emit = defineEmits<{
  (event: "click"): void;
}>();
</script>

<template>
  <Button
    type="primary"
    size="large"
    :class-name="className"
    :disabled="disabled"
    :icon="renderIcon(icon)"
    :loading="loading"
    @click="emit('click')"
  >
    {{ label }}
  </Button>
</template>
