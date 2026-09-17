# Fresh-install rehearsal

This is a synthetic source/dependency rehearsal for the CivicRelay 0.6.0
candidate. It does not enroll a mailbox, read an existing private store, contact
Bridge or GitHub, send mail, synchronize mail, publish, or create an external
account.

## Method

The final refreshed rehearsal copied 98 tracked or nonignored candidate files into a separate
clean directory under `.etl/relay-general-build/rehearsal/clean-source`. The
copy excludes `.git`, `.private`, and `node_modules`; it is not a clone of any
live mailbox/profile. The copy helper uses `git ls-files --cached --others
--exclude-standard`, so ignored private material is not included.

`npm.cmd ci --ignore-scripts` completed against the copied `package-lock.json`:
18 packages were installed and npm reported no audit vulnerabilities. This
confirms that the documented Node/Python prerequisites and lockfile are enough
to install the JavaScript dependencies for this rehearsal.

## Offline checks

- `npm.cmd run test:docs` passed in the initial clean copy with
  `network_accessed:false`. After the generated tool reference was refreshed in
  the candidate, the same check also passed from the source candidate with 21
  Markdown files, 57 local links, 24 documented commands, and 48 native-tool
  schemas checked.
- `python -m py_compile` was run over copied `app/` and `connector/` Python
  files without a syntax error.
- A newly created empty Windows Temp directory was used as `LOCALAPPDATA` for
  `proton_status`. It returned `configured:false`, no email/display/profile ID,
  `legacy_storage:false`, a fresh `CivicRelay\ProtonConnector` path, and
  `network_accessed:false`.
- The same kind of empty synthetic profile returned the blank workspace defaults
  from `desk_get_workspace`: revision zero, blank profile fields, starter pack
  `blank`, and no configured account.

The temporary profile directory was outside the Git worktree and removed in the
same command. An initial attempt to put synthetic `LOCALAPPDATA` under the
rehearsal directory was correctly refused by the private-storage Git-worktree
guard; that refusal is expected security behavior, not a setup workaround.

## Rehearsal suite evidence

After refreshing the final candidate into the clean dependency installation,
`npm.cmd test` completed successfully: 45 Node tests, 83 application Python tests,
50 connector Python tests, and the documentation checks (21 Markdown files,
59 local links, 24 documented commands, 48 native schemas). The documented JSON
template example is imported and rendered by a regression test.

All three synthetic browser suites also passed in the candidate source. The
generic story verifies profile persistence, template preview/duplicate/archive/
export/import, frozen request versions, remaining targets, exact fake SMTP
acceptance, assigned incoming mail, attachment capture, a real temporary ZIP,
response evidence, destination invalidation, fake publication and uncertain
outcome reconciliation. Desktop and narrow-window synthetic screenshots were
inspected. No real mail or public issue was sent by any rehearsal.

These results do not verify real provider delivery, current agency procedures,
an actual GitHub repository's permissions, or a cloud/multi-account deployment.
