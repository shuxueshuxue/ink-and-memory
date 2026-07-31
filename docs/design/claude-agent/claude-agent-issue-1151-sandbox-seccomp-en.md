# `sandbox.seccomp.applyPath` in settings.json is ignored — embedded apply-seccomp is always used (CLI 2.1.220)

## Summary

The `sandbox.seccomp.applyPath` / `sandbox.seccomp.bpfPath` settings keys — which the CLI itself advertises as the override mechanism for the seccomp helper ("copy vendor/seccomp/* from sandbox-runtime and set `sandbox.seccomp.bpfPath` and `applyPath` in settings.json") — are **silently ignored** by the CLI's embedded Linux sandbox path in 2.1.220. The settings→runtime converter hardcodes the seccomp config to the embedded executor (`/proc/self/fd/*`), so there is no supported way to replace or disable apply-seccomp. In Docker / nested-userns environments this makes sandboxed Bash commands fail hard with:

```
apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied
```

## Environment

- `@anthropic-ai/claude-code` **2.1.220** (linux-x64, npm, single 275 MB self-contained binary)
- `claude-agent-sdk` (Python) 0.2.128 (issue is in the CLI, reproduced both via the SDK subprocess and directly)
- Docker (Debian bookworm base, `cap_add: SYS_ADMIN`, `seccomp=unconfined`, `apparmor=unconfined`; host `kernel.apparmor_restrict_unprivileged_userns=0`)

## Expected behavior

Per the CLI's own hint text (visible in the binary: *"or copy vendor/seccomp/* from sandbox-runtime and set `sandbox.seccomp.bpfPath` and `applyPath` in settings.json"*), setting the following in the loaded `settings.json` should make the sandbox invoke the given executable instead of the embedded apply-seccomp:

```json
{
  "sandbox": {
    "enabled": true,
    "seccomp": { "applyPath": "/usr/local/share/claude-agent/apply-seccomp-passthrough" }
  }
}
```

(Our use case: a passthrough shim that neutralizes apply-seccomp, the standard workaround for nested-userns Docker environments where writing `/proc/self/setgroups` is impossible. This is exactly what the settings override appears to be designed for.)

## Actual behavior

The key is never read. The embedded apply-seccomp (executed via `/proc/self/fd/`) always runs, and the sandboxed command fails with the `setgroups` Permission denied error above.

## Evidence

1. **The settings→runtime converter does not read the key.** On the Linux binary:
   ```
   strings claude.exe | grep -c "sandbox?.seccomp"     → 0
   strings claude.exe | grep -c "/proc/self/fd/"        → 16
   ```
   The converter never touches `sandbox.seccomp`, while sibling fields are read normally.
2. **The converter hardcodes the embedded executor.** In the (more readable) macOS build, the sandbox settings→runtime converter returns `seccomp: jCu()` — the embedded `{applyPath: "/proc/self/fd/3", argv0: "apply-seccomp"}` — while every sibling field is sourced from `e.sandbox?.<field>` (`ignoreViolations`, `enableWeakerNestedSandbox`, `enableWeakerNetworkIsolation`, `allowAppleEvents`, …). `seccomp` is the only field not taken from settings.
3. **Functional proof.** Pointing `sandbox.seccomp.applyPath` at a logging shim (`#!/bin/sh; echo "$@" >> /tmp/shim.log; exec "$@"`) produces **zero invocations** while sandboxed commands run and fail.
4. **The hint string is present but unwired.** `strings` shows both `sandbox.seccomp.bpfPath and applyPath in settings.json` and the consumer log lines (`[SeccompFilter] Using apply-seccomp binary from explicit path: …`) — the explicit-path code path exists, but the settings key never reaches it on the embedded path. It presumably only works for the standalone `srt` sandbox-runtime CLI, which reads the same settings schema through a different code path.

## Impact

- **There is currently no supported way to run the Linux Bash sandbox in Docker / nested-userns environments with CLI 2.1.220.** Sandboxed Bash fails deterministically.
- The previous escape hatch is gone: ≤2.1.108 shipped `vendor/seccomp/apply-seccomp` on disk, which deployments could replace; 2.1.220's single-file binary removed that surface (the embedded helper is executed via `/proc/self/fd/`).
- The documented-looking settings override is a trap: it fails **silently** — the configuration is accepted, `settings.json` shows it, yet behavior never changes, making this extremely hard to diagnose.

## Suggested fixes (any one)

1. Honor `sandbox.seccomp.applyPath` / `bpfPath` from settings in the embedded converter (with whatever settings-source scoping you deem safe — e.g. user/managed settings only), instead of hardcoding the embedded executor;
2. Or provide an explicit override channel (env var / CLI flag) for the apply-seccomp path;
3. Or restore an on-disk vendor location for the seccomp helper so deployments can patch it;
4. At minimum, **warn** when `sandbox.seccomp` is present in settings but ignored — silent no-op configs are the worst kind.

## Reproduction

1. Docker container (bookworm): `npm install -g @anthropic-ai/claude-code@2.1.220 bubblewrap socat`.
2. Create a project `.claude/settings.json` with `"sandbox": {"enabled": true, "seccomp": {"applyPath": "/path/to/logging-shim"}}`.
3. Run any sandboxed Bash command through the CLI (e.g. via the Agent SDK with `cwd` set to that project).
4. Observe: command fails with `apply-seccomp: write /proc/self/setgroups … Permission denied`; the shim is never invoked (no log output).

## Workaround we currently ship (Docker, apply-seccomp passthrough patch)

We currently pin the CLI to **2.1.108** and patch its **on-disk** `vendor/seccomp/apply-seccomp` to a passthrough at image build time — confirming the sandbox otherwise works fine in the same environment. The full recipe:

```dockerfile
# Claude Code + sandbox-runtime.
# Patch apply-seccomp to passthrough to avoid nested userns / setgroups failure in Docker.
ARG CLAUDE_CODE_VERSION=2.1.108
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm bubblewrap socat; \
    npm install -g \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@anthropic-ai/sandbox-runtime"; \
    # Build-time assertion: the platform binary must actually be runnable
    # (2.1.220 taught us optional deps can silently miss, leaving a dead wrapper).
    claude --version; \
    # Neutralize apply-seccomp: replace every vendored helper with a passthrough.
    APPLY_SECCOMP_ROOT="$(npm root -g)/@anthropic-ai/claude-code/vendor/seccomp"; \
    test -d "$APPLY_SECCOMP_ROOT"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print \
        -exec sh -c 'printf "%s\n" "#!/bin/sh" "exec \"\$@\"" > "$1"; chmod +x "$1"' sh {} \; ; \
    echo "Patched Claude Code apply-seccomp passthrough:"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print -exec head -n 2 {} \; ; \
    npm cache clean --force
```

Container runtime flags (compose equivalent):

```yaml
cap_add:
  - SYS_ADMIN      # bubblewrap mount-namespace setup inside Docker
security_opt:
  - seccomp=unconfined
  - apparmor=unconfined
```

What the patch does and why it is safe for our threat model:

- The sandbox's network/filesystem isolation is enforced by **bwrap** (`--unshare-net`, bind mounts) plus the host-side filtering proxy — **not** by seccomp. apply-seccomp only adds unix-socket blocking on top.
- Replacing apply-seccomp with `#!/bin/sh` + `exec "$@"` makes the seccomp step a no-op while leaving bwrap isolation fully intact (the CLI even treats a missing seccomp helper as a warning, not an error — "seccomp not available - unix socket access not restricted").
- **This workaround is impossible with 2.1.220**: the CLI is a single self-contained binary, `vendor/seccomp/` no longer exists on disk, the helper is executed from `/proc/self/fd/`, and the settings-driven override (`sandbox.seccomp.applyPath`) is silently ignored — which is exactly the bug reported above.
