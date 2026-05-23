<script setup lang="ts">
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
</script>

<template>
  <label>
    <TypographyText type="secondary">
      <slot name="label" />
    </TypographyText>
    <slot />
  </label>
</template>
