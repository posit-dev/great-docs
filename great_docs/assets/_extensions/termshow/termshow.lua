-- termshow.lua — Quarto shortcode for embedding terminal recordings.
--
-- Usage in .qmd files:
--
--   {{< termshow file="demos/getting-started" >}}
--
--   {{< termshow file="demos/install" autoplay="true" pause_on_chapters="true" >}}
--
-- Options:
--   file             (required) Path to .termshow file (without extension)
--   autoplay         "true"/"false" - start playing automatically
--   loop             "true"/"false" - loop playback
--   speed            number - playback speed multiplier
--   pause_on_chapters "true"/"false" - auto-pause at chapter boundaries
--   poster           number - time (s) for poster frame
--   controls         "true"/"false" - show control bar
--   theme            "auto"/"dark"/"light" - player theme override
--
-- The shortcode embeds manifest JSON + SVG frames inline so the player
-- works without network fetches (including with file:// protocol).

local function escape_attr(s)
    if s == nil then return "" end
    return s:gsub('"', "&quot;"):gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
end

local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    local s = pandoc.utils.stringify(raw)
    return s or ""
end

--- Read a file relative to the Quarto project input directory.
local function read_project_file(rel_path)
    -- quarto.project.directory is the project root during render
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
    ["termshow"] = function(args, kwargs, meta)
        -- Get file path (required)
        local file = kwarg_str(kwargs, "file")
        if file == "" and #args > 0 then
            file = pandoc.utils.stringify(args[1])
        end
        if file == "" then
            quarto.log.warning("[termshow] 'file' attribute is required")
            return pandoc.Null()
        end

        -- Build paths
        local basename = file:match("([^/]+)$") or file
        local tp_dir = "termshow/" .. basename .. "/"

        -- Read options
        local autoplay = kwarg_str(kwargs, "autoplay")
        if autoplay == "" then autoplay = "false" end
        local loop = kwarg_str(kwargs, "loop")
        if loop == "" then loop = "false" end
        local speed = kwarg_str(kwargs, "speed")
        if speed == "" then speed = "1" end
        local pause_on_chapters = kwarg_str(kwargs, "pause_on_chapters")
        if pause_on_chapters == "" then pause_on_chapters = "false" end
        local poster = kwarg_str(kwargs, "poster")
        if poster == "" then poster = "0" end
        local controls = kwarg_str(kwargs, "controls")
        if controls == "" then controls = "true" end
        local theme = kwarg_str(kwargs, "theme")
        if theme == "" then theme = "auto" end

        -- Try to read manifest.json from the pre-rendered output
        local manifest_json = read_project_file(tp_dir .. "manifest.json")

        -- Read SVG frames inline if manifest exists
        local frames_json = "[]"
        if manifest_json then
            -- Parse keyframes from manifest to know which SVGs to embed
            local frames = {}
            for frame_file in manifest_json:gmatch('"file"%s*:%s*"([^"]+)"') do
                local svg = read_project_file(tp_dir .. frame_file)
                if svg then
                    -- Escape for JSON string embedding
                    local escaped = svg:gsub("\\", "\\\\"):gsub('"', '\\"')
                        :gsub("\n", "\\n"):gsub("\r", "\\r")
                        :gsub("\t", "\\t")
                    table.insert(frames, '"' .. escaped .. '"')
                end
            end
            if #frames > 0 then
                frames_json = "[" .. table.concat(frames, ",") .. "]"
            end
        end

        -- Build poster path (fallback if inline fails)
        local offset = ""
        if quarto and quarto.project and quarto.project.offset then
            offset = quarto.project.offset .. "/"
        end
        local poster_path = offset .. tp_dir .. "frame-000.svg"
        local manifest_url = offset .. tp_dir .. "manifest.json"

        -- Generate HTML with inline data
        local parts = {}
        table.insert(parts, '<div class="gd-termshow" ')
        table.insert(parts, 'data-manifest="' .. escape_attr(manifest_url) .. '" ')
        table.insert(parts, 'data-autoplay="' .. escape_attr(autoplay) .. '" ')
        table.insert(parts, 'data-loop="' .. escape_attr(loop) .. '" ')
        table.insert(parts, 'data-speed="' .. escape_attr(speed) .. '" ')
        table.insert(parts, 'data-pause-on-chapters="' .. escape_attr(pause_on_chapters) .. '">')

        -- Embed manifest as inline JSON script
        if manifest_json then
            table.insert(parts, '\n  <script type="application/json" class="gd-tp-manifest">')
            table.insert(parts, manifest_json)
            table.insert(parts, '</script>')
            -- Embed SVG frames as inline JSON array
            table.insert(parts, '\n  <script type="application/json" class="gd-tp-frames">')
            table.insert(parts, frames_json)
            table.insert(parts, '</script>')
        end

        -- Poster image (visible before JS inits, works with file://)
        table.insert(parts, '\n  <img src="' .. escape_attr(poster_path) .. '" ')
        table.insert(parts, 'alt="Terminal recording: ' .. escape_attr(basename) .. '" ')
        table.insert(parts, 'class="gd-termshow-poster" loading="lazy"/>')

        table.insert(parts, '\n  <noscript>')
        table.insert(parts, '\n    <p>Terminal recording: ' .. escape_attr(basename))
        table.insert(parts, ' (requires JavaScript for playback)</p>')
        table.insert(parts, '\n  </noscript>')
        table.insert(parts, '\n</div>')

        return pandoc.RawInline("html", table.concat(parts))
    end
}
