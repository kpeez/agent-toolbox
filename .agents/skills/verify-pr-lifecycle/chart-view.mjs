const p = 1;

export const title = "A pull request from local work to merged";

const issue = { started: "issue In Progress", review: "issue In Review", done: "issue Done" };

export const state = (v) => {
  const pr = v.pr[p];
  if (pr === "none") return v.request === "hold" ? "Local only, no authority to publish" : "Local work";
  if (pr === "merged") return `Merged, ${issue[v.issue]}`;
  if (v.readyBy[p] === "finalize") return `Ready for human review, ${issue[v.issue]}`;
  const name = pr === "draft" ? "Draft" : "Ready";
  if (v.trusted[p] !== -1) {
    return v.trusted[p] === v.head[p] ? `${name}, PASS, rechecked` : `${name}, head moved after the recheck`;
  }
  return v.vres[p] === "pass" && v.vpatch[p] === v.head[p] ? `${name}, PASS` : `${name}, no PASS for this patch`;
};

export const group = (v) => {
  const pr = v.pr[p];
  if (pr === "none") return "local";
  if (pr === "merged") return "merged";
  return pr === "ready" ? "ready" : "draft";
};

export const colors = { local: "blue", draft: "teal", ready: "orange", merged: "purple" };

const labels = {
  Publish: "the agent commits, pushes, and opens a draft",
  Push: "someone pushes a new patch",
  Recheck: "the agent fetches and compares the patch-id",
  MarkReady: "the agent marks the draft ready (Land)",
  FinalizeReady: "the agent marks the draft ready (Finalize)",
  Merge: "the agent merges, pinned to the rechecked head",
  MergeRefused: "GitHub refuses the pinned merge: the head moved",
  IssueToReview: "the agent moves the issue to In Review",
  IssueToDone: "the issue moves to Done",
  TrackerClosesIssue: "the issue moves to Done",
};

export const step = (action, from, to) => {
  if (action === "GetVerdict") return to.vres[p] === "pass" ? "an independent verifier says PASS" : null;
  return labels[action] ?? action;
};
