-- marimo.lua — Quarto shortcode for embedding Marimo notebooks as WASM islands.
--
-- Usage in .qmd files:
--
--   {{< marimo file="notebooks/gt-basics.py" >}}
--
--   {{< marimo file="notebooks/gt-basics.py" show-code="false" >}}
--
--   {{< marimo file="notebooks/gt-basics.py" mode="iframe" height="600px" >}}
--
-- Options:
--   file        (required) Path to .py marimo notebook relative to project root
--   mode        "island" (default), "iframe"
--   show-copy   "true"/"false" — show Copy Notebook button (default: true)
--   theme       "auto"/"light"/"dark" — color theme (default: auto)
--   height      CSS height for iframe mode (default: 600px)
--
-- Island mode uses pre-generated HTML from MarimoIslandGenerator (built
-- during the Great Docs build step). The HTML is read from
-- _marimo_islands/<notebook-stem>.html.

local function escape_html(s)
    if s == nil then return "" end
    return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

local function kwarg(kwargs, key, default)
    local raw = kwargs[key]
    if raw == nil then return default end
    local s = pandoc.utils.stringify(raw)
    if s == "" then return default end
    return s
end

--- Read a file relative to the Quarto project root.
local function read_project_file(rel_path)
    local base = ""
    if quarto and quarto.project and quarto.project.directory then
        base = quarto.project.directory .. "/"
    end
    local path = base .. rel_path
    local f = io.open(path, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    return content
end

return {
    ["marimo"] = function(args, kwargs, meta)
        -- Get file path (required)
        local file = kwarg(kwargs, "file", "")
        if file == "" and #args > 0 then
            file = pandoc.utils.stringify(args[1])
        end
        if file == "" then
            quarto.log.warning("[marimo] 'file' attribute is required")
            return pandoc.Null()
        end

        -- Read options
        local mode = kwarg(kwargs, "mode", "island")
        local show_copy = kwarg(kwargs, "show-copy", "true")
        local theme = kwarg(kwargs, "theme", "auto")
        local height = kwarg(kwargs, "height", "600px")

        -- IFRAME MODE --------------------------------------------------------
        if mode == "iframe" then
            local offset = ""
            if quarto and quarto.project and quarto.project.offset then
                offset = quarto.project.offset .. "/"
            end
            local wasm_path = file:gsub("%.py$", "") .. "/index.html"
            local parts = {}
            table.insert(parts, '<div class="gd-marimo-iframe-wrap">')
            table.insert(parts, '<iframe class="gd-marimo-iframe" ')
            table.insert(parts, 'src="' .. escape_html(offset .. wasm_path) .. '" ')
            table.insert(parts, 'width="100%" height="' .. escape_html(height) .. '" ')
            table.insert(parts, 'sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms" ')
            table.insert(parts, 'allow="microphone" allowfullscreen loading="lazy">')
            table.insert(parts, '</iframe>')
            table.insert(parts, '</div>')
            return pandoc.RawInline("html", table.concat(parts))
        end

        -- ISLAND MODE --------------------------------------------------------
        local show_code = kwarg(kwargs, "show-code", "true")

        -- Read pre-generated island HTML from _marimo_islands/<stem>.html
        local stem = file:match("([^/]+)%.py$")
        if not stem then
            quarto.log.warning("[marimo] Cannot determine notebook stem from: " .. file)
            return pandoc.RawInline("html",
                '<div class="gd-marimo-error">Invalid notebook path: '
                .. escape_html(file) .. '</div>')
        end

        -- Use -nocode variant when show-code is false
        local island_file = "_marimo_islands/" .. stem .. ".html"
        if show_code == "false" then
            island_file = "_marimo_islands/" .. stem .. "-nocode.html"
        end
        local island_html = read_project_file(island_file)
        if not island_html then
            quarto.log.warning("[marimo] Pre-generated island HTML not found for: " .. stem)
            return pandoc.RawInline("html",
                '<div class="gd-marimo-error">Island HTML not generated for: '
                .. escape_html(file) .. '</div>')
        end

        local parts = {}
        local wrapper_classes = "gd-marimo-island-group"
        if show_code == "false" then
            wrapper_classes = wrapper_classes .. " gd-marimo-nocode"
        end
        table.insert(parts, '<div class="' .. wrapper_classes .. '" data-theme="' .. escape_html(theme) .. '">')
        table.insert(parts, island_html)

        -- Copy notebook button
        if show_copy == "true" then
            local source = read_project_file(file)
            if source then
                local escaped_source = escape_html(source)
                table.insert(parts,
                    '\n  <script type="text/plain" class="gd-marimo-source" data-filename="' ..
                    escape_html(file:match("[^/]+$") or file) .. '">')
                table.insert(parts, escaped_source)
                table.insert(parts, '</script>')
                table.insert(parts, '\n  <div class="gd-marimo-copy">')
                table.insert(parts, '<button class="gd-marimo-copy-btn" title="Copy notebook source">')
                table.insert(parts,
                    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>')
                table.insert(parts, ' Copy Notebook</button>')
                table.insert(parts,
                    '<span class="gd-marimo-copy-hint">Run locally: <code>marimo edit ' ..
                    escape_html(file:match("[^/]+$") or file) .. '</code></span>')
                table.insert(parts, '</div>')
            end
        end

        table.insert(parts, '\n</div>')

        return pandoc.RawInline("html", table.concat(parts))
    end
}
