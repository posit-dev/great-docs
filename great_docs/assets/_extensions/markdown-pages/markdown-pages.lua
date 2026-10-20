-- Write a Markdown companion of each rendered page during Quarto rendering.
--
-- Run at the `post-quarto` stage, after other filters such as `interlinks`
-- have resolved the page. Write `<stem>.md` next to `<stem>.html` and link
-- it from the page with `<link rel="alternate" type="text/markdown">`. Skip
-- the project's `404.html` and draft pages.
--
-- Return five filters that run in order:
--
-- 1. Snapshot the document, so Quarto writes the HTML from the original.
-- 2. Convert Quarto custom nodes to plain Pandoc blocks. Quarto exposes
--    custom nodes only to a filter's own top-level handlers; a walk over a
--    copy of the document sees bare divs.
-- 3. Join HTML tables that the Markdown reader split into one raw block per
--    tag. Keep this pass separate: Block handlers run before Blocks handlers
--    within a filter, and flattening reads each raw block alone.
-- 4. Flatten the document into elements GitHub-Flavored Markdown can hold.
-- 5. Write the companion and return the snapshot.

local PLACEHOLDER = "[Rich HTML output — view on the documentation site]"

-- Servers can send `.md` without a UTF-8 charset, so plain ASCII keeps
-- *View as Markdown* readable in the browser
local ASCII = {
    ["\u{2018}"] = "'",
    ["\u{2019}"] = "'",
    ["\u{201C}"] = '"',
    ["\u{201D}"] = '"',
    ["\u{2013}"] = "-",
    ["\u{2014}"] = "--",
}

local snapshot = nil

--- Return the page path relative to the project output directory.
---@param output_file string  Absolute path of the rendered page.
---@param output_dir string|nil  Absolute path of the project output directory.
---@return string|nil
local function page_path(output_file, output_dir)
    local path = output_file:gsub("\\", "/")
    if output_dir == nil then return nil end
    local root = output_dir:gsub("\\", "/"):gsub("/$", "") .. "/"
    if path:sub(1, #root) ~= root then return nil end
    return path:sub(#root + 1)
end

--- Join runs from a raw `<code>` tag to `</code>` into single code spans.
---
--- Rendered signatures mark up parts of a term with spans inside a raw
--- `<code>` element; the writer would otherwise split the term.
---@param inlines pandoc.Inlines
---@return pandoc.Inlines
local function collapse_code(inlines)
    local out = pandoc.Inlines({})
    local i = 1
    while i <= #inlines do
        local el = inlines[i]
        local code_end = nil
        if el.t == "RawInline" and el.format == "html" and el.text:match("^<code[%s>]") then
            for k = i + 1, #inlines do
                local inline = inlines[k]
                if inline.t == "RawInline" and inline.text == "</code>" then
                    code_end = k
                    break
                end
            end
        end
        if code_end == nil then
            out:insert(el)
            i = i + 1
        else
            local inner = pandoc.Inlines({})
            for k = i + 1, code_end - 1 do
                local inline = inlines[k]
                if inline.t == "RawInline"
                    and (inline.text == "&nbsp;" or inline.text:match("^<br")) then
                    inner:insert(pandoc.Space())
                else
                    inner:insert(inline)
                end
            end
            out:insert(pandoc.Code((pandoc.utils.stringify(inner):gsub("^%s+", ""))))
            i = code_end + 1
        end
    end
    return out
end

--- Reduce cells to at most one Plain block; GFM writes `[TABLE]` otherwise.
---@param tbl pandoc.Table
---@return pandoc.Table
local function plain_cells(tbl)
    ---@param list pandoc.BulletList|pandoc.OrderedList
    ---@return pandoc.Blocks
    local function list_blocks(list)
        local blocks = pandoc.Blocks({})
        for _, item in ipairs(list.content) do blocks:extend(item) end
        return blocks
    end
    ---@param cell pandoc.Cell
    ---@return pandoc.Cell
    local function flatten_cell(cell)
        local blocks = cell.contents:walk({
            HorizontalRule = function() return {} end,
            BulletList = list_blocks,
            OrderedList = list_blocks,
        })
        cell.contents = pandoc.Blocks({})
        if #blocks > 0 then
            cell.contents:insert(
                pandoc.Plain(pandoc.utils.blocks_to_inlines(blocks, { pandoc.Space() }))
            )
        end
        return cell
    end
    ---@param rows pandoc.List
    local function flatten_rows(rows)
        for _, row in ipairs(rows) do row.cells = row.cells:map(flatten_cell) end
    end
    flatten_rows(tbl.head.rows)
    for _, body in ipairs(tbl.bodies) do
        flatten_rows(body.head)
        flatten_rows(body.body)
    end
    flatten_rows(tbl.foot.rows)
    return tbl
end

--- Report whether a block is raw HTML.
---@param block pandoc.Block
---@return boolean
local function is_raw_html(block)
    return block.t == "RawBlock" and block.format == "html"
end

--- Rejoin HTML tables that the Markdown reader split apart.
---
--- An HTML table written in a page reaches the document as one raw block
--- per tag, with the cell text parsed as Markdown between them. Pandoc can
--- read the table back only as a whole.
---@param blocks pandoc.Blocks
---@return pandoc.Blocks
local function join_html_tables(blocks)
    local out = pandoc.Blocks({})
    local i = 1
    while i <= #blocks do
        local block = blocks[i]
        local table_end = nil
        if is_raw_html(block) and block.text:match("^%s*<table[%s>]")
            and not block.text:match("</table>%s*$") then
            for k = i + 1, #blocks do
                if is_raw_html(blocks[k]) and blocks[k].text:match("</table>%s*$") then
                    table_end = k
                    break
                end
            end
        end
        if table_end == nil then
            out:insert(block)
            i = i + 1
        else
            local parts = {}
            for k = i, table_end do
                local part = blocks[k]
                if is_raw_html(part) then
                    parts[#parts + 1] = part.text
                else
                    parts[#parts + 1] = pandoc.write(pandoc.Pandoc({ part }), "html")
                end
            end
            out:insert(pandoc.RawBlock("html", table.concat(parts, "\n")))
            i = table_end + 1
        end
    end
    return out
end

--- Report whether a link target names a file inside the site.
---@param target string
---@return boolean
local function is_relative(target)
    return not (target:match("^%a[%w+.-]*:") or target:match("^/") or target:match("^#"))
end

local flatten = {}

flatten.Inlines = collapse_code

flatten.Span = function(span) return span.content end

flatten.Div = function(div)
    -- Drop Quarto's hidden navigation copies, and the homepage sidebar of
    -- site links, which would otherwise lead the homepage companion
    if div.identifier == "quarto-navigation-envelope"
        or div.identifier == "quarto-meta-markdown"
        or div.classes:includes("hidden")
        or div.classes:includes("gd-homepage-sidebar") then
        return {}
    end
    -- Rich output such as widgets has no Markdown form
    if div.classes:includes("cell-output-display") and #div.content == 0 then
        return pandoc.Para({ pandoc.Emph({ pandoc.Str(PLACEHOLDER) }) })
    end
    return div.content
end

flatten.RawBlock = function(raw)
    if raw.format ~= "html" then return {} end
    local ok, doc = pcall(pandoc.read, raw.text, "html")
    if not ok then return {} end
    return doc.blocks:walk(flatten)
end

flatten.Table = plain_cells

flatten.Link = function(link)
    if is_relative(link.target) then
        link.target = link.target:gsub("%.qmd$", ".md"):gsub("%.qmd#", ".md#")
            :gsub("%.html$", ".md"):gsub("%.html#", ".md#")
    end
    link.attr = pandoc.Attr()
    return link
end

flatten.Header = function(header)
    header.attr = pandoc.Attr()
    return header
end

local convert = {
    Callout = function(callout)
        local kind = (callout.type or "note"):gsub("^%l", string.upper)
        local head = pandoc.Inlines({ pandoc.Str(kind) })
        if callout.title and pandoc.utils.stringify(callout.title) ~= "" then
            head:insert(pandoc.Str(":"))
            head:insert(pandoc.Space())
            head:extend(quarto.utils.as_inlines(callout.title))
        end
        local blocks = pandoc.Blocks({ pandoc.Para({ pandoc.Strong(head) }) })
        if callout.content then blocks:extend(quarto.utils.as_blocks(callout.content)) end
        return pandoc.BlockQuote(blocks)
    end,

    Tabset = function(tabset)
        local blocks = pandoc.Blocks({})
        for _, tab in ipairs(tabset.tabs) do
            blocks:insert(pandoc.Para({ pandoc.Strong(quarto.utils.as_inlines(tab.title)) }))
            blocks:extend(quarto.utils.as_blocks(tab.content))
        end
        return blocks
    end,
}

--- Write the companion of the page being rendered.
---@param doc pandoc.Pandoc  The flattened document.
---@return string|nil  Path of the companion, or `nil` when the page has none.
local function write_companion(doc)
    local out = quarto.doc.output_file
    if out == nil or doc.meta.draft == true then return nil end
    local path = page_path(out, quarto.project.output_directory)
    if path == "404.html" then return nil end

    local blocks = pandoc.Blocks({})
    if doc.meta.title and pandoc.utils.stringify(doc.meta.title) ~= "" then
        local title = pandoc.Header(1, quarto.utils.as_inlines(doc.meta.title))
        blocks:insert(title:walk(flatten))
    end
    blocks:extend(doc.blocks)
    local md = pandoc.write(pandoc.Pandoc(blocks), "gfm-raw_html", { wrap_text = "none" })
    for from, to in pairs(ASCII) do md = md:gsub(from, to) end

    -- A full render cleans the output directory, and Quarto creates each
    -- subdirectory only when it moves the first finished page into it
    pandoc.system.make_directory(pandoc.path.directory(out), true)
    local companion = out:gsub("%.html$", ".md")
    local file = io.open(companion, "w")
    if file == nil then return nil end
    file:write(md)
    file:close()
    return companion
end

local write = {
    Pandoc = function(doc)
        local companion = write_companion(doc)
        if companion then
            local name = pandoc.path.filename(companion)
            quarto.doc.include_text(
                "in-header",
                '<link rel="alternate" type="text/markdown" href="' .. name .. '">'
            )
        end
        return snapshot
    end,
}

return {
    { Pandoc = function(doc) snapshot = doc:clone() end },
    convert,
    { Blocks = join_html_tables },
    flatten,
    write,
}
