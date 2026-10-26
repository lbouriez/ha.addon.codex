# Upstream PR review — 2026-10-26

The fork and upstream main both started at `2074535f543ec0f649307caa3d0ddedfd9bf1db7`.
The existing merged PR #1 is already included. The open PRs below were inspected
at their fetched heads; none had been merged upstream at review time.

| PR | Decision | Reason |
| --- | --- | --- |
| [#6](https://github.com/kecksdigital/codex-hass/pull/6) | Adapted | Fixes ignored `enable_mcp: false`. Preserve the default when the option is absent as well. Includes configuration regression coverage. |
| [#7](https://github.com/kecksdigital/codex-hass/pull/7) | Adapted | Makes optional CLI updates persistent and executable under AppArmor. Add a version/health check so stale or broken installs do not shadow the bundled CLI. |
| [#3](https://github.com/kecksdigital/codex-hass/pull/3) | Not imported | Its model is already superseded; it also changes defaults to root, full access, and no approvals. This fork follows the current CLI model default and retains the existing permission choices. |
| [#4](https://github.com/kecksdigital/codex-hass/pull/4) | Deferred | The one-shot toggle still installs into the nonpersistent root prefix, conflicting with #7. Manual npm updates and optional startup updates already cover updating the CLI. |
| [#8](https://github.com/kecksdigital/codex-hass/pull/8) | Deferred | Useful mobile controls, but introduces a patched ttyd frontend and generated HTML. Needs separate browser/mobile validation and reproducible frontend builds. |
| [#9](https://github.com/kecksdigital/codex-hass/pull/9) | Useful follow-up | Adds managed remote MCP servers and environment variables, depending on #6. Separate feature scope; review reserved runtime environment variables and existing server/header handling before import. |
| [#10](https://github.com/kecksdigital/codex-hass/pull/10) | Deferred | Adds SSH, credentials, host keys and a new network listener on top of #9. Keep optional until direct SSH access is wanted and HA OS networking is tested. |

Imported source heads: #6 `0704b50a9ec5f6cc58c84d593db4c8a8fc19e1f7`,
#7 `eb3bd2968363f5f67dc2dd69fe87a70fb909e9f5`.
Changes are adapted into the fork release rather than merging incompatible
version/changelog entries from stacked PRs.
