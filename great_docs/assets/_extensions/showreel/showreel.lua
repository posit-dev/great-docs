-- showreel.lua — Quarto shortcode for embedding narrated demo reels.
--
-- Usage in .qmd files:
--
--   {{< showreel file="reels/data-color" >}}
--
-- Options:
--   file   (required) Path to the reel (without the .showreel.yml extension)
--
-- The reel must be pre-built: `prerender_showreels()` (run during the Great
-- Docs build) writes a self-contained `showreel/<name>/embed.html` that this
-- filter injects. The embed inlines the manifest, media (as data URIs), and the
-- player runtime, so there are no runtime fetches.

local function kwarg_str(kwargs, key)
    local raw = kwargs[key]
    if raw == nil then return "" end
    return pandoc.utils.stringify(raw) or ""
end

--- Read a file relative to the Quarto project input directory.
local function read_project_file(rel_path)
    local base = ""
    if quarto and quarto.project and quarto.project.directory then
        base = quarto.project.directory .. "/"
    end
    local f = io.open(base .. rel_path, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    return content
end

return {
    ["showreel"] = function(args, kwargs, meta)
        local file = kwarg_str(kwargs, "file")
        if file == "" and #args > 0 then
            file = pandoc.utils.stringify(args[1])
        end
        if file == "" then
            quarto.log.warning("[showreel] 'file' attribute is required")
            return pandoc.Null()
        end

        local basename = file:match("([^/]+)$") or file
        local embed = read_project_file("showreel/" .. basename .. "/embed.html")
        if not embed then
            quarto.log.warning(
                "[showreel] no pre-built reel for '" .. basename ..
                "' (expected showreel/" .. basename .. "/embed.html)")
            return pandoc.RawBlock("html",
                '<div class="gd-showreel-missing">Showreel &quot;' .. basename ..
                '&quot; has not been built.</div>')
        end

        return pandoc.RawBlock("html", embed)
    end
}
