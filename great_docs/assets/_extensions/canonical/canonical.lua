-- Add a canonical link to each page rendered by Quarto.
--
-- Read the preferred site URL from `gd-canonical-base-url` in `_quarto.yml`.
-- The URL must end with a slash. Skip pages when this setting is absent.
--
-- Use directory URLs for index pages: `guide/index.html` becomes `<base>guide/`,
-- and `index.html` becomes `<base>`.

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

--- Build the preferred URL for a page, using directory URLs for index pages.
---@param base string  Site address with a trailing slash.
---@param path string  Page path relative to the site root.
---@return string
local function canonical_url(base, path)
    if path == "index.html" then return base end
    local dir = path:match("^(.*/)index%.html$")
    if dir then return base .. dir end
    return base .. path
end

function Meta(meta)
    local base = meta["gd-canonical-base-url"]
    if base == nil or quarto.doc.output_file == nil then return nil end

    local path = page_path(quarto.doc.output_file, quarto.project.output_directory)
    if path == nil then return nil end

    local url = canonical_url(pandoc.utils.stringify(base), path)
    quarto.doc.include_text("in-header", '<link rel="canonical" href="' .. url .. '">')
    return nil
end
