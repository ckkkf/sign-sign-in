<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Card from "@kousum/semi-ui-vue/dist/card";
import Input from "@kousum/semi-ui-vue/dist/input";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import { IconRefresh, IconSave } from "@kousum/semi-icons-vue";
import ConfigField from "../components/ConfigField.vue";
import type { DraftConfigKey } from "../types/app";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  draft: Record<DraftConfigKey, string>;
}>();

const emit = defineEmits<{
  (event: "changeInput", key: DraftConfigKey, value: string): void;
  (event: "regenerateUserAgent"): void;
  (event: "saveConfig"): void;
}>();

function updateDeviceField(key: DraftConfigKey, value: string) {
  emit("changeInput", key, value);
  emit("regenerateUserAgent");
}

</script>

<template>
  <section class="home-panel config-panel">
    <header class="title-row">
      <div class="title-pair">
        <TypographyTitle :heading="3">配置</TypographyTitle>
        <span>位置、设备与 User-Agent</span>
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

      <template #footer>
        <Space wrap>
          <Button theme="light" :icon="renderIcon(IconRefresh)" @click="emit('regenerateUserAgent')">生成 UA</Button>
          <Button type="primary" :icon="renderIcon(IconSave)" @click="emit('saveConfig')">保存配置</Button>
        </Space>
      </template>
    </Card>
  </section>
</template>
