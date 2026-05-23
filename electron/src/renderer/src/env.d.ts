/// <reference types="vite/client" />

import type { SignSignInApi } from "@shared/ipc";

declare global {
  interface Window {
    signSignIn: SignSignInApi;
  }
}

export {};
