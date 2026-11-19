/**
 * Flags to put before a `.ts` path when this process launches another one with `process.execPath`.
 *
 * Node 23.6 to 24.x prints an ExperimentalWarning to stderr for each `.ts` file it runs.
 * `scripts/run-ts` suppresses it with the same flag. Bun needs no flag.
 */
export function runtimeFlags(): string[] {
  return process.versions.bun === undefined ? ["--disable-warning=ExperimentalWarning"] : [];
}
