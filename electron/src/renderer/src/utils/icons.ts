import { h } from "vue";

export function renderIcon(icon: unknown, size = "small") {
  return h(icon as never, { size });
}
