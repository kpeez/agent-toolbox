// The statechart view for chart.cfg: one mirrored command, seen from its Rex block.
const m = "m1";

export const title = "A mirrored background command's Rex block";

// The block that opened: the floating layer, or else the fallback `rex run` block.
const slot = (v) => (v.block[m].layer !== "none" ? "layer" : "run");

export const state = (v) => {
  const k = slot(v);
  const block = v.block[m][k];
  const status = v.status[m][k];
  if (block === "none") {
    if (v.mpc[m] === "ended" || v.mpc[m] === "dead") return "No block";
    return v.opc[m] === "timer" || v.opc[m] === "none" ? "Starting" : "Opening";
  }
  if (block === "closed") return status === "done" ? "Closed after done" : "Closed after error";
  if (status === "done" || status === "error") {
    return v.closeFailed[m][k] ? `Shows ${status}, left open` : `Shows ${status}, closes in 1 s`;
  }
  const stuck = (v.mpc[m] === "ended" || v.mpc[m] === "dead") && v.exitLine[m] === -1;
  return stuck ? "Working forever" : "Working";
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
  MirrorInstallsHandlers: "the mirror sets its signal handlers",
  MirrorTimerFires: "the open delay passes",
  MirrorInspects: "the mirror asks Rex for a floating pane",
  ServerOpens: "Rex opens the pane",
  ServerRefuses: "Rex refuses the pane",
  MirrorLayerGivesUp: "the pane request dies before its reply",
  MirrorRunGivesUp: "the `rex run` request dies before its reply",
  MirrorReadsEnd: "the mirror reads the end of the output",
  MirrorHandlesSignal: "the mirror handles the stop signal",
  Kill: "Claude Code stops the task",
  ViewerClosesBlock: "the viewer closes the block",
  ViewerCloseFails: "the close fails (session end retries it)",
};

export const step = (action, from, to) => {
  if (action === "ViewerReadsExitLine") {
    return to.status[m][slot(to)] === "done" ? "the command exits 0" : "the command fails, or is stopped";
  }
  return labels[action] ?? action;
};
