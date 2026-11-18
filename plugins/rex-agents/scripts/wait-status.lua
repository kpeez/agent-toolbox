-- wait-status.lua: wait until a block's program reports a settled status, or its program exits.
--
--   rex do -s <session> wait-status.lua block=<block> [timeout=600] [states=done,blocked,error,idle] [after=<RFC 3339>]
--
-- First reads the block's current state, so a status reported before the wait
-- began is not missed: the newest status record, if it is in `states` and newer
-- than `after`, or the program's exit, returns at once. Otherwise waits for a
-- program_status_changed or child_exited event from the block. Events buffer
-- from the moment the script starts, so none is lost between the read and the
-- wait. Prints one JSON object. Exits 2 on timeout.
--
-- Pass the `updated_at` of the last record you acted on as `after`, so the next
-- wait returns only for a newer record.

local TERMINAL = "com.superlogical.terminal"
local block = rex.args.block
if not block then
  print(rex.json.encode({ error = "block is required" }))
  rex.stop(1)
end
local timeout = tonumber(rex.args.timeout) or 600

local wanted = {}
for state in string.gmatch(rex.args.states or "done,blocked,error,idle", "[^,]+") do
  wanted[state] = true
end

-- Seconds since the epoch for an RFC 3339 time, such as 2026-11-18T01:39:11.98-08:00.
local function epoch(ts)
  local y, mo, d, h, mi, s, frac, zone =
    string.match(ts or "", "^(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)(%.?%d*)(.*)$")
  if not y then return nil end
  y, mo, d = tonumber(y), tonumber(mo), tonumber(d)
  if mo <= 2 then y = y - 1 end
  local era = math.floor(y / 400)
  local yoe = y - era * 400
  local doy = math.floor((153 * (mo + (mo > 2 and -3 or 9)) + 2) / 5) + d - 1
  local days = era * 146097 + yoe * 365 + math.floor(yoe / 4) - math.floor(yoe / 100) + doy - 719468
  local t = days * 86400 + tonumber(h) * 3600 + tonumber(mi) * 60 + tonumber(s) + (tonumber("0" .. frac) or 0)
  local sign, oh, om = string.match(zone, "^([+-])(%d%d):?(%d%d)$")
  if sign then
    local offset = tonumber(oh) * 3600 + tonumber(om) * 60
    t = sign == "+" and t - offset or t + offset
  end
  return t
end

local after = rex.args.after and epoch(rex.args.after) or nil

local function settled(record)
  if not record or not wanted[record.state] then return false end
  if after then
    local t = epoch(record.updated_at)
    return t ~= nil and t > after
  end
  return true
end

local function report(event, record, extra)
  local out = { block = block, event = event }
  for _, key in ipairs({ "state", "kind", "msg", "app", "updated_at" }) do
    out[key] = record and record[key] or nil
  end
  for key, value in pairs(extra or {}) do out[key] = value end
  print(rex.json.encode(out))
  rex.stop(0)
end

-- Read the current state first.
local status, err = rex.block.call(TERMINAL, "program_status", { block_id = block })
if not status then
  print(rex.json.encode({ block = block, error = err }))
  rex.stop(1)
end
local newest
for _, record in ipairs(status.records or {}) do
  if not newest or (epoch(record.updated_at) or 0) > (epoch(newest.updated_at) or 0) then newest = record end
end
if settled(newest) then report("status", newest) end
local process = rex.block.call(TERMINAL, "process", { block_id = block })
if process and process.last_exit and not process.child then
  report("child_exited", nil, { exit_code = process.last_exit.exit_code })
end

-- Then wait for a newer report or the program's exit.
local ev = rex.wait("block_event", function(e, ctx)
  if ctx.block_id ~= block then return false end
  if e.name == "child_exited" then return true end
  return e.name == "program_status_changed" and settled(e.payload and e.payload.record)
end, timeout)
if not ev then
  print(rex.json.encode({ block = block, event = "timeout", timeout = timeout }))
  rex.stop(2)
end
if ev.name == "child_exited" then
  report("child_exited", nil, { exit_code = ev.payload and ev.payload.exit_code })
end
report("status", ev.payload.record)
