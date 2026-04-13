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
        local script_dir = debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
        local helper = script_dir .. "_evolution_shortcode.py"

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
            -- Resolve relative paths: script_dir is <project>/_extensions/evolution/
            -- so project root is two levels up.
            if json_val:sub(1, 1) ~= "/" then
                local project_root = script_dir .. "../../"
                json_val = project_root .. json_val
            end
            table.insert(cmd_args, "--json_file")
            table.insert(cmd_args, json_val)
        end

        -- Build shell command (quote each argument)
        local parts = {}
        for _, arg in ipairs(cmd_args) do
            local escaped = arg:gsub("'", "'\\''")
            table.insert(parts, "'" .. escaped .. "'")
        end
        local cmd = table.concat(parts, " ") .. " 2>&1"

        local handle = io.popen(cmd)
        if not handle then
            return pandoc.RawBlock(
                "html",
                "<!-- evolution shortcode error: failed to run helper script -->"
            )
        end

        local result = handle:read("*a")
        local success = handle:close()

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
