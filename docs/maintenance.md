# Maintenance and publishing

## Ownership

Repository: `lbouriez/ha.addon.codex`. Install this repository in HA directly.
The manifest consumed by `codex/config.yaml` is
`ghcr.io/lbouriez/ha.addon.codex:<version>`.
Per-architecture images are `ghcr.io/lbouriez/amd64-ha.addon.codex` and
`ghcr.io/lbouriez/aarch64-ha.addon.codex`. Original MIT attribution is retained.

The first publication may create private GHCR packages even for a public source
repository. Check all three packages and make them public so HA can pull without
registry credentials. Keep their Actions access linked to this repository.

## Pipeline

`.github/workflows/publish-codex.yml` runs on PRs, main pushes and manual dispatch.
It validates YAML, ownership, architecture consistency, translations, release
metadata, Python regressions and Bash syntax. Native AMD64 and ARM64 runners
build and smoke-test the actual image: CLI execution as root and the runtime
user, terminal startup, MCP enabled/disabled, and legacy model migration.
The real terminal launcher is also exercised with a harmless fake CLI to verify
YOLO on/off argument propagation and that tmux keeps work running through a
simulated client disconnect and reattaches to the same process.
The AMD64 job also runs Chromium against the built ttyd image under an ingress
path, including native clipboard shortcuts, iframe clipboard denial/fallback,
Unicode and multiline paste, history export, selection, responsive layout and
reconnection. Screenshots are retained as workflow artifacts. Run locally with
`cd codex/terminal`, `npm ci`, `npx playwright install chromium`, then
`TEST_IMAGE=<local-image> npm test` (set the environment variable using your shell).
The toolbar is injected into the checksum-pinned ttyd HTML during image build;
the build fails if the expected public `window.term` API disappears.
A disposable mock Supervisor also exercises the real unprivileged helpers:
official MCP initialization/tools/resources/prompts, REST, WebSocket queries and
subscriptions, configuration checks, file writes and credential isolation.
The real background daemon is installed, started, queried, stopped and restarted
as UID 22000 in a container with networking disabled. CI loads the shipped
AppArmor profile and applies it to the terminal and daemon tests; local Docker Desktop runs
without AppArmor unless `CODEX_TEST_APPARMOR` names an already loaded profile.

Only main in `lbouriez/ha.addon.codex` may publish. Both architectures must pass
before the signed multi-arch manifest is published. The HA builder's
`skip-existing` prevents overwriting an existing version: bump the add-on
version for every release. Re-running a partial publication can finish the
missing architecture/manifest. `latest` is for convenience; HA uses the exact
version in config.yaml. No personal token or `DISPATCH_TOKEN` is required:
publishing uses the repository's `GITHUB_TOKEN` and OIDC signing.

Plex was reviewed as a reference. Its reusable workflows publish per-architecture
images and dispatch releases to a separate `hassio-addons` repository. That
layout is not used here: this repository already contains its own HA repository
metadata. The old shared workflows also use deprecated `set-output` commands
and old action versions; copying them would not improve this pipeline.

## Releasing

1. Review the latest stable version with `npm view @openai/codex version`.
2. Update `ARG CODEX_VERSION` in `codex/Dockerfile` and the user documentation.
3. Increment `version` in `codex/config.yaml` and add the matching changelog entry.
4. Run `python scripts/validate.py` and `python -B -m unittest discover -s codex/tests -v`
   (Python 3.13, PyYAML and jq; CLI executable tests run on Linux).
5. Build locally with `docker build --build-arg BUILD_ARCH=amd64 -t codex-test codex`
   and run `python scripts/smoke.py codex-test`.
6. Push to main after review. Wait for both architectures and the manifest job.
7. Verify an unauthenticated pull of the versioned manifest, then refresh the
   repository in HA and install/update the App.

Dependabot maintains action/base-image updates. It does not update the npm
version embedded in the Dockerfile; that is a deliberate reviewed release step.
`auto_update_codex` remains an optional, independent startup update into `/data`.

## Limits of CI

The smoke tests use a fixture token against an isolated mock Supervisor and make
no model requests or real HA calls. They do not
validate your ChatGPT entitlement, device login, real HA service calls, or the
full Supervisor environment on a running HA OS VM. Browser tests use Chromium;
Safari, mobile operating-system clipboard menus and your actual HA ingress still
need installation verification. The
terminal and daemon tests enforce AppArmor on CI runners; the HA protocol fixture uses Docker defaults.
Confirm those after installing. Switching from a separately installed upstream
repository creates a separate HA add-on identity; back up existing Codex state
before uninstalling an old instance.
