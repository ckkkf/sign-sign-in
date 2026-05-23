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
    class-name="free-banner"
    type="danger"
    title="初始化失败"
    :description="bootError"
    :bordered="false"
  />
  <div v-else class="free-banner notice-banner" :title="noticeContent">
    <div class="notice-track">
      <span><strong>【公告】</strong>{{ noticeContent }}</span>
      <span aria-hidden="true"><strong>【公告】</strong>{{ noticeContent }}</span>
    </div>
  </div>
</template>
