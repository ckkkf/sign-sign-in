<script setup lang="ts">
import Banner from "@kousum/semi-ui-vue/dist/banner";

defineProps<{
  bootError: string;
  noticeContent: string;
}>();
</script>

<template>
  <Banner
    v-if="bootError"
    type="danger"
    title="初始化失败："
    :description="bootError"
    :bordered="false"
    close-icon=""
  />
  <Banner
    v-else-if="noticeContent"
    type="info"
    title="公告："
    :description="noticeContent"
    :bordered="false"
    close-icon=""
  />
</template>
