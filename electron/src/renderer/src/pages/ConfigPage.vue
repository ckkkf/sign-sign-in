<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Card from "@kousum/semi-ui-vue/dist/card";
import Input from "@kousum/semi-ui-vue/dist/input";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import { IconDeleteStroked, IconPlus, IconRefresh, IconSave } from "@kousum/semi-icons-vue";
import type { AutoClockNotificationConfig, AutoClockTaskConfig } from "@shared/types";
import ConfigField from "../components/ConfigField.vue";
import type { DraftConfigKey } from "../types/app";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  draft: Record<DraftConfigKey, string> & {
    autoClockTasks: AutoClockTaskConfig[];
    notifications: AutoClockNotificationConfig[];
  };
}>();

const emit = defineEmits<{
  (event: "changeInput", key: DraftConfigKey, value: string): void;
  (event: "updateTasks", tasks: AutoClockTaskConfig[]): void;
  (event: "updateNotifications", notifications: AutoClockNotificationConfig[]): void;
  (event: "importImageForTask", index: number): void;
  (event: "testNotification", channel: AutoClockNotificationConfig): void;
  (event: "regenerateUserAgent"): void;
  (event: "saveConfig"): void;
}>();

function updateDeviceField(key: DraftConfigKey, value: string) {
  emit("changeInput", key, value);
  emit("regenerateUserAgent");
}

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
  <section class="home-panel config-panel">
    <header class="title-row">
      <div class="title-pair">
        <TypographyTitle :heading="3">配置</TypographyTitle>
        <span>位置、设备、定时打卡、推送与 User-Agent</span>
      </div>
    </header>
    <Card title="配置中心" :bordered="false" class-name="section-card">
      <div class="config-grid">
        <ConfigField>
          <template #label>经度</template>
          <Input :value="draft.longitude" show-clear @change="(value: string) => emit('changeInput', 'longitude', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>纬度</template>
          <Input :value="draft.latitude" show-clear @change="(value: string) => emit('changeInput', 'latitude', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>抖动半径（米）</template>
          <Input :value="draft.locationJitterMeters" show-clear @change="(value: string) => emit('changeInput', 'locationJitterMeters', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>平台</template>
          <Select
            :value="draft.platform"
            :option-list="[{ value: 'android', label: 'android' }, { value: 'ios', label: 'ios' }]"
            @change="(value: any) => updateDeviceField('platform', String(value))"
          />
        </ConfigField>
        <ConfigField>
          <template #label>品牌</template>
          <Input :value="draft.brand" show-clear @change="(value: string) => updateDeviceField('brand', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>型号</template>
          <Input :value="draft.model" show-clear @change="(value: string) => updateDeviceField('model', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>Android 版本</template>
          <Input :value="draft.systemVersion" show-clear @change="(value: string) => updateDeviceField('systemVersion', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>PushPlus Token</template>
          <Input :value="draft.pushplusToken" show-clear @change="(value: string) => emit('changeInput', 'pushplusToken', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>定时打卡</template>
          <Select
            :value="draft.autoClockEnabled"
            :option-list="[{ value: 'false', label: '关闭' }, { value: 'true', label: '启用' }]"
            @change="(value: any) => emit('changeInput', 'autoClockEnabled', String(value))"
          />
        </ConfigField>
        <ConfigField>
          <template #label>轮询间隔（秒）</template>
          <Input :value="draft.autoClockPollSeconds" show-clear @change="(value: string) => emit('changeInput', 'autoClockPollSeconds', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>随机偏移（分钟）</template>
          <Input :value="draft.autoClockRandomMinutes" show-clear @change="(value: string) => emit('changeInput', 'autoClockRandomMinutes', value)" />
        </ConfigField>
        <ConfigField>
          <template #label>通知</template>
          <Select
            :value="draft.notificationsEnabled"
            :option-list="[{ value: 'false', label: '关闭' }, { value: 'true', label: '启用' }]"
            @change="(value: any) => emit('changeInput', 'notificationsEnabled', String(value))"
          />
        </ConfigField>
        <ConfigField class="wide">
          <template #label>User-Agent</template>
          <TextArea
            :value="draft.userAgent"
            :autosize="{ minRows: 4, maxRows: 6 }"
            show-clear
            @change="(value: string) => emit('changeInput', 'userAgent', value)"
          />
        </ConfigField>
      </div>

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
          <Button
            theme="light"
            :disabled="task.mode !== 'photo_in' && task.mode !== 'photo_out'"
            @click="emit('importImageForTask', index)"
          >
            选择图片
          </Button>
          <Button theme="light" type="danger" :icon="renderIcon(IconDeleteStroked)" @click="removeTask(index)">删除</Button>
        </article>
        <div v-if="!draft.autoClockTasks.length" class="dialog-empty">暂无定时任务</div>

        <div class="editor-head">
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

      <template #footer>
        <Space wrap>
          <Button theme="light" :icon="renderIcon(IconRefresh)" @click="emit('regenerateUserAgent')">生成 UA</Button>
          <Button type="primary" :icon="renderIcon(IconSave)" @click="emit('saveConfig')">保存配置</Button>
        </Space>
      </template>
    </Card>
  </section>
</template>
