// The statechart view of EvalBudget.tla: the batch as the person who runs it sees it.
const STOPS = { budget: "Stopped: budget", cost: "Stopped: a run's cost is unknown", errors: "Stopped: errors in a row" };

const held = (v) => Object.values(v.pc).filter((pc) => pc !== "idle").length;

export const title = "Eval batch budget";

export const state = (v) => {
  if (v.stop !== "none") return STOPS[v.stop];
  const n = held(v);
  const phase = v.restarts > 0 ? "Resumed" : "First run";
  if (n === 0 && v.todo.length === 0) return `${phase}: plan done`;
  return `${phase}: ${n === 0 ? "no launch" : n === 1 ? "1 launch" : `${n} launches`} in flight`;
};

export const step = (action, from, to) =>
  ({
    Reserve:
      to.stop === "budget" && from.stop === "none"
        ? "the budget check refuses the next launch"
        : held(to) > held(from)
          ? "a worker reserves a run"
          : "a worker skips a run that ended",
    Release: to.stop !== "none" && from.stop === "none" ? "a launch ends with no known cost" : "a launch ends and frees its slot",
    Resume: "the process dies and a rerun resumes",
    Prepare: "a worker prepares the run folder",
    LaunchStart: "the launch starts",
    LaunchEnd: "the launch ends",
    Done: null,
  })[action];

export const group = (v) => (v.stop !== "none" ? "stopped" : "running");
export const colors = { stopped: "orange", running: "blue" };
