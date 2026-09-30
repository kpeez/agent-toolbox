# Delegation preflight

Before dispatching a bounded worker, check the effective provider, model, role,
tool access, write scope, and host capability against the user's and project's
current constraints. A role name or provider default does not prove its model
or permissions are allowed. Select a configurable permitted route or report
the limitation; do not silently substitute a model or provider.

Give each worker one objective with acceptance criteria, relevant requirements
and source paths, file ownership or an isolated checkout for writes, allowed
actions, checks, and a route back to the caller for blockers or material
decisions. Workers should return concise status, changed paths or artifacts,
evidence, and unresolved concerns. The lead verifies the assembled outcome.

For an external CLI or ACP provider, confirm its actual tool, path, and URL
permissions in addition to the host sandbox. Prompt wording alone does not
make a task read-only. If a model constraint applies, resolve and set an
allowed model explicitly; an omitted model may inherit a provider default.
Stop when an allowed model or required permission mode cannot be established.
