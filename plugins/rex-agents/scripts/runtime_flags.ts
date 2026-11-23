/** Node 23.6 to 24.2 prints an ExperimentalWarning to stderr for each `.ts` file it runs. */
export function runtimeFlags(): string[] {
  return process.versions.bun === undefined ? ["--disable-warning=ExperimentalWarning"] : [];
}
