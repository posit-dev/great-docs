--- Resolve documentation references against a prebuilt index
---
--- great-docs writes `_inv/index.lua` before Quarto runs. This filter parses a
--- reference, looks the name up, and renders the result. It does no merging,
--- no priority arithmetic and no inventory parsing.

local quarto = _G.quarto --- @diagnostic disable-line:undefined-field
local pandoc = _G.pandoc --- @diagnostic disable-line:undefined-field

-- Pandoc percent-encodes the backticks that carry a reference target.
local HEX_QUOTE = "%%60"

local CALLABLE_ROLES = { ["function"] = true, ["method"] = true }

local index = nil

--- Check whether a file can be read
--- @param path string
--- @return boolean
local function file_exists(path)
  local f = io.open(path, "r")
  if f then
    f:close()
    return true
  end
  return false
end

--- Read the index, keeping a compiled copy for the other pandoc processes
--- @return table
local function load_index()
  local root = quarto.project.offset or "."
  local binary = root .. "/_inv/index.luac"
  local source = root .. "/_inv/index.lua"

  if file_exists(binary) then
    local compiled = loadfile(binary)
    if compiled then
      return compiled()
    end
  end

  local chunk = loadfile(source)
  if not chunk then
    return { prefixes = {}, names = {} }
  end

  -- Rename rather than write in place: a parallel render must never load a
  -- half-written file. The token comes from this process's own table address.
  local token = (tostring({}):gsub("[^%w]", ""))
  local tmp = binary .. "." .. token
  local out = io.open(tmp, "wb")
  if out then
    out:write(string.dump(chunk))
    out:close()
    os.rename(tmp, binary)
  end

  return chunk()
end

--- @return table
local function get_index()
  if index == nil then
    index = load_index()
  end
  return index
end

--- Split a string on a separator
--- @param str string
--- @param sep string
--- @return string[]
local function split_on(str, sep)
  local tokens = {}
  for s in string.gmatch(str, "([^" .. sep .. "]+)") do
    tokens[#tokens + 1] = s
  end
  return tokens
end

--- @param name string
--- @return string
local function short_name(name)
  local tokens = split_on(name, "%.")
  return tokens[#tokens]
end

--- Give a role its standard name
--- @param role string
--- @return string
local function standard_role(role)
  if role == "func" then
    return "function"
  elseif role == "meth" then
    return "method"
  elseif role == "attr" then
    return "attribute"
  elseif role == "mod" then
    return "module"
  end
  return role
end

--- Read a link target into a reference
---
--- Accepts `~pkg.Name` and the Sphinx role forms `:func:`x``,
--- `:py:class:`x`` and `:external+numpy:py:class:`x``.
---
--- @param target string
--- @return table|nil
local function parse_target(target)
  local ref = {}
  local quoted = HEX_QUOTE .. "(.*)" .. HEX_QUOTE

  if target:sub(1, 1) == ":" then
    local tokens = split_on(target, ":")
    if #tokens == 2 then
      ref.role = standard_role(tokens[1])
      ref.name = tokens[2]:match(quoted)
    elseif #tokens == 3 then
      ref.domain = tokens[1]
      ref.role = standard_role(tokens[2])
      ref.name = tokens[3]:match(quoted)
    elseif #tokens == 4 then
      ref.source = tokens[1]:match("external%+(.*)")
      ref.domain = tokens[2]
      ref.role = standard_role(tokens[3])
      ref.name = tokens[4]:match(quoted)
    end
  else
    ref.name = target:match(quoted)
  end

  if not ref.name then
    return nil
  end

  if ref.name:sub(1, 1) == "~" then
    ref.shortened = true
    ref.name = ref.name:sub(2)
  end

  return ref
end

--- Rewrite a leading module alias into the roots it stands for
--- @param name string
--- @return string[]
local function alias_forms(name)
  local head, rest = name:match("^([%w_]+)%.(.+)$")
  if not head then
    return {}
  end
  local roots = get_index().prefixes[head]
  if not roots then
    return {}
  end
  local forms = {}
  for _, root in ipairs(roots) do
    forms[#forms + 1] = root .. "." .. rest
  end
  return forms
end

--- Find the entry a reference points at
--- @param ref table
--- @param local_only boolean
--- @return table|nil
local function lookup(ref, local_only)
  local candidates = { ref.name }
  for _, form in ipairs(alias_forms(ref.name)) do
    candidates[#candidates + 1] = form
  end

  for _, name in ipairs(candidates) do
    local entries = get_index().names[name]
    if entries then
      for _, entry in ipairs(entries) do
        local matches = (not ref.role or entry.role == ref.role)
          and (not ref.domain or entry.domain == ref.domain)
          and (not ref.source or entry.source == ref.source)
          and (not local_only or entry["local"])
        if matches then
          return entry
        end
      end
    end
  end

  return nil
end

--- Build the text shown for a resolved reference
--- @param ref table
--- @param entry table
--- @return string
local function link_text(ref, entry)
  local text = ref.shortened and short_name(ref.name) or ref.name
  if get_index().add_function_parentheses and CALLABLE_ROLES[entry.role] then
    text = text .. "()"
  end
  return text
end

--- @param content table
--- @param uri string
--- @param classes string[]
--- @return table
local function make_link(content, uri, classes)
  return pandoc.Link(content, uri, "", pandoc.Attr("", classes))
end

--- Resolve an explicit reference
--- @param link table
local function Link(link)
  if not link.target:match(HEX_QUOTE) then
    return link, false
  end

  local ref = parse_target(link.target)
  if not ref then
    return nil, false
  end

  local entry = lookup(ref, false)
  local authored = #link.content > 0

  if not entry then
    quarto.log.warning("interlinks: no match for " .. ref.name)
    if authored then
      return link.content, false
    end
    local text = ref.shortened and short_name(ref.name) or ref.name
    return pandoc.Code(text), false
  end

  if authored then
    return make_link(link.content, entry.uri, { "gdls-link" }), false
  end

  -- The anchor carries the monospace styling itself, so the text is plain.
  return make_link({ pandoc.Str(link_text(ref, entry)) }, entry.uri, { "gdls-link", "gdls-code" }),
    false
end

--- Split a code span into its display prefix, name and call parentheses
--- @param text string
--- @return string|nil, string|nil, string|nil
local function parse_code(text)
  local prefix = ""
  local rest = text

  if rest:sub(1, 3) == "~~." then
    prefix, rest = "~~.", rest:sub(4)
  elseif rest:sub(1, 2) == "~~" then
    prefix, rest = "~~", rest:sub(3)
  end

  local parens = ""
  if rest:sub(-2) == "()" then
    parens, rest = "()", rest:sub(1, -3)
  end

  if not rest:match("^[%a_][%w_%.]*$") then
    return nil, nil, nil
  end

  return prefix, rest, parens
end

--- Link a code span that names a documented object
--- @param code table
local function Code(code)
  if code.classes:includes("gd-no-link") then
    return nil
  end

  local prefix, name, parens = parse_code(code.text)
  if not name then
    return nil
  end

  local entry = lookup({ name = name }, true)
  local short = short_name(name)

  if not entry then
    if prefix == "~~." then
      return pandoc.Code("." .. short .. parens, code.attr)
    elseif prefix == "~~" then
      return pandoc.Code(short .. parens, code.attr)
    end
    return nil
  end

  local display
  if prefix == "~~." then
    display = "." .. short .. parens
  elseif prefix == "~~" then
    display = short .. parens
  else
    display = name .. parens
  end

  return make_link({ pandoc.Str(display) }, entry.uri, { "gdls-link", "gdls-code" })
end

return {
  {
    traverse = "topdown",
    Link = Link,
    Code = Code,
  },
}
