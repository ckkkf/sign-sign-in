<script setup lang="ts">
import Input from "@kousum/semi-ui-vue/dist/input";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import { reactive } from "vue";
import type { FeedbackPayload } from "../services/authApi";

defineProps<{
  visible: boolean;
  loading: boolean;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "submit", payload: FeedbackPayload): void;
}>();

const form = reactive<FeedbackPayload>({
  title: "",
  feedbackType: "功能建议",
  priority: "1",
  contact: "",
  content: ""
});

const feedbackTypeOptions = [
  { value: "功能建议", label: "功能建议" },
  { value: "Bug 反馈", label: "Bug 反馈" },
  { value: "使用咨询", label: "使用咨询" },
  { value: "其他问题", label: "其他问题" }
];

const priorityOptions = [
  { value: "0", label: "低" },
  { value: "1", label: "中" },
  { value: "2", label: "高" }
];

function submit() {
  const title = form.title.trim();
  const contact = form.contact.trim();
  const content = form.content.trim();

  if (!title) {
    Toast.warning("请填写反馈标题");
    return;
  }
  if (!content) {
    Toast.warning("请填写反馈内容");
    return;
  }

  emit("submit", {
    title,
    feedbackType: form.feedbackType,
    priority: form.priority,
    contact,
    content
  });
}

function changeFeedbackType(value: string | number | any[] | Record<string, any> | undefined) {
  form.feedbackType = String(value || "功能建议");
}

function changePriority(value: string | number | any[] | Record<string, any> | undefined) {
  form.priority = String(value || "1");
}
</script>

<template>
  <Modal
    :visible="visible"
    title="发送反馈"
    :width="520"
    :style="{ marginTop: '7vh' }"
    :mask-closable="false"
    ok-text="提交反馈"
    cancel-text="取消"
    :confirm-loading="loading"
    :cancel-button-props="{ disabled: loading }"
    @cancel="emit('close')"
    @ok="submit"
  >
    <Space vertical spacing="medium" class-name="feedback-form-stack">
      <Space vertical align="start" spacing="tight" class-name="feedback-field">
        <TypographyText type="secondary">标题</TypographyText>
        <Input
          :value="form.title"
          placeholder="一句话说明反馈主题"
          show-clear
          :disabled="loading"
          @change="(value: string) => (form.title = value)"
          @enter-press="submit"
        />
      </Space>

      <Space align="center" spacing="medium" class-name="feedback-select-row">
        <Space vertical align="start" spacing="tight" class-name="feedback-field">
          <TypographyText type="secondary">反馈类型</TypographyText>
          <Select
            :value="form.feedbackType"
            :option-list="feedbackTypeOptions"
            :disabled="loading"
            @change="changeFeedbackType"
          />
        </Space>

        <Space vertical align="start" spacing="tight" class-name="feedback-field">
          <TypographyText type="secondary">优先级</TypographyText>
          <Select
            :value="form.priority"
            :option-list="priorityOptions"
            :disabled="loading"
            @change="changePriority"
          />
        </Space>
      </Space>

      <Space vertical align="start" spacing="tight" class-name="feedback-field">
        <TypographyText type="secondary">联系方式</TypographyText>
        <Input
          :value="form.contact"
          placeholder="Email / QQ / 微信（可选）"
          show-clear
          :disabled="loading"
          @change="(value: string) => (form.contact = value)"
        />
      </Space>

      <Space vertical align="start" spacing="tight" class-name="feedback-field">
        <TypographyText type="secondary">反馈内容</TypographyText>
        <TextArea
          :value="form.content"
          placeholder="请尽量描述清楚问题、重现步骤或你期待的功能..."
          :autosize="{ minRows: 6, maxRows: 8 }"
          :max-count="1000"
          show-counter
          :disabled="loading"
          @change="(value: string) => (form.content = value)"
        />
      </Space>
    </Space>

  </Modal>
</template>
