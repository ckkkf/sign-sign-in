<script setup lang="ts">
import Banner from "@kousum/semi-ui-vue/dist/banner";
import { computed, onUnmounted, ref, watch } from "vue";

const props = defineProps<{
  bootError: string;
  noticeContent: string | string[];
}>();

const currentIndex = ref(0);
let timer: number | undefined;

const notices = computed(() => {
  const raw = Array.isArray(props.noticeContent) ? props.noticeContent : [props.noticeContent];
  return raw.map((item) => String(item || "").trim()).filter(Boolean);
});
const currentNotice = computed(() => notices.value[currentIndex.value] || "");

function stopTimer() {
  if (timer) {
    window.clearInterval(timer);
    timer = undefined;
  }
}

function startTimer() {
  stopTimer();
  if (notices.value.length <= 1) return;
  timer = window.setInterval(() => {
    currentIndex.value = (currentIndex.value + 1) % notices.value.length;
  }, 5000);
}

watch(
  notices,
  () => {
    currentIndex.value = 0;
    startTimer();
  },
  { immediate: true }
);

onUnmounted(stopTimer);
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
    v-else-if="currentNotice"
    className="notice-banner"
    type="info"
    :title="notices.length > 1 ? `公告 ${currentIndex + 1}/${notices.length}：` : '公告：'"
    :description="currentNotice"
    :bordered="false"
    close-icon=""
  />
</template>
