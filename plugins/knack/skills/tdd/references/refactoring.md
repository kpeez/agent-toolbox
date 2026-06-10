# Refactor Candidates

After all tests pass, look for:

- **Duplication** → extract function/class
- **Long methods** → break into private helpers (keep tests on the public interface)
- **Shallow modules** → combine or deepen (see [deep-modules.md](deep-modules.md))
- **Feature envy** → move logic to where its data lives
- **Primitive obsession** → introduce value objects
- **Existing code** the new code reveals as problematic

Run tests after each refactor step. Never refactor while RED — get to GREEN
first.
