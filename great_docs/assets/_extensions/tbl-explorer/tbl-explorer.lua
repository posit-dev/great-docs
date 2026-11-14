-- tbl-explorer.lua — Quarto shortcode for interactive table explorer
--
-- Usage in .qmd files:
--
--   {{< tbl-explorer file="data/example.csv" >}}
--   {{< tbl-explorer file="data.csv" page_size="25" sortable="true" >}}
--   {{< tbl-explorer file="data.csv" column_toggle="false" downloadable="false" >}}
--
-- Calls the companion _tbl_explorer_shortcode.py script, which imports
-- tbl_explorer() from great_docs._tables.explorer and prints the resulting
-- HTML to stdout.

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
    ["tbl-explorer"] = function(args, kwargs)
        -- File path can be a positional arg or named kwarg
        local file = kwarg_str(kwargs, "file")
        if file == "" and #args > 0 then
            file = pandoc.utils.stringify(args[1])
        end

        if file == "" then
            return pandoc.RawBlock(
                "html",
                "<!-- tbl-explorer shortcode error: missing file parameter -->"
            )
        end

        -- Locate the helper script (lives alongside this .lua file)
        local here = script_dir()
        local helper = here .. "_tbl_explorer_shortcode.py"

        -- Resolve relative file paths against the Quarto project root
        if file:sub(1, 1) ~= "/" then
            local project_root = here .. "../../"
            file = project_root .. file
        end

        -- Build CLI arguments
        local cmd_args = { "python3", helper, file }

        -- Forward optional keyword arguments
        local forwarded = {
            "columns", "page_size", "sortable", "filterable",
            "column_toggle", "copyable", "downloadable", "resizable",
            "sticky_header", "search_highlight",
            "show_row_numbers", "show_dtypes", "show_dimensions",
            "max_col_width", "min_tbl_width", "caption",
            "highlight_missing",
        }
        for _, key in ipairs(forwarded) do
            local val = kwarg_str(kwargs, key)
            if val ~= "" then
                table.insert(cmd_args, "--" .. key)
                table.insert(cmd_args, val)
            end
        end

        local success, result = run_helper(cmd_args)

        if not success or result == "" then
            return pandoc.RawBlock(
                "html",
                "<!-- tbl-explorer shortcode error: " ..
                (result or "unknown error"):gsub("[\r\n]+", " "):sub(1, 500) .. " -->"
            )
        end

        return pandoc.RawBlock("html", result)
    end
}
