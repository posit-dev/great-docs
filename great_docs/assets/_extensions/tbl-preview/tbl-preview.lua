-- tbl-preview.lua — Quarto shortcode for data table previews
--
-- Usage in .qmd files:
--
--   {{< tbl-preview file="data/example.csv" >}}
--   {{< tbl-preview file="data.tsv" >}}
--   {{< tbl-preview file="data.jsonl" show_all="true" >}}
--   {{< tbl-preview file="data.parquet" n_head="10" n_tail="5" >}}
--   {{< tbl-preview file="data.csv" show_all="true" caption="My Dataset" >}}
--
-- Calls the companion _tbl_preview_shortcode.py script, which imports
-- tbl_preview() from great_docs._tbl_preview and prints the resulting
-- HTML to stdout.

local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    local s = pandoc.utils.stringify(raw)
    return s or ""
end

return {
    ["tbl-preview"] = function(args, kwargs)
        -- File path can be a positional arg or named kwarg
        local file = kwarg_str(kwargs, "file")
        if file == "" and #args > 0 then
            file = pandoc.utils.stringify(args[1])
        end

        if file == "" then
            return pandoc.RawBlock(
                "html",
                "<!-- tbl-preview shortcode error: missing file parameter -->"
            )
        end

        -- Locate the helper script (lives alongside this .lua file)
        local script_dir = debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
        local helper = script_dir .. "_tbl_preview_shortcode.py"

        -- Resolve relative file paths against the Quarto project root
        -- (script_dir is <project>/_extensions/tbl-preview/)
        if file:sub(1, 1) ~= "/" then
            local project_root = script_dir .. "../../"
            file = project_root .. file
        end

        -- Build CLI arguments
        -- Use python3 for macOS compatibility (python may not exist)
        local cmd_args = { "python3", helper, file }

        -- Forward optional keyword arguments
        local forwarded = {
            "columns", "n_head", "n_tail", "show_all",
            "show_row_numbers", "show_dtypes", "show_dimensions",
            "max_col_width", "min_tbl_width", "caption",
            "row_index_offset",
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
                "<!-- tbl-preview shortcode error: failed to run helper script -->"
            )
        end

        local result = handle:read("*a")
        local success = handle:close()

        if not success or result == "" then
            local msg = result ~= "" and result or "unknown error"
            msg = msg:gsub("-->", "-- >")
            return pandoc.RawBlock(
                "html",
                "<!-- tbl-preview shortcode error: " .. msg .. " -->"
            )
        end

        return pandoc.RawBlock("html", result)
    end
}
