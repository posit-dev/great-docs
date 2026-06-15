-- gd-compare.lua — Quarto shortcode for before/after image comparison
--
-- Usage:
--   {{< compare before="old.png" after="new.png" >}}
--
-- Optional attributes:
--   label-before="Old"   — Custom label for the before image (default: "Before")
--   label-after="New"    — Custom label for the after image (default: "After")
--   direction="vertical" — Split direction: "horizontal" (default) or "vertical"
--   start="30"           — Initial divider position in % (default: 50)

return {
    ["compare"] = function(args, kwargs, meta)
        -- Helper: safely convert kwarg to string
        local function str(val, default)
            if val == nil then return default end
            if type(val) == "string" then return val end
            return pandoc.utils.stringify(val) or default
        end

        local before = str(kwargs["before"], args[1] or "")
        local after = str(kwargs["after"], args[2] or "")

        if before == "" or after == "" then
            quarto.log.warning("gd-compare shortcode requires 'before' and 'after' images")
            return pandoc.Null()
        end

        local label_before = str(kwargs["label-before"], "Before")
        local label_after = str(kwargs["label-after"], "After")
        local direction = str(kwargs["direction"], "horizontal")
        local start_pos = str(kwargs["start"], "50")

        -- Ensure defaults are applied (kwargs may stringify to "")
        if label_before == "" then label_before = "Before" end
        if label_after == "" then label_after = "After" end
        if direction == "" then direction = "horizontal" end
        if start_pos == "" then start_pos = "50" end

        -- Build data attributes
        local data_attrs = ''
            .. ' data-direction="' .. direction .. '"'
            .. ' data-start-position="' .. start_pos .. '"'
            .. ' data-label-before="' .. label_before:gsub('"', '&quot;') .. '"'
            .. ' data-label-after="' .. label_after:gsub('"', '&quot;') .. '"'

        -- Build HTML
        local html = '<div class="gd-compare"' .. data_attrs .. '>'
            .. '<img src="' .. before .. '" alt="' .. label_before .. '">'
            .. '<img src="' .. after .. '" alt="' .. label_after .. '">'
            .. '</div>'

        return pandoc.RawBlock("html", html)
    end
}
