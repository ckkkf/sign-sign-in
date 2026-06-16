<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import { IconDeleteStroked, IconPlus, IconSave, IconStop, IconClock } from "@kousum/semi-icons-vue";
import type { AutoClockNotificationConfig, AutoClockState, AutoClockTaskConfig } from "@shared/types";
import type { DraftConfigKey } from "../types/app";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  visible: boolean;
  autoClock: AutoClockState;
  draft: Record<DraftConfigKey, string> & {
    autoClockTasks: AutoClockTaskConfig[];
    notifications: AutoClockNotificationConfig[];
  };
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "changeInput", key: DraftConfigKey, value: string): void;
  (event: "updateTasks", tasks: AutoClockTaskConfig[]): void;
  (event: "updateNotifications", notifications: AutoClockNotificationConfig[]): void;
  (event: "importImageForTask", index: number): void;
  (event: "testNotification", channel: AutoClockNotificationConfig): void;
  (event: "saveConfig"): void;
  (event: "toggleAutoClock"): void;
}>();

function updateTask(index: number, patch: Partial<AutoClockTaskConfig>) {
  emit("updateTasks", props.draft.autoClockTasks.map((task, taskIndex) => (taskIndex === index ? { ...task, ...patch } : task)));
}

function addTask() {
  emit("updateTasks", [...props.draft.autoClockTasks, { time: "08:55", mode: "in" }]);
}

function removeTask(index: number) {
  emit("updateTasks", props.draft.autoClockTasks.filter((_, taskIndex) => taskIndex !== index));
}

function updateNotification(index: number, patch: Partial<AutoClockNotificationConfig>) {
  emit("updateNotifications", props.draft.notifications.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
}

function addNotification() {
  emit("updateNotifications", [...props.draft.notifications, { type: "tray" }]);
}

function removeNotification(index: number) {
  emit("updateNotifications", props.draft.notifications.filter((_, itemIndex) => itemIndex !== index));
}
</script>

<template>
  <Modal className="compact-tool-modal auto-clock-modal" :visible="visible" title="定时打卡" :width="760" footer="" @cancel="emit('close')">
    <section class="auto-clock-dialog">
      <header class="auto-clock-summary">
        <div>
          <strong>{{ autoClock.enabled ? "定时打卡运行中" : "定时打卡未启动" }}</strong>
          <span>{{ autoClock.message || "配置任务和通知渠道后保存，可直接启动或停止定时打卡。" }}</span>
        </div>
        <Button
          :type="autoClock.enabled ? 'danger' : 'primary'"
          :icon="renderIcon(autoClock.enabled ? IconStop : IconClock)"
          @click="emit('toggleAutoClock')"
        >
          {{ autoClock.enabled ? "停止定时" : "启动定时" }}
        </Button>
      </header>

      <section class="auto-clock-settings">
        <label>
          <span>定时打卡</span>
          <Select
            :value="draft.autoClockEnabled"
            :option-list="[{ value: 'false', label: '关闭' }, { value: 'true', label: '启用' }]"
            @change="(value: any) => emit('changeInput', 'autoClockEnabled', String(value))"
          />
        </label>
        <label>
          <span>轮询间隔（秒）</span>
          <Input :value="draft.autoClockPollSeconds" show-clear @change="(value: string) => emit('changeInput', 'autoClockPollSeconds', value)" />
        </label>
        <label>
          <span>随机偏移（分钟）</span>
          <Input :value="draft.autoClockRandomMinutes" show-clear @change="(value: string) => emit('changeInput', 'autoClockRandomMinutes', value)" />
        </label>
        <label>
          <span>通知</span>
          <Select
            :value="draft.notificationsEnabled"
            :option-list="[{ value: 'false', label: '关闭' }, { value: 'true', label: '启用' }]"
            @change="(value: any) => emit('changeInput', 'notificationsEnabled', String(value))"
          />
        </label>
        <label class="wide">
          <span>PushPlus Token</span>
          <Input :value="draft.pushplusToken" show-clear @change="(value: string) => emit('changeInput', 'pushplusToken', value)" />
        </label>
      </section>

      <section class="auto-clock-editor">
        <div class="editor-head">
          <strong>定时任务</strong>
          <Button theme="light" :icon="renderIcon(IconPlus)" @click="addTask">添加任务</Button>
        </div>
        <article v-for="(task, index) in draft.autoClockTasks" :key="`${task.time}-${task.mode}-${index}`" class="task-row">
          <Input :value="task.time" placeholder="HH:mm" @change="(value: string) => updateTask(index, { time: value })" />
          <Select
            :value="task.mode"
            :option-list="[
              { value: 'in', label: '普通签到' },
              { value: 'out', label: '普通签退' },
              { value: 'photo_in', label: '拍照签到' },
              { value: 'photo_out', label: '拍照签退' }
            ]"
            @change="(value: any) => updateTask(index, { mode: String(value) })"
          />
          <Input
            :value="task.image_path || task.imagePath || ''"
            :disabled="task.mode !== 'photo_in' && task.mode !== 'photo_out'"
            placeholder="拍照模式图片路径"
            @change="(value: string) => updateTask(index, { image_path: value })"
          />
          <Button theme="light" :disabled="task.mode !== 'photo_in' && task.mode !== 'photo_out'" @click="emit('importImageForTask', index)">
            选择图片
          </Button>
          <Button theme="light" type="danger" :icon="renderIcon(IconDeleteStroked)" @click="removeTask(index)">删除</Button>
        </article>
        <div v-if="!draft.autoClockTasks.length" class="dialog-empty">暂无定时任务</div>

        <div class="editor-head notice-editor-head">
          <strong>通知渠道</strong>
          <Button theme="light" :icon="renderIcon(IconPlus)" @click="addNotification">添加通知</Button>
        </div>
        <article v-for="(item, index) in draft.notifications" :key="`${item.type}-${index}`" class="notice-row">
          <Select
            :value="item.type"
            :option-list="[
              { value: 'tray', label: '系统通知' },
              { value: 'pushplus', label: 'PushPlus' }
            ]"
            @change="(value: any) => updateNotification(index, { type: String(value) })"
          />
          <Input
            :value="item.token || ''"
            :disabled="item.type !== 'pushplus'"
            placeholder="PushPlus Token"
            @change="(value: string) => updateNotification(index, { token: value })"
          />
          <Button theme="light" @click="emit('testNotification', item)">测试</Button>
          <Button theme="light" type="danger" :icon="renderIcon(IconDeleteStroked)" @click="removeNotification(index)">删除</Button>
        </article>
        <div v-if="!draft.notifications.length" class="dialog-empty">暂无通知渠道</div>
      </section>

      <footer class="auto-clock-footer">
        <Space wrap>
          <Button type="primary" :icon="renderIcon(IconSave)" @click="emit('saveConfig')">保存配置</Button>
          <Button theme="light" @click="emit('close')">关闭</Button>
        </Space>
      </footer>
    </section>
  </Modal>
</template>
