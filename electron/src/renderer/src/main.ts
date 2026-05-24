import { createApp } from "vue";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import App from "./App.vue";
import "@kousum/semi-ui-vue/dist/_base/base.css";
import "./styles/base.css";

Toast.config({ zIndex: 3000 });

createApp(App).mount("#app");
