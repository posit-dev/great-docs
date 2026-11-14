--- Stand-ins for the HTML features Great Docs relies on that Quarto 2 lacks (experimental)
---
--- Great Docs registers this filter only for a Quarto 2 render, and it reads its settings
--- from `gd-quarto2` in `_quarto.yml`. Quarto 2 ignores `shift-heading-level-by` for HTML
--- and the `metadata.html` partial, and writes no Open Graph or Twitter card tags, so the
--- filter shifts the headings and adds the partial's page tags and the card tags. It also
--- sets no text direction, and writes a page's `body-classes` in place of the classes it
--- computes for the layout, so the filter records both in `<meta>` tags for Great Docs'
--- Quarto 2 post-render script to move onto `<html>` and `<body>`.

local pandoc = _G.pandoc --- @diagnostic disable-line:undefined-field
local quarto = _G.quarto --- @diagnostic disable-line:undefined-field

local stringify = pandoc.utils.stringify

--- @param value any
--- @return string|nil
local function text(value)
  if value == nil or value == false then
    return nil
  end
  local s = stringify(value)
  if s == "" then
    return nil
  end
  return s
end

--- Escape a value for a double-quoted HTML attribute
--- @param s string
--- @return string
local function attribute(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

--- Read the markup of a head tag that Great Docs stores as inline raw HTML
---
--- Quarto 2 may read the stored form, `` `<meta ...>`{=html} ``, as raw HTML that keeps its
--- backticks and `{=html}`, or as plain text, so unwrap whichever arrives.
--- @param value any
--- @return string|nil
local function raw_markup(value)
  local parts = {}
  if type(value) == "string" then
    parts[1] = value
  elseif type(value) == "table" then
    for _, el in ipairs(value) do
      if (el.t == "RawInline" or el.t == "RawBlock") and el.format == "html" then
        parts[#parts + 1] = el.text
      end
    end
    if #parts == 0 then
      parts[1] = stringify(value)
    end
  end
  local markup = table.concat(parts)
  local fence = markup:match("^(`+)")
  if fence then
    local inner = markup:match("^" .. fence .. "(.-)" .. fence .. "{=html}$")
    if inner then
      markup = inner
    end
  end
  if markup == "" then
    return nil
  end
  return markup
end

--- Shift every heading as Pandoc's `--shift-heading-level-by` does
---
--- A heading shifted below level 1 becomes a paragraph. When the document opens with a
--- heading that a negative shift moves to level 0, the heading becomes the title.
--- @param doc table
--- @param by integer
--- @return table
local function shift_headings(doc, by)
  local blocks = doc.blocks
  if by < 0 and #blocks > 0 and blocks[1].t == "Header" and blocks[1].level + by == 0 then
    doc.meta.title = pandoc.MetaInlines(blocks[1].content)
    blocks:remove(1)
  end
  doc.blocks = blocks:walk({
    Header = function(header)
      if header.level + by > 0 then
        header.level = header.level + by
        return header
      end
      return pandoc.Para(header.content)
    end,
  })
  return doc
end

--- The page's tags that the metadata partial would write
--- @param meta table
--- @return string[]
local function partial_tags(meta)
  local tags = {}
  local robots = text(meta.robots)
  if robots then
    tags[#tags + 1] = '<meta name="robots" content="' .. attribute(robots) .. '">'
  end
  if meta["gd-auto-generated"] then
    tags[#tags + 1] = '<meta name="gd-auto-generated" content="true">'
  end
  for _, entry in ipairs(meta["gd-head-tags"] or {}) do
    local markup = raw_markup(entry)
    if markup then
      tags[#tags + 1] = markup
    end
  end
  return tags
end

--- Read a key of a page's card option, which may be `true`, `false` or a mapping
--- @param option any
--- @param key string
--- @return string|nil
local function card_value(option, key)
  if type(option) == "table" and option[key] ~= nil then
    return text(option[key])
  end
  return nil
end

--- The Open Graph and Twitter card tags for the page, as Quarto 1 writes them
--- @param meta table
--- @param cards table
--- @param site_title string|nil
--- @return string[]
local function card_tags(meta, cards, site_title)
  if meta["gd-own-social-cards"] or meta["open-graph"] == false then
    return {}
  end
  local open_graph, twitter = meta["open-graph"], meta["twitter-card"]

  local page_title = text(meta.title)
  local default_title = site_title
  if page_title and site_title then
    default_title = page_title .. " – " .. site_title
  elseif page_title then
    default_title = page_title
  end
  local title = card_value(open_graph, "title") or default_title
  local description = card_value(open_graph, "description")
    or text(meta["description-meta"])
    or text(meta.description)
  local image = card_value(open_graph, "image") or text(cards.image)

  local tags = { '<meta property="og:type" content="website">' }
  local function add(kind, key, value)
    if value then
      tags[#tags + 1] = "<meta " .. kind .. '="' .. key .. '" content="' .. attribute(value) .. '">'
    end
  end
  add("property", "og:title", title)
  add("property", "og:description", description)
  add("property", "og:image", image)
  add("property", "og:site_name", site_title)

  if twitter ~= false then
    local card = text(cards.card) or (image and "summary_large_image" or "summary")
    add("name", "twitter:card", card)
    add("name", "twitter:title", card_value(twitter, "title") or title)
    add("name", "twitter:description", card_value(twitter, "description") or description)
    add("name", "twitter:image", card_value(twitter, "image") or image)
    add("name", "twitter:site", text(cards.site))
  end
  return tags
end

function Pandoc(doc)
  local meta = doc.meta
  local settings = meta["gd-quarto2"]
  if type(settings) ~= "table" then
    return nil
  end
  local site_title = text(settings["site-title"])

  local by = meta["shift-heading-level-by"] or settings["shift-heading-level-by"]
  if type(by) ~= "number" then
    by = tonumber(by and stringify(by))
  end
  if by and by ~= 0 then
    doc = shift_headings(doc, math.floor(by))
  end

  -- Quarto 1 titles a page with an empty title after the site
  if meta.title ~= nil and text(meta.title) == nil and meta.pagetitle == nil and site_title then
    doc.meta.pagetitle = pandoc.MetaString(site_title)
  end

  local tags = partial_tags(meta)
  if type(settings["social-cards"]) == "table" then
    for _, tag in ipairs(card_tags(meta, settings["social-cards"], site_title)) do
      tags[#tags + 1] = tag
    end
  end

  -- The post-render script moves these markers onto `<html>` and `<body>`
  local dir = text(meta.dir)
  if dir == "rtl" or dir == "ltr" then
    tags[#tags + 1] = '<meta name="gd-dir" content="' .. dir .. '">'
  end
  local value = meta["body-classes"]
  local values = pandoc.utils.type(value) == "List" and value or { value }
  local classes = {}
  for _, item in ipairs(values) do
    for name in (text(item) or ""):gmatch("[%w_-]+") do
      classes[#classes + 1] = name
    end
  end
  if #classes > 0 then
    -- Leave Quarto 2 to compute the layout classes
    doc.meta["body-classes"] = nil
    tags[#tags + 1] = '<meta name="gd-body-classes" content="' .. table.concat(classes, " ") .. '">'
  end

  for _, tag in ipairs(tags) do
    quarto.doc.include_text("in-header", tag)
  end
  return doc
end
