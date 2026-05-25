<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Card from "@kousum/semi-ui-vue/dist/card";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Tag from "@kousum/semi-ui-vue/dist/tag";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import { IconImage, IconLink, IconQrCode, IconRefresh, IconSend, IconTick } from "@kousum/semi-icons-vue";
import type { ImageItem } from "@shared/types";
import SectionTitle from "../components/SectionTitle.vue";
import { useJieLongState } from "../composables/useJieLongState";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  images: ImageItem[];
}>();

const emit = defineEmits<{
  (event: "openImageManager"): void;
}>();

const {
  status,
  loginStatus,
  loading,
  submitting,
  qrBusy,
  qrPolling,
  qrVisible,
  qrImage,
  qrUuid,
  bundle,
  settings,
  answers,
  invalidFields,
  statusTone,
  visibleFields,
  summaryItems,
  statusClass,
  fieldId,
  fieldKind,
  parseOptions,
  isOtherOption,
  setAnswer,
  selectOption,
  imageName,
  parseShareUrl,
  startQrLogin,
  closeQrModal,
  loadForm,
  chooseImage,
  clearImage,
  submit
} = useJieLongState();
</script>

<template>
  <section class="home-panel jielong-panel">
    <header class="title-row">
      <div class="title-pair">
        <TypographyTitle :heading="3">接龙</TypographyTitle>
        <span>扫码登录、拉取表单并提交打卡</span>
      </div>
      <Space>
        <Tag :color="statusTone">{{ status }}</Tag>
        <Tag v-if="loginStatus" :color="statusTone">{{ loginStatus }}</Tag>
      </Space>
    </header>

    <Card class-name="jielong-card" :bordered="false">
      <div class="jielong-top">
        <label class="login-field">
          <span>接龙 Token</span>
          <Input :value="settings.authorization" placeholder="扫码登录后自动填充" @change="(value: string) => (settings.authorization = value)" />
        </label>
        <Space>
          <Button theme="light" :icon="renderIcon(IconQrCode)" :loading="qrBusy" @click="startQrLogin">扫码登录</Button>
        </Space>

        <label class="login-field wide">
          <span>分享链接</span>
          <Input :value="settings.share_url" placeholder="粘贴接龙分享链接，例如 https://jielong.com/s/..." @change="(value: string) => (settings.share_url = value)" />
        </label>
        <Button theme="light" :icon="renderIcon(IconLink)" @click="parseShareUrl">解析</Button>

        <label class="login-field">
          <span>threadId</span>
          <Input :value="settings.thread_id" placeholder="解析后自动填充，也可手动输入" @change="(value: string) => (settings.thread_id = value)" />
        </label>
        <Button type="primary" :icon="renderIcon(IconRefresh)" :loading="loading" @click="loadForm">拉取表单</Button>
      </div>
    </Card>

    <section v-if="summaryItems.length" class="jielong-summary">
      <div v-for="item in summaryItems" :key="item.key" class="jielong-summary-item">
        <span>{{ item.key }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <SectionTitle label="接龙字段" />
    <section class="jielong-fields">
      <div v-if="!bundle" class="jielong-empty">点击“拉取表单”后在这里填写内容。</div>
      <div v-else-if="!visibleFields.length" class="jielong-empty">接口已返回，但没有可渲染字段。</div>

      <article v-for="field in visibleFields" :key="fieldId(field)" class="jielong-field-card">
        <header class="jielong-field-head">
          <strong>{{ field.Name || "未命名字段" }}</strong>
          <Tag size="small">{{ fieldKind(field) }}</Tag>
          <Tag v-if="field.IsRequired" color="red" size="small">必填</Tag>
        </header>
        <TypographyText v-if="field.Tip" type="tertiary">{{ field.Tip }}</TypographyText>

        <Input
          v-if="fieldKind(field) === 'text'"
          :value="answers[fieldId(field)]?.value || ''"
          @change="(value: string) => setAnswer(fieldId(field), { value })"
        />
        <TextArea
          v-else-if="fieldKind(field) === 'textarea'"
          :value="answers[fieldId(field)]?.value || ''"
          :autosize="{ minRows: 2, maxRows: 5 }"
          @change="(value: string) => setAnswer(fieldId(field), { value })"
        />
        <div v-else-if="fieldKind(field) === 'select'" class="jielong-stack">
          <Select
            :value="answers[fieldId(field)]?.option_value"
            placeholder="请选择"
            :option-list="parseOptions(field).map((item) => ({ label: item.Text, value: item.Value }))"
            @change="(value: any) => selectOption(field, value)"
          />
          <Input
            v-if="isOtherOption(field)"
            :value="answers[fieldId(field)]?.other_value || ''"
            placeholder="请补充说明"
            @change="(value: string) => setAnswer(fieldId(field), { other_value: value })"
          />
        </div>
        <div v-else-if="fieldKind(field) === 'location'" class="jielong-location">
          <Input
            :class-name="invalidFields[fieldId(field)] ? 'is-invalid' : ''"
            :value="answers[fieldId(field)]?.area || ''"
            placeholder="填写市区"
            @change="(value: string) => setAnswer(fieldId(field), { area: value })"
          />
          <Input
            :class-name="invalidFields[fieldId(field)] ? 'is-invalid' : ''"
            :value="answers[fieldId(field)]?.place || ''"
            placeholder="填写地点"
            @change="(value: string) => setAnswer(fieldId(field), { place: value })"
          />
          <Input
            :class-name="invalidFields[fieldId(field)] ? 'is-invalid' : ''"
            :value="answers[fieldId(field)]?.longitude || ''"
            placeholder="经度"
            @change="(value: string) => setAnswer(fieldId(field), { longitude: value })"
          />
          <Input
            :class-name="invalidFields[fieldId(field)] ? 'is-invalid' : ''"
            :value="answers[fieldId(field)]?.latitude || ''"
            placeholder="纬度"
            @change="(value: string) => setAnswer(fieldId(field), { latitude: value })"
          />
          <TypographyText type="tertiary">请分别填写市区和地点，系统会自动用“•”拼接；下方经纬度需填写有效数字。</TypographyText>
        </div>
        <div v-else class="jielong-media">
          <div class="jielong-media-preview">
            <IconImage />
            <span>{{ (answers[fieldId(field)]?.files || []).map(imageName).join("、") || "未选择图片" }}</span>
          </div>
          <Space wrap>
            <Select
              placeholder="选择图片"
              :value="answers[fieldId(field)]?.files?.[0]?.LocalPath || ''"
              :option-list="props.images.map((image) => ({ label: image.name, value: image.path }))"
              @change="(value: any) => chooseImage(field, String(value || ''))"
            />
            <Button theme="light" @click="emit('openImageManager')">图片管理</Button>
            <Button theme="light" type="danger" @click="clearImage(field)">清空</Button>
          </Space>
        </div>
      </article>
    </section>

    <footer class="jielong-footer">
      <span :class="['jielong-status-chip', statusClass(status)]">{{ status }}</span>
      <Button type="primary" :icon="renderIcon(IconSend)" :disabled="!bundle || submitting" :loading="submitting" @click="submit">提交打卡</Button>
    </footer>

    <Modal
      :visible="qrVisible"
      title="接龙扫码登录"
      :has-cancel="false"
      ok-text="确定"
      :mask-closable="false"
      width="390px"
      @ok="closeQrModal"
      @cancel="closeQrModal"
    >
      <div class="jielong-qr">
        <TypographyText type="tertiary">请使用微信扫码确认登录，确认后会自动换取 Token。</TypographyText>
        <img v-if="qrImage" :src="qrImage" alt="接龙登录二维码" />
        <div v-else class="jielong-qr-placeholder">二维码将在这里显示</div>
        <Tag :color="loginStatus === '登录成功' ? 'green' : 'blue'">{{ loginStatus || "等待扫码" }}</Tag>
        <Button v-if="qrPolling" theme="light" :icon="renderIcon(IconTick)" @click="closeQrModal">后台等待</Button>
      </div>
    </Modal>
  </section>
</template>
