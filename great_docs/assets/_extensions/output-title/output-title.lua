-- output-title.lua — Quarto filter for labelling and framing code cell outputs
--
-- Usage in .qmd files:
--
--   ```{python}
--   #| output-title: "Response"
--   chat.chat("Hello!")
--   ```
--
--   ```{python}
--   #| output-frame: true
--   print("framed output, no title")
--   ```
--
-- Wraps the cell's output in a styled container with an optional title.
-- Works with any executable code cell, and composes with source-code: mock.

--- Extract the output-title value from a cell Div's attributes.
--- Quarto passes unrecognised hash-pipe options as attributes on the
--- enclosing div.cell element.
---@param div pandoc.Div
---@return string|nil  The title text (unquoted), or nil if absent.
local function get_output_title(div)
    -- Quarto passes custom cell options as attributes on the div
    local title = div.attributes["output-title"]
    if title == nil then return nil end

    -- Strip surrounding quotes if present
    title = title:match('^"(.*)"$') or title:match("^'(.*)'$") or title
    if title == "" then return nil end
    return title
end

--- Check whether output-frame is set to a truthy value.
---@param div pandoc.Div
---@return boolean
local function get_output_frame(div)
    local val = div.attributes["output-frame"]
    if val == nil then return false end
    val = val:lower()
    return val == "true" or val == "yes" or val == "1"
end

--- Check whether a block element is a cell-output container.
---@param el pandoc.Block
---@return boolean
local function is_cell_output(el)
    if el.t ~= "Div" then return false end
    for _, cls in ipairs(el.classes) do
        if cls:match("^cell%-output") then return true end
    end
    return false
end

function Div(div)
    -- Only operate on executable code cells
    if not div.classes:includes("cell") then return nil end

    local title = get_output_title(div)
    local frame = get_output_frame(div)

    -- Need either a title or an explicit frame request
    if title == nil and not frame then return nil end

    -- Remove attributes so they don't leak into the HTML
    div.attributes["output-title"] = nil
    div.attributes["output-frame"] = nil

    -- Collect output blocks and wrap them
    local new_content = pandoc.List()
    local output_blocks = pandoc.List()

    for _, el in ipairs(div.content) do
        if is_cell_output(el) then
            output_blocks:insert(el)
        else
            new_content:insert(el)
        end
    end

    if #output_blocks == 0 then return nil end

    -- Build the container HTML
    local title_html = '<div class="gd-output-title-container">\n'
    if title then
        title_html = title_html
            .. '<div class="gd-output-title-header">' .. title .. '</div>\n'
    end
    title_html = title_html .. '<div class="gd-output-title-body">\n'
    local close_html = '</div>\n</div>'

    -- Wrap: open tag, output blocks, close tag
    new_content:insert(pandoc.RawBlock("html", title_html))
    for _, ob in ipairs(output_blocks) do
        new_content:insert(ob)
    end
    new_content:insert(pandoc.RawBlock("html", close_html))

    div.content = new_content
    return div
end
