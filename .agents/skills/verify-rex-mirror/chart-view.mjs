// The statechart view for chart.cfg: one mirrored command, seen from its Rex block.
const m = "m1";

export const title = "A mirrored background command's Rex block";

export const state = (v) => {
  const block = v.block[m];
  const status = v.status[m];
  if (block === "none") return ["start", "log"].includes(v.mpc[m]) ? "Starting" : "No block";
  if (block === "closed") return status === "done" ? "Closed after done" : "Closed after error";
  if (status === "done" || status === "error") {
    return v.closeFailed[m] ? `Shows ${status}, left open` : `Shows ${status}, closes in 1 s`;
  }
  return v.mpc[m] === "dead" ? "Working forever" : "Working";
};

export const group = (v) => {
  const s = state(v);
  if (s === "Working forever") return "stuck";
  if (s.startsWith("Shows") || s.startsWith("Closed")) return "settled";
  return "running";
};

export const colors = { running: "blue", settled: "teal", stuck: "orange" };

const labels = {
  MirrorCreatesLog: "the mirror creates its log",
  MirrorOpensBlock: "the mirror opens a block",
  MirrorGetsNoBlock: "rex run fails",
  Kill: "Claude Code stops the task [before the mirror sets its signal handlers]",
  ViewerClosesBlock: "the viewer closes the block",
  ViewerCloseFails: "the close fails (session end retries it)",
};

export const step = (action, from, to) => {
  if (action === "ViewerReadsExitLine") {
    return to.status[m] === "done" ? "the command exits 0" : "the command fails, or is stopped";
  }
  return labels[action] ?? action;
};
