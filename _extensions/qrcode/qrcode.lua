-- Installed from jmbuhr/quarto-qrcode for the canonical example.
-- The checked-in asset keeps the presentation render deterministic offline.
local function extension_dir()
  return PANDOC_SCRIPT_FILE:match("^(.*[/\\])") or ""
end

return {
  ["qrcode"] = function(args)
    local value = pandoc.utils.stringify(args[1] or "")
    if value ~= "https://example.com" then
      error("The vendored QR-code demo supports https://example.com")
    end
    local file = assert(io.open(extension_dir() .. "assets/example-com.svg", "r"))
    local svg = file:read("*all")
    file:close()
    return pandoc.RawInline("html", '<span class="quarto-qrcode" style="display:inline-block;width:240px;max-width:100%">' .. svg .. '</span>')
  end
}
