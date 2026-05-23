<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import { renderIcon } from "../utils/icons";

defineProps<{
  disabled?: boolean;
  icon: unknown;
  label: string;
}>();

const emit = defineEmits<{
  (event: "click"): void;
}>();
</script>

<template>
  <Button
    theme="light"
    :class-name="['tool-button', disabled ? 'is-disabled' : ''].filter(Boolean).join(' ')"
    :icon="renderIcon(icon)"
    @click="disabled ? undefined : emit('click')"
  >
    {{ label }}
  </Button>
</template>
