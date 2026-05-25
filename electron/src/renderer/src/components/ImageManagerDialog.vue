<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Space from "@kousum/semi-ui-vue/dist/space";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import {
  IconDeleteStroked,
  IconEditStroked,
  IconFolderOpen,
  IconImage,
  IconRefresh,
  IconUpload
} from "@kousum/semi-icons-vue";
import { computed, ref, watch } from "vue";
import type { ImageItem } from "@shared/types";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  visible: boolean;
  images: ImageItem[];
  selectedImage: string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "select", path: string): void;
  (event: "import"): void;
  (event: "rename", path: string, name: string): void;
  (event: "replace", path: string): void;
  (event: "delete", path: string): void;
  (event: "refresh"): void;
  (event: "openDir"): void;
}>();

const activePath = ref("");
const renameValue = ref("");

const activeImage = computed(() => props.images.find((image) => image.path === activePath.value) || props.images[0]);
const activeSize = computed(() => {
  const size = activeImage.value?.size || 0;
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
});
const activeUpdatedAt = computed(() => {
  if (!activeImage.value?.updatedAt) return "-";
  return new Date(activeImage.value.updatedAt).toLocaleString();
});

watch(
  () => [props.visible, props.selectedImage, props.images] as const,
  () => {
    if (!props.visible) return;
    const next = props.images.find((image) => image.path === props.selectedImage)?.path || props.images[0]?.path || "";
    activePath.value = next;
    renameValue.value = props.images.find((image) => image.path === next)?.name || "";
  },
  { immediate: true }
);

watch(activeImage, (image) => {
  renameValue.value = image?.name || "";
});

function selectImage(path: string) {
  activePath.value = path;
  emit("select", path);
}

function renameActive() {
  if (!activeImage.value) return;
  emit("rename", activeImage.value.path, renameValue.value);
}
</script>

<template>
  <Modal
    :visible="visible"
    title="图片管理"
    width="760px"
    footer=""
    @cancel="emit('close')"
  >
    <section class="image-manager">
      <header class="image-manager-toolbar">
        <Space wrap>
          <Button type="primary" :icon="renderIcon(IconUpload)" @click="emit('import')">导入图片</Button>
          <Button theme="light" :icon="renderIcon(IconRefresh)" @click="emit('refresh')">刷新</Button>
          <Button theme="light" :icon="renderIcon(IconFolderOpen)" @click="emit('openDir')">打开目录</Button>
        </Space>
        <TypographyText type="tertiary">{{ images.length }} 张图片</TypographyText>
      </header>

      <div class="image-manager-body">
        <section class="image-library-grid">
          <button
            v-for="image in images"
            :key="image.path"
            :class="['image-tile', { 'is-active': image.path === activeImage?.path }]"
            type="button"
            @click="selectImage(image.path)"
          >
            <img :src="image.previewUrl" :alt="image.name" />
            <span>{{ image.name }}</span>
          </button>
          <div v-if="!images.length" class="image-empty">
            <IconImage />
            <span>图片库为空</span>
          </div>
        </section>

        <aside class="image-detail-panel">
          <div class="image-preview-box">
            <img v-if="activeImage" :src="activeImage.previewUrl" :alt="activeImage.name" />
            <IconImage v-else />
          </div>

          <label class="login-field">
            <span>图片名称</span>
            <Input
              :value="renameValue"
              placeholder="例如 sign-photo.png"
              :disabled="!activeImage"
              show-clear
              @change="(value: string) => (renameValue = value)"
            />
          </label>

          <div class="image-meta">
            <span>大小</span>
            <strong>{{ activeSize }}</strong>
            <span>更新时间</span>
            <strong>{{ activeUpdatedAt }}</strong>
          </div>

          <Space wrap>
            <Button theme="light" :disabled="!activeImage" :icon="renderIcon(IconEditStroked)" @click="renameActive">重命名</Button>
            <Button theme="light" :disabled="!activeImage" :icon="renderIcon(IconUpload)" @click="activeImage && emit('replace', activeImage.path)">替换图片</Button>
            <Button theme="light" type="danger" :disabled="!activeImage" :icon="renderIcon(IconDeleteStroked)" @click="activeImage && emit('delete', activeImage.path)">删除</Button>
          </Space>
        </aside>
      </div>
    </section>
  </Modal>
</template>
