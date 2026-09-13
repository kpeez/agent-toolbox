# Stacked pull requests

Read this reference only when the user or established task design calls for a
dependent branch chain. Confirm the stack order and base relationships from
current evidence. Each pull request must stand alone for its own diff.

Use stack tooling's documented publication and merge behavior. Put a fix on
the lowest branch that owns the code, then replay branches above it. Do not
convert ordinary tasks into a stack merely to create a grouping layer.
