<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import RadioGroup from "@kousum/semi-ui-vue/dist/radio/radioGroup";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Tag from "@kousum/semi-ui-vue/dist/tag";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import {
  IconApps,
  IconClock,
  IconCodeStroked,
  IconCopy,
  IconDeleteStroked,
  IconFile,
  IconImage,
  IconLink,
  IconLockStroked,
  IconPlay,
  IconRefresh,
  IconShieldStroked,
  IconStop
} from "@kousum/semi-icons-vue";
import { computed } from "vue";
import { PROJECT_NAME, QQ_GROUP } from "@shared/constants";
import type { CaptureState, ImageItem, SignOption, SystemStatus, TaskState } from "@shared/types";
import MainActionButton from "../components/MainActionButton.vue";
import SectionTitle from "../components/SectionTitle.vue";
import StatusGrid from "../components/StatusGrid.vue";
import ToolButton from "../components/ToolButton.vue";
import type { PageKey, StatusItem } from "../types/app";
import { renderIcon } from "../utils/icons";

defineProps<{
  actionOptions: Array<{ label: SignOption["action"]; value: SignOption["action"] }>;
  capture: CaptureState;
  images: ImageItem[];
  isPhotoAction: boolean;
  loading: boolean;
  selectedAction: SignOption["action"];
  selectedImage: string;
  status: SystemStatus;
  statusItems: StatusItem[];
  task: TaskState;
}>();

const emit = defineEmits<{
  (event: "changePage", page: PageKey): void;
  (event: "changeSelectedAction", value: SignOption["action"]): void;
  (event: "changeSelectedImage", value: string): void;
  (event: "copyQQGroup"): void;
  (event: "deleteSelectedImage"): void;
  (event: "openImageManager"): void;
  (event: "openCertManager"): void;
  (event: "openFeedback"): void;
  (event: "openProxySettings"): void;
  (event: "refreshAll"): void;
  (event: "startCapture"): void;
  (event: "startTask"): void;
  (event: "stopCapture"): void;
  (event: "stopTask"): void;
}>();

const toolButtons = computed(() => [
  { label: "系统代理", icon: IconLink, action: () => emit("openProxySettings") },
  { label: "证书管理", icon: IconLockStroked, action: () => emit("openCertManager") },
  { label: "编辑配置", icon: IconFile, action: () => emit("changePage", "config") },
  { label: "刷新状态", icon: IconRefresh, action: () => emit("refreshAll") },
  { label: "发送反馈", icon: IconShieldStroked, action: () => emit("openFeedback") },
  { label: "图片管理", icon: IconImage, action: () => emit("openImageManager") },
  { label: "更新中心", icon: IconShieldStroked, disabled: true },
  { label: "AI 与周记", icon: IconApps, disabled: true },
  { label: "定时打卡", icon: IconClock, disabled: true }
]);

function clickTool(tool: (typeof toolButtons.value)[number]) {
  if (tool.disabled) return;
  tool.action?.();
}
</script>

<template>
  <section class="home-panel">
    <header class="title-row">
      <div class="title-pair">
        <TypographyTitle :heading="3">{{ PROJECT_NAME }}</TypographyTitle>
        <span>自动化实习签到系统</span>
      </div>
      <Space>
        <Tag :color="task.running ? 'blue' : 'grey'">{{ task.running ? "TASK RUNNING" : "IDLE" }}</Tag>
        <Tag :color="status.sessionValid ? 'green' : 'orange'">{{ status.sessionValid ? "SESSION READY" : "NEED CODE" }}</Tag>
      </Space>
    </header>

    <Button class-name="qq-strip" theme="light" block :icon="renderIcon(IconCopy)" @click="emit('copyQQGroup')">
      <span class="qq-badge">QQ</span>
      <span class="qq-label">交流群</span>
      <span class="qq-divider">/</span>
      <span class="qq-number">{{ QQ_GROUP }}</span>
      <span class="qq-hint">点击复制</span>
    </Button>

    <SectionTitle label="状态域">
      <Button
        class-name="section-refresh-button"
        theme="borderless"
        type="tertiary"
        :icon="renderIcon(IconRefresh)"
        @click="emit('refreshAll')"
      />
    </SectionTitle>
    <StatusGrid :items="statusItems" />

    <SectionTitle label="工具箱" />
    <section class="tool-grid">
      <ToolButton
        v-for="tool in toolButtons"
        :key="tool.label"
        :label="tool.label"
        :icon="tool.icon"
        :disabled="tool.disabled"
        @click="clickTool(tool)"
      />
    </section>

    <div class="reminder-line">提示：小程序会自动关闭，签到请在本软件完成</div>

    <SectionTitle label="执行操作（拍照签到签退经纬度不准会导致外勤）" />
    <section class="mode-row">
      <RadioGroup
        class-name="mode-group"
        :value="selectedAction"
        :options="actionOptions"
        direction="horizontal"
        @change="(event: any) => emit('changeSelectedAction', event.target.value)"
      />
    </section>

    <div v-if="isPhotoAction" class="field-row">
      <Select
        :value="selectedImage"
        placeholder="选择签到图片"
        class-name="flex-field"
        :option-list="images.map((image) => ({ value: image.path, label: image.name }))"
        @change="(value: any) => emit('changeSelectedImage', String(value || ''))"
      />
      <Button theme="light" :icon="renderIcon(IconImage)" @click="emit('openImageManager')">图片管理</Button>
      <Button
        theme="light"
        type="danger"
        :disabled="!selectedImage"
        :icon="renderIcon(IconDeleteStroked)"
        @click="emit('deleteSelectedImage')"
      >
        删除
      </Button>
    </div>

    <section class="main-actions">
      <MainActionButton
        :class-name="['get-code-btn', capture.running ? 'is-stopping' : ''].filter(Boolean).join(' ')"
        :icon="capture.running ? IconStop : IconCodeStroked"
        :label="capture.running ? '停止捕获' : '获取code'"
        @click="capture.running ? emit('stopCapture') : emit('startCapture')"
      />
      <MainActionButton
        class-name="start-btn"
        :loading="loading"
        :disabled="task.running || (isPhotoAction && !selectedImage)"
        :icon="IconPlay"
        label="开始执行"
        @click="emit('startTask')"
      />
      <Button v-if="task.running" theme="outline" :icon="renderIcon(IconStop)" @click="emit('stopTask')">停止执行</Button>
    </section>

    <section class="support-row">
      <Button theme="outline">支持作者</Button>
      <Button theme="outline">开源仓库</Button>
    </section>
  </section>
</template>
