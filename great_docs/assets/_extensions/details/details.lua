-- details.lua — Quarto filter for enhanced collapsible sections
--
-- Usage in .qmd files (fenced div syntax):
--
--   ::: {.details summary="Click to expand"}
--   Content here with **markdown** support.
--   :::
--
--   ::: {.details summary="Advanced Options" .open icon="settings"}
--   This section starts expanded.
--   :::
--
--   ::: {.details summary="Section A" group="faq" type="note"}
--   Only one section in a group can be open at a time (accordion).
--   :::
--
-- Renders as <details class="gd-details"> with smooth animations,
-- optional Lucide icons, callout-type styling, and accordion groups.
--
-- All styling is handled via CSS classes in great-docs.scss.
-- Accordion behavior and smooth animation are handled by details.js.

--- Escape HTML special characters in a string.
local function escape_html(s)
    return s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
end

--- Render inline backtick code in summary text as <code> elements.
--- First escapes HTML, then converts `...` to <code>...</code>.
local function render_summary(s)
    local escaped = escape_html(s)
    return escaped:gsub("`([^`]+)`", "<code>%1</code>")
end

--- Read a named attribute from a Pandoc Div, returning "" if absent.
local function attr_str(div, key)
    local val = div.attributes[key]
    if val == nil then return "" end
    return val
end

-- Valid callout-like types for styled details
local TYPES = {
    note = true,
    warning = true,
    tip = true,
    danger = true,
    gradient = true,
}

-- Valid named gradient presets
local GRADIENT_PRESETS = {
    sky = true,
    peach = true,
    prism = true,
    lilac = true,
    slate = true,
    honey = true,
    dusk = true,
    mint = true,
}

-- Map types to default Lucide icon names
local TYPE_ICONS = {
    note    = "message-circle",
    warning = "zap",
    tip     = "lightbulb",
    danger  = "ban",
}

--- Render a Lucide icon SVG by calling the icon helper script.
--- Returns the SVG HTML string, or empty string on failure.
local function render_icon(icon_name)
    if icon_name == "" then return "" end

    -- Locate the icon helper script in the sibling extension directory
    local script_dir = debug.getinfo(1, "S").source:match("@?(.*/)") or "./"
    local helper = script_dir .. "../icon/_icon_shortcode.py"

    local cmd = "python3 '" ..
        helper .. "' '" .. icon_name:gsub("'", "'\\''") ..
        "' --size 16 --class gd-details-icon 2>/dev/null"
    local handle = io.popen(cmd)
    if not handle then return "" end

    local result = handle:read("*a")
    local success = handle:close()

    if not success or result == "" then return "" end
    return result
end

function Div(div)
    -- Only process divs with the "details" class
    if not div.classes:includes("details") then
        return nil
    end

    -- Read attributes
    local summary = attr_str(div, "summary")
    if summary == "" then summary = "Details" end
    local icon     = attr_str(div, "icon")
    local dtype    = attr_str(div, "type")
    local group    = attr_str(div, "group")
    local gradient = attr_str(div, "gradient")
    local open_val = div.classes:includes("open")
    local gleam    = div.classes:includes("gleam")

    -- Build CSS classes for the <details> element
    local classes  = { "gd-details" }
    if dtype ~= "" and TYPES[dtype] then
        table.insert(classes, "gd-details--" .. dtype)
    end

    -- Named gradient preset (gradient="sky" etc.) overrides type="gradient"
    if gradient ~= "" and GRADIENT_PRESETS[gradient] then
        table.insert(classes, "gd-details--gradient-" .. gradient)
    end

    -- Gleam border effect
    if gleam then
        table.insert(classes, "gd-details--gleam")
    end

    -- If a type is set but no icon was specified, use the default icon
    if icon == "" and dtype ~= "" and TYPE_ICONS[dtype] then
        icon = TYPE_ICONS[dtype]
    end

    -- Build data attributes
    local data_attrs = {}
    if group ~= "" then
        table.insert(data_attrs, 'data-gd-group="' .. escape_html(group) .. '"')
    end

    -- Build the open attribute
    local open_attr = open_val and " open" or ""

    -- Render icon SVG
    local icon_html = ""
    if icon ~= "" then
        icon_html = render_icon(icon)
        if icon_html ~= "" then
            icon_html = '<span class="gd-details-icon-wrap">' ..
                icon_html .. '</span>'
        end
    end

    -- Build the HTML wrapper
    local class_attr = table.concat(classes, " ")
    local extra_attrs = ""
    if #data_attrs > 0 then
        extra_attrs = " " .. table.concat(data_attrs, " ")
    end

    local html_open = '<details class="' .. class_attr .. '"'
        .. open_attr .. extra_attrs .. '>\n'
        .. '<summary class="gd-details-summary">'
        .. '<span class="gd-details-chevron" aria-hidden="true"></span>'
        .. icon_html
        .. '<span class="gd-details-title">'
        .. render_summary(summary) .. '</span>'
        .. '</summary>\n'
        .. '<div class="gd-details-body">'
    local html_close = '</div>\n</details>'

    -- Return opening HTML + inner blocks + closing HTML
    local output = pandoc.List:new()
    output:insert(pandoc.RawBlock("html", html_open))
    for _, block in ipairs(div.content) do
        output:insert(block)
    end
    output:insert(pandoc.RawBlock("html", html_close))
    return output
end
