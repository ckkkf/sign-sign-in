# SignSignIn Electron

Electron + Vue3 + TypeScript desktop rewrite for the core SignSignIn workflow.

## Commands

```bash
pnpm install
pnpm dev
pnpm typecheck
pnpm test
pnpm dist
```

## Current Scope

- Core desktop UI: status, code capture, sign actions, image library, logs, config.
- Node/TypeScript services for XYB token generation, login, plan lookup, geocode, normal sign, photo sign, config, session cache, proxy state.
- Python/PySide6 code is left untouched as a behavior reference.

## Notes

- Runtime config is copied from `../resources/config/config.json` into Electron `userData` on first launch.
- The Node proxy listens on `127.0.0.1:13140` and can set/restore system HTTP/HTTPS proxy on macOS/Windows.
- HTTPS traffic is currently forwarded with CONNECT tunneling, not decrypted as a full MITM implementation. If automatic code capture cannot read the encrypted request body, paste the code into the fallback field in the UI.
