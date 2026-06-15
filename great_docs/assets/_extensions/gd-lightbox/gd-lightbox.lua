-- gd-lightbox.lua — Quarto filter for Great Docs lightbox image enhancement
--
-- Transforms images with the `.lightbox` class (or all block images when
-- lightbox mode is "auto") into interactive lightbox-enabled images with
-- support for:
--   - Click-to-zoom with origin-aware animation
--   - Dark-mode image variants (auto-detected or explicit)
--   - Gallery grouping with filmstrip navigation
--   - Before/after comparison slider (via shortcode)
--   - Image annotations
--   - Copy/download toolbar
--
-- The filter injects data attributes that the companion gd-lightbox.js reads
-- at runtime. It also ensures the JS and CSS assets are included once.
--
-- Works as a drop-in replacement for Quarto's built-in GLightbox integration.
-- Supports the same syntax: {.lightbox}, {.nolightbox}, group="...", and
-- the document-level `lightbox: true/auto/false` YAML key.

local assets_injected = false
local lightbox_mode = nil -- nil = not yet read, "auto", "true", "false", "explicit"
local image_counter = 0

--- Read the document-level lightbox mode from Meta.
local function read_meta(meta)
    if meta["lightbox"] then
        local val = pandoc.utils.stringify(meta["lightbox"])
        if val == "true" or val == "auto" then
            lightbox_mode = "auto"
        elseif val == "false" then
            lightbox_mode = "false"
        else
            -- Could be a table with options; treat as auto
            lightbox_mode = "auto"
        end
    else
        -- Default: explicit only (require .lightbox class)
        lightbox_mode = "explicit"
    end
end

--- Check if an element has a specific class.
local function has_class(el, cls)
    if el.classes then
        for _, c in ipairs(el.classes) do
            if c == cls then return true end
        end
    end
    return false
end

--- Determine if an image should get lightbox treatment.
--- @param img pandoc.Image
--- @return boolean
local function should_lightbox(img)
    -- Explicit opt-out always wins
    if has_class(img, "nolightbox") then
        return false
    end
    -- Explicit opt-in always works
    if has_class(img, "lightbox") then
        return true
    end
    -- In auto mode, all block-level images get treatment
    if lightbox_mode == "auto" then
        return true
    end
    return false
end

--- Resolve a dark-mode variant only when the author has opted in.
--- Opt-in happens via an explicit dark="..." attribute, or by naming the
--- source with a ".light" segment (e.g. "diagram.light.svg"), in which case
--- the dark sibling is "diagram.dark.svg".
---
--- We deliberately do NOT guess a ".dark" sibling for arbitrary sources:
--- the Lua filter cannot verify the file exists at render time, so a blind
--- guess produces a broken image (404) in the lightbox whenever no dark
--- variant was ever provided.
--- @param src string
--- @param attrs table
--- @return string|nil  dark variant path, or nil
local function get_dark_variant(src, attrs)
    -- Explicit attribute takes priority
    if attrs["dark"] then
        return attrs["dark"]
    end
    -- Naming convention opt-in: file.light.ext → file.dark.ext
    local stem, ext = src:match("^(.+)%.([^%.]+)$")
    if not stem then return nil end

    local base = stem:match("^(.+)%.light$")
    if base then
        return base .. ".dark." .. ext
    end

    -- No explicit dark variant and no ".light" opt-in: leave it unset so the
    -- lightbox keeps using the (working) light source in dark mode.
    return nil
end

--- Build the HTML wrapper for a lightbox-enabled image.
--- @param img pandoc.Image
--- @return pandoc.RawBlock
local function render_lightbox_image(img)
    image_counter = image_counter + 1
    local src = img.src
    local alt = pandoc.utils.stringify(img.caption) or ""
    local attrs = img.attributes or {}
    local classes = img.classes or {}

    -- Collect lightbox data attributes
    local data_attrs = {}
    data_attrs["data-gd-lightbox"] = "true"
    data_attrs["data-gd-lightbox-id"] = "gd-lb-" .. tostring(image_counter)

    -- Group (gallery) attribute
    local group = attrs["group"]
    if group then
        data_attrs["data-gd-lightbox-group"] = group
    end

    -- Dark variant
    local dark = get_dark_variant(src, attrs)
    if dark then
        data_attrs["data-gd-lightbox-dark"] = dark
    end

    -- Caption (can be markdown — passed as plain text for now)
    local caption = attrs["caption"] or alt
    if caption and caption ~= "" then
        data_attrs["data-gd-lightbox-caption"] = caption
    end

    -- Credit / attribution
    if attrs["credit"] then
        data_attrs["data-gd-lightbox-credit"] = attrs["credit"]
    end

    -- Description position
    if attrs["desc-position"] then
        data_attrs["data-gd-lightbox-desc-position"] = attrs["desc-position"]
    end

    -- Zoom target
    if attrs["zoom-target"] then
        data_attrs["data-gd-lightbox-zoom-target"] = attrs["zoom-target"]
    end

    -- Annotations (JSON or file path)
    if attrs["annotations"] then
        data_attrs["data-gd-lightbox-annotations"] = attrs["annotations"]
    end

    -- Gallery loop control (default: true; set loop="false" to stop at ends)
    if attrs["loop"] then
        data_attrs["data-gd-lightbox-loop"] = attrs["loop"]
    end

    -- Gallery autoplay interval (e.g., "3s", "2000ms")
    if attrs["autoplay"] then
        data_attrs["data-gd-lightbox-autoplay"] = attrs["autoplay"]
    end

    -- Explicit full-resolution source for lightbox view
    if attrs["full-src"] then
        data_attrs["data-gd-lightbox-full-src"] = attrs["full-src"]
    end

    -- Build HTML attributes string
    local attr_parts = {}
    for k, v in pairs(data_attrs) do
        table.insert(attr_parts, k .. '="' .. v:gsub('"', '&quot;') .. '"')
    end

    -- Collect CSS classes for the wrapper
    local wrapper_classes = { "gd-lightbox-wrapper" }
    for _, c in ipairs(classes) do
        if c ~= "lightbox" and c ~= "nolightbox" then
            table.insert(wrapper_classes, c)
        end
    end

    -- Build image tag attributes (preserve width/height if set)
    local img_attrs = {}
    if attrs["width"] then
        table.insert(img_attrs, 'width="' .. attrs["width"] .. '"')
    end
    if attrs["height"] then
        table.insert(img_attrs, 'height="' .. attrs["height"] .. '"')
    end
    if attrs["srcset"] then
        table.insert(img_attrs, 'srcset="' .. attrs["srcset"] .. '"')
    end
    if attrs["sizes"] then
        table.insert(img_attrs, 'sizes="' .. attrs["sizes"] .. '"')
    end

    local img_attrs_str = ""
    if #img_attrs > 0 then
        img_attrs_str = " " .. table.concat(img_attrs, " ")
    end

    -- Determine display src (use .light variant if dark exists and we're explicit)
    local display_src = src

    -- Construct the HTML
    local html = '<div class="' .. table.concat(wrapper_classes, " ") .. '" '
        .. table.concat(attr_parts, " ") .. '>'
        .. '<img src="' .. display_src .. '" alt="' .. alt:gsub('"', '&quot;') .. '"'
        .. img_attrs_str
        .. ' class="gd-lightbox-img" loading="lazy"'
        .. '>'
        .. '<button class="gd-lightbox-expand" aria-label="Enlarge image" title="Click to enlarge">'
        .. '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        .. 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        .. '<polyline points="15 3 21 3 21 9"></polyline>'
        .. '<polyline points="9 21 3 21 3 15"></polyline>'
        .. '<line x1="21" y1="3" x2="14" y2="10"></line>'
        .. '<line x1="3" y1="21" x2="10" y2="14"></line>'
        .. '</svg>'
        .. '</button>'
        .. '</div>'

    return pandoc.RawBlock("html", html)
end

--- Render a .lightbox-compare fenced div as a comparison slider.
--- Expected: two images inside the div.
--- @param div pandoc.Div
--- @return pandoc.RawBlock|nil
local function render_compare_div(div)
    local images = {}
    div:walk({
        Image = function(img)
            table.insert(images, img)
        end
    })
    if #images < 2 then return nil end

    local before_img = images[1]
    local after_img = images[2]

    -- Read optional attributes from the div
    local attrs = div.attributes or {}
    local direction = attrs["direction"] or "horizontal"
    local start_pos = attrs["start"] or "50"

    -- Determine labels from image class (.before/.after) caption, or defaults
    local label_before = before_img.attributes["caption"] or "Before"
    local label_after = after_img.attributes["caption"] or "After"

    local data_attrs = ' data-direction="' .. direction .. '"'
        .. ' data-start-position="' .. start_pos .. '"'
        .. ' data-label-before="' .. label_before:gsub('"', '&quot;') .. '"'
        .. ' data-label-after="' .. label_after:gsub('"', '&quot;') .. '"'

    local before_alt = pandoc.utils.stringify(before_img.caption) or label_before
    local after_alt = pandoc.utils.stringify(after_img.caption) or label_after

    local html = '<div class="gd-compare"' .. data_attrs .. '>'
        .. '<img src="' .. before_img.src .. '" alt="' .. before_alt:gsub('"', '&quot;') .. '">'
        .. '<img src="' .. after_img.src .. '" alt="' .. after_alt:gsub('"', '&quot;') .. '">'
        .. '</div>'

    return pandoc.RawBlock("html", html)
end

--- Main filter: process images in the document.
--- Note: gd-lightbox.js and gd-lightbox.css are injected globally via core.py
--- using the quarto:offset pattern (handles subdirectory pages correctly).
--- The Lua filter only transforms image markup.
return {
    {
        Meta = function(meta)
            read_meta(meta)
            return meta
        end
    },
    {
        -- Process .lightbox-compare fenced divs and code output cells
        Div = function(div)
            if has_class(div, "lightbox-compare") then
                return render_compare_div(div)
            end

            -- Auto-enhance computational cell outputs (fig-* outputs)
            -- In auto mode, images inside .cell-output-display get lightbox
            if lightbox_mode == "auto" and has_class(div, "cell-output-display") then
                local blocks = {}
                local changed = false
                for _, block in ipairs(div.content) do
                    if block.t == "Para" and #block.content == 1
                        and block.content[1].t == "Image" then
                        local img = block.content[1]
                        if not has_class(img, "nolightbox") then
                            -- Auto-add lightbox to cell output images
                            table.insert(blocks, render_lightbox_image(img))
                            changed = true
                        else
                            table.insert(blocks, block)
                        end
                    else
                        table.insert(blocks, block)
                    end
                end
                if changed then
                    return pandoc.Div(blocks, div.attr)
                end
            end

            return nil
        end,

        -- Process images that appear as standalone paragraphs (block-level)
        Para = function(para)
            -- A paragraph with a single image is a "figure" in Pandoc
            if #para.content == 1 and para.content[1].t == "Image" then
                local img = para.content[1]
                if should_lightbox(img) then
                    return render_lightbox_image(img)
                end
            end
            return nil
        end,

        -- Process explicit figure environments
        Figure = function(fig)
            -- Walk into the figure to find images
            local modified = false
            local result = fig:walk({
                Image = function(img)
                    if should_lightbox(img) then
                        -- We'll handle at Figure level
                        modified = true
                    end
                    return nil
                end
            })
            if modified and fig.content and #fig.content > 0 then
                -- Extract the first image from the figure
                local img = nil
                fig:walk({
                    Image = function(i)
                        if not img then img = i end
                        return nil
                    end
                })
                if img and should_lightbox(img) then
                    return render_lightbox_image(img)
                end
            end
            return nil
        end,
    }
}
