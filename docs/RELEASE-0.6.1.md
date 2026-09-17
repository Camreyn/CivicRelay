# CivicRelay 0.6.1 — complete assistant setup

This source-only patch fixes the starter configuration for local assistant tools.
The original 0.6.0 configuration enabled 20 of the 40 records tools. New generated
configurations now expose all 40 records tools plus the 8 mail tools, including
workspace settings, custom templates, campaigns, response tracking, publication
destinations and equipment-request tracking.

## What changed

- Completed the records-server tool allowlist; no tool schemas or host permission
  defaults were weakened.
- Added five configuration regressions to the normal test/CI suite. They parse
  generated TOML, detect omitted/duplicate/stale/disabled tools, preserve existing
  configurations, and exercise both real local MCP servers with synthetic data.
- Documented new-user connection checks, template/campaign delegation, existing
  configuration upgrades, and the limits of clients without local tool access.
- Updated package, health and records-tool version reporting to 0.6.1. Dependency
  versions and the public catalog/form/map snapshot are unchanged.

## Existing users: review the tool allowlist

Updating source does not overwrite a live `.codex/config.toml`. Compare the
`records_desk.enabled_tools` list in the configuration your assistant actually
uses with the corrected template and add the tools you want available. Preserve
absolute paths, other servers, intentional restrictions and permission choices.
Restart the CivicRelay tool connections afterward. Restarting alone cannot repair
an old allowlist; do not delete the whole configuration or re-enroll your mailbox.

See the [setup and upgrade guide](https://github.com/Camreyn/CivicRelay/blob/v0.6.1/docs/SETUP.md#upgrading-an-existing-assistant-configuration)
and [configuration template](https://github.com/Camreyn/CivicRelay/blob/v0.6.1/docs/mcp-config.example.toml).

## Verification and limits

The release checks cover 183 automated tests (50 Node, 83 application Python,
50 connector Python), documentation/schema checks, three synthetic browser suites,
publication-safety checks and a clean-checkout locked-dependency rehearsal.

MCP integration is tested with the SDK using generated settings, not through a
particular assistant's UI/trust/permission dialogs. Mail and public-issue actions
use fake transports in tests; passing is not proof of real recipient delivery.
See [testing details](https://github.com/Camreyn/CivicRelay/blob/v0.6.1/docs/TESTING.md).

No mailbox credentials, real messages, attachments, private templates, operational
databases or machine-specific configuration are included. No live mail, fees,
records publication, new enrollment, storage migration or permission changes
are part of this patch or its verification. Source archives are not a Windows
installer. The existing Windows/Python/Node/Proton Bridge prerequisites still apply.
