-- agent-inbox.lua: list every block that needs a look, on this server and on each host.
--
--   rex do agent-inbox.lua
--
-- Prints a JSON list with one entry for each status record in state blocked,
-- done, or error: server, session, session label, block, block label, state,
-- kind, msg, app, and updated_at. A host that cannot be reached gives one entry
-- with its error.

local TERMINAL = "com.superlogical.terminal"
local SHOW = { blocked = true, done = true, error = true }
local inbox = {}

local function scan(server, api)
  local sessions, err = api.call("session.list", {})
  if not sessions then
    table.insert(inbox, { server = server, error = tostring(err) })
    return
  end
  for _, session in ipairs(sessions.sessions or {}) do
    local blocks = api.call("session.list_blocks", { session_id = session.session_id })
    for _, block in ipairs(blocks and blocks.blocks or {}) do
      if block.creator_name == TERMINAL then
        local status = api.block.call(TERMINAL, "program_status", {
          session_id = session.session_id,
          block_id = block.block_id,
        })
        for _, record in ipairs(status and status.records or {}) do
          if SHOW[record.state] then
            table.insert(inbox, {
              server = server,
              session = session.session_id,
              session_label = session.label,
              block = block.block_id,
              label = block.label,
              state = record.state,
              kind = record.kind,
              msg = record.msg,
              app = record.effective_app or record.app,
              updated_at = record.updated_at,
            })
          end
        end
      end
    end
  end
end

scan("local", rex)
for _, label in ipairs(rex.servers()) do
  local ok, api = pcall(rex.server, label)
  if ok then
    local scanned, err = pcall(scan, label, api)
    if not scanned then table.insert(inbox, { server = label, error = tostring(err) }) end
  else
    table.insert(inbox, { server = label, error = tostring(api) })
  end
end

-- rex.json.encode turns an empty table into {}, so print an empty list by hand.
print(#inbox == 0 and "[]" or rex.json.encode(inbox))
