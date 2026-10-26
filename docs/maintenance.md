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

The smoke tests have no HA credentials and make no model requests. They do not
validate your ChatGPT entitlement, device login, real HA service calls, browser
interaction or the Supervisor-enforced AppArmor profile on a running HA OS VM.
Confirm those after installing. Switching from a separately installed upstream
repository creates a separate HA add-on identity; back up existing Codex state
before uninstalling an old instance.
