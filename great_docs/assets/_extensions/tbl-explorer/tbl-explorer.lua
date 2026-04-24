-- tbl-explorer.lua — Quarto shortcode for interactive table explorer
--
-- Usage in .qmd files:
--
--   {{< tbl-explorer file="data/example.csv" >}}
--   {{< tbl-explorer file="data.csv" page_size="25" sortable="true" >}}
--   {{< tbl-explorer file="data.csv" column_toggle="false" downloadable="false" >}}
--
-- Calls the companion _tbl_explorer_shortcode.py script, which imports
-- tbl_explorer() from great_docs._tbl_explorer and prints the resulting
-- HTML to stdout.

local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    local s = pandoc.utils.stringify(raw)
    return s or ""
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
        local script_dir = debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
        local helper = script_dir .. "_tbl_explorer_shortcode.py"

        -- Resolve relative file paths against the Quarto project root
        if file:sub(1, 1) ~= "/" then
            local project_root = script_dir .. "../../"
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
                "<!-- tbl-explorer shortcode error: failed to run helper script -->"
            )
        end

        local result = handle:read("*a")
        local success = handle:close()

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
