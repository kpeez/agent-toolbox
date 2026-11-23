export const title = "A plugin change from PR to every config folder";

export const state = (v) => {
  const pr = v.pr.pr1;
  if (pr === "none") return "No PR open";
  if (pr === "open") return "PR open";
  if (pr === "green") return "Checks pass";
  if (pr === "red") return "Checks fail";
  const stale = Object.keys(v.installed).filter((d) => v.installed[d] !== v.coreRev);
  if (stale.length === 0) return "Every folder on the merged commit";
  if (v.ran.c1 && v.ran.h1) return "README steps done, another Claude Code folder stale";
  return stale.length === Object.keys(v.installed).length ? "Merged, no folder updated" : "Merged, some folders updated";
};

export const group = (v) => {
  const s = state(v);
  if (s === "Every folder on the merged commit" || s === "No PR open") return "current";
  if (s.startsWith("README")) return "stale";
  return s.startsWith("Merged") ? "rollout" : "pr";
};

export const colors = { pr: "blue", rollout: "yellow", current: "teal", stale: "orange" };

const folder = (from, to) =>
  Object.keys(to.installed).find((d) => to.installed[d] !== from.installed[d]) ??
  Object.keys(to.ran).find((d) => to.ran[d] && !from.ran[d]);

export const step = (action, from, to) => {
  if (action === "PrOpens") return "a PR edits a plugin";
  if (action === "ChecksRun") return to.pr.pr1 === "green" ? "the checks pass" : "the checks fail";
  if (action === "PrMerges") return "the PR merges";
  if (action === "HermesInstalls") return "you install the merged SHA in the Hermes profile";
  if (action === "ClaudeUpdates") {
    return folder(from, to) === "c1"
      ? "you run the README update steps"
      : "you run them again under another CLAUDE_CONFIG_DIR";
  }
  return null;
};
