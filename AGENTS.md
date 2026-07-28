# Repository Guidelines

## Git Commit Policy

Every completed change must be tracked in a descriptive, granular git commit.
Do not leave completed work uncommitted.

- Commit after each distinct logical unit of work, rather than batching a
  session's unrelated changes together.
- Keep each commit focused on one coherent change.
- Use informative commit messages in `type(scope): subject` format, with a body
  explaining what changed and why when the subject alone is insufficient.
- Stage files selectively so each commit contains only the files belonging to
  that logical unit.
- Do not amend, rewrite, or force-push commits unless the user explicitly asks.
- Before yielding a completed task, verify the work is committed with
  `git status --short` and `git log --oneline -3`.

## Documentation Synchronization

Keep documentation synchronized with the system's implemented capabilities.
Any edit, addition, or removal that changes functionality must include the
corresponding documentation update before the work is considered complete.

- Update the relevant user, operator, architecture, configuration, and command
  references in the same logical unit of work as the functional change.
- Document added capabilities, changed behavior or interfaces, migration or
  compatibility considerations, and removed or deprecated functionality.
- Check examples, usage instructions, and cross-references for stale behavior.
- If a functional change genuinely requires no documentation update, record
  that conclusion and its reason in the commit message or task report.

