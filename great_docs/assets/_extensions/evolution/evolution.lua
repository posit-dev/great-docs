-- evolution.lua — Quarto shortcode for API evolution tables
--
-- Usage in .qmd files:
--
--   {{< evolution build >}}
--   {{< evolution symbol="build" changes_only="false" >}}
--   {{< evolution build old_version="v1.0" new_version="v2.0" >}}
--   {{< evolution build json="path/to/data.json" >}}
--
-- Calls the companion _evolution_shortcode.py script, which imports
-- render_evolution_table() and prints the resulting HTML to stdout.

-- Helper: stringify a kwarg value; returns "" if the key is absent or empty.
-- In Quarto >=1.8 kwargs[key] can return a truthy-but-empty object for
-- keys not supplied by the user, so a simple truthiness check is unreliable.
local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    local s = pandoc.utils.stringify(raw)
    return s or ""
end

--- Return the directory holding this script, ending in a slash.
---
--- Quarto 2 omits Lua's `debug` library, so resolve a path against the
--- extension's directory instead.
local function script_dir()
    if debug then
        return debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
    end
    return (quarto.utils.resolve_path("x"):gsub("x$", ""))
end

--- Run a helper command without a shell.
---
--- Use `pandoc.system.command` where Pandoc has it: under Quarto 2, `io.popen`
--- can deadlock when shortcodes run on parallel threads.
---@param cmd_args string[]  The command and its arguments.
---@return boolean  Whether the command exited successfully.
---@return string  Its standard output followed by its standard error.
local function run_helper(cmd_args)
    if pandoc.system.command then
        local ok, status, out, err = pcall(
            pandoc.system.command, cmd_args[1], { table.unpack(cmd_args, 2) }, ""
        )
        if not ok then return false, tostring(status) end
        return status == false, (out or "") .. (err or "")
    end
    local parts = {}
    for _, arg in ipairs(cmd_args) do
        local escaped = arg:gsub("'", "'\\''")
        table.insert(parts, "'" .. escaped .. "'")
    end
    local handle = io.popen(table.concat(parts, " ") .. " 2>&1")
    if not handle then return false, "" end
    local result = handle:read("*a")
    return handle:close() == true, result
end

return {
    ["evolution"] = function(args, kwargs)
        -- Symbol can be a positional arg or a named kwarg
        local symbol = kwarg_str(kwargs, "symbol")
        if symbol == "" and #args > 0 then
            symbol = pandoc.utils.stringify(args[1])
        end

        if symbol == "" then
            return pandoc.RawBlock(
                "html",
                "<!-- evolution shortcode error: missing symbol -->"
            )
        end

        -- Locate the helper script (lives alongside this .lua file)
        local here = script_dir()
        local helper = here .. "_evolution_shortcode.py"

        -- Build CLI arguments for the helper script
        local cmd_args = { "python", helper, symbol }

        -- Forward optional keyword arguments
        local forwarded = {
            "package", "old_version", "new_version",
            "changes_only", "disclosure", "summary", "css"
        }
        for _, key in ipairs(forwarded) do
            local val = kwarg_str(kwargs, key)
            if val ~= "" then
                table.insert(cmd_args, "--" .. key)
                table.insert(cmd_args, val)
            end
        end

        -- Forward json as --json_file, resolving relative paths against
        -- the Quarto project root (the directory containing _extensions/).
        local json_val = kwarg_str(kwargs, "json")
        if json_val ~= "" then
            -- Resolve relative paths: `here` is <project>/_extensions/evolution/
            -- so project root is two levels up.
            if json_val:sub(1, 1) ~= "/" then
                local project_root = here .. "../../"
                json_val = project_root .. json_val
            end
            table.insert(cmd_args, "--json_file")
            table.insert(cmd_args, json_val)
        end

        local success, result = run_helper(cmd_args)

        if not success or result == "" then
            local msg = result ~= "" and result or "unknown error"
            -- Sanitise to prevent breaking the HTML comment
            msg = msg:gsub("-->", "-- >")
            return pandoc.RawBlock(
                "html",
                "<!-- evolution shortcode error: " .. msg .. " -->"
            )
        end

        return pandoc.RawBlock("html", result)
    end
}
