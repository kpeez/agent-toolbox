/**
 * `import.meta.main` is missing on Node 23.6 to 24.1 and wrong on 24.2, so compare
 * real paths instead.
 */

import { realpathSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function isMain(moduleUrl: string): boolean {
  const entry = process.argv[1];
  if (!entry) return false;
  try {
    return realpathSync(resolve(entry)) === realpathSync(fileURLToPath(moduleUrl));
  } catch {
    return false;
  }
}
