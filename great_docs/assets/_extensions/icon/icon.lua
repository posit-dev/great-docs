-- icon.lua — Quarto shortcode for inline Lucide icons
--
-- Usage in .qmd files:
--
--   {{< icon heart >}}
--   {{< icon name="heart" >}}
--   {{< icon heart size="24" >}}
--   {{< icon heart class="my-icon" >}}
--   {{< icon heart label="Favorite" >}}
--
-- Calls the companion _icon_shortcode.py script, which imports
-- get_icon_svg() from great_docs._icons and prints the resulting
-- SVG markup to stdout.

local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    local s = pandoc.utils.stringify(raw)
    return s or ""
end

return {
    ["icon"] = function(args, kwargs)
        -- Icon name can be a positional arg or a named kwarg
        local name = kwarg_str(kwargs, "name")
        if name == "" and #args > 0 then
            name = pandoc.utils.stringify(args[1])
        end

        if name == "" then
            return pandoc.RawInline(
                "html",
                "<!-- icon shortcode error: missing icon name -->"
            )
        end

        -- Locate the helper script (lives alongside this .lua file)
        local script_dir = debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
        local helper = script_dir .. "_icon_shortcode.py"

        -- Build CLI arguments for the helper script
        -- Use python3 for macOS compatibility (python may not exist)
        local cmd_args = { "python3", helper, name }

        -- Forward optional keyword arguments
        local forwarded = { "size", "class", "label" }
        for _, key in ipairs(forwarded) do
            local val = kwarg_str(kwargs, key)
            if val ~= "" then
                table.insert(cmd_args, "--" .. key)
                table.insert(cmd_args, val)
            end
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
            return pandoc.RawInline(
                "html",
                "<!-- icon shortcode error: failed to run helper script -->"
            )
        end

        local result = handle:read("*a")
        local success = handle:close()

        if not success or result == "" then
            local msg = result ~= "" and result or "unknown error"
            msg = msg:gsub("-->", "-- >")
            return pandoc.RawInline(
                "html",
                "<!-- icon shortcode error: " .. msg .. " -->"
            )
        end

        -- Icons are inline elements, not blocks
        return pandoc.RawInline("html", result)
    end
}
