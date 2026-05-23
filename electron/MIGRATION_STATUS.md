# Electron Migration Status

## Implemented

- Electron + Vue3 + TypeScript project under `electron/`.
- Main process services:
  - Config read/write with existing `resources/config/config.json` compatibility.
  - Session cache in Electron `userData`.
  - Image import/list/delete.
  - XYB request client for login, plan lookup, geocode, normal sign, photo sign, OSS upload.
  - XYB header token and SM2 device code generation.
  - Task orchestration with cancellation.
  - Local Node proxy service, system proxy set/restore, certificate file generation.
  - IPC bridge and log streaming.
- Renderer:
  - Desktop dashboard.
  - Code capture controls with manual fallback.
  - Sign action controls.
  - Image library.
  - Log view.
  - Config editor.
- Tests:
  - Token structure/device code tests.
  - Config helper tests.

## Known Limits

- The Node proxy currently supports HTTP forwarding and HTTPS CONNECT tunneling.
- HTTPS body decryption for automatic `common/getOpenId.action` capture is not fully implemented yet. The UI includes a manual code fallback.
- Package management is pnpm-based (`packageManager: pnpm@10.33.0`). `pnpm typecheck` and `pnpm test` pass in this checkout.
- `electron` is allowed in `pnpm.onlyBuiltDependencies`, so its postinstall downloads the Electron binary. If `Electron uninstall` appears again, run `pnpm rebuild electron`.

## Next Technical Step

Implement full Node HTTPS MITM:

1. Persist CA private key as well as cert.
2. Generate per-host certificates signed by the CA.
3. Terminate client TLS in the proxy for CONNECT requests.
4. Forward decrypted requests to upstream TLS.
5. Capture `code` from decrypted `common/getOpenId.action` request bodies.
