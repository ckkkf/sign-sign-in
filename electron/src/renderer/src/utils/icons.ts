import { h } from "vue";

export function renderIcon(icon: unknown) {
  return h(icon as never, { size: "small" });
}
