-- color-swatch.lua — Quarto shortcode for color palette display
--
-- Usage in .qmd files:
--
--   {{< color-swatch >}}
--   - name: Sky Blue
--     hex: "#38bdf8"
--   {{< /color-swatch >}}
--
--   {{< color-swatch palette="sky" >}}
--   {{< color-swatch palette="sky" mode="rectangles" >}}
--
-- Calls the companion _color_swatch_shortcode.py script, which computes
-- contrast ratios, builds tooltip data, and returns complete HTML.

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
local function find_script_dir()
    if debug then
        return debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
    end
    return (quarto.utils.resolve_path("x"):gsub("x$", ""))
end

return {
    ["color-swatch"] = function(args, kwargs, blocks)
        -- Locate the helper script (lives alongside this .lua file)
        local script_dir = find_script_dir()
        local helper = script_dir .. "_color_swatch_shortcode.py"

        -- Build CLI arguments
        local cmd_args = { "python3", helper }

        -- Forward all keyword arguments as CLI flags
        local forwarded = {
            { key = "palette",       flag = "--palette" },
            { key = "mode",          flag = "--mode" },
            { key = "cols",          flag = "--cols" },
            { key = "size",          flag = "--size" },
            { key = "show-contrast", flag = "--show-contrast" },
            { key = "show-names",    flag = "--show-names" },
            { key = "show-hex",      flag = "--show-hex" },
            { key = "copy-format",   flag = "--copy-format" },
            { key = "title",         flag = "--title" },
            { key = "description",   flag = "--description" },
            { key = "file",          flag = "--file" },
            { key = "height",        flag = "--height" },
            { key = "show-css",      flag = "--show-css" },
            { key = "show-details",  flag = "--show-details" },
            { key = "show-controls", flag = "--show-controls" },
            { key = "id",            flag = "--id" },
            { key = "class",         flag = "--class" },
            { key = "border",        flag = "--border" },
        }

        for _, spec in ipairs(forwarded) do
            local val = kwarg_str(kwargs, spec.key)
            if val ~= "" then
                table.insert(cmd_args, spec.flag)
                table.insert(cmd_args, val)
            end
        end

        -- Resolve --file relative to the Quarto project root
        local file_val = kwarg_str(kwargs, "file")
        if file_val ~= "" and file_val:sub(1, 1) ~= "/" then
            local project_root = script_dir .. "../../"
            -- Replace the already-inserted value
            for i, arg in ipairs(cmd_args) do
                if arg == "--file" and cmd_args[i + 1] == file_val then
                    cmd_args[i + 1] = project_root .. file_val
                    break
                end
            end
        end

        -- Note: Quarto shortcodes do not support paired (body) content.
        -- The third parameter is `meta` (document metadata), not `blocks`.
        -- Custom colors are supplied via the `file` parameter instead.
        local body = ""

        -- Build shell command: pipe body via echo into the helper
        local parts = {}
        for _, arg in ipairs(cmd_args) do
            local escaped = arg:gsub("'", "'\\''")
            table.insert(parts, "'" .. escaped .. "'")
        end
        local cmd_str = table.concat(parts, " ")

        local cmd
        if body ~= "" then
            -- Pipe the YAML body via a here-document to avoid shell escaping issues
            local body_escaped = body:gsub("'", "'\\''")
            cmd = "printf '%s' '" .. body_escaped .. "' | " .. cmd_str .. " 2>&1"
        else
            cmd = cmd_str .. " 2>&1"
        end

        local handle = io.popen(cmd)
        if not handle then
            return pandoc.RawBlock(
                "html",
                "<!-- color-swatch error: failed to run helper script -->"
            )
        end

        local result = handle:read("*a")
        local success = handle:close()

        if not success or result == "" then
            local msg = result ~= "" and result or "unknown error"
            msg = msg:gsub("-->", "-- >")
            return pandoc.RawBlock(
                "html",
                "<!-- color-swatch error: " .. msg .. " -->"
            )
        end

        return pandoc.RawBlock("html", result)
    end
}
