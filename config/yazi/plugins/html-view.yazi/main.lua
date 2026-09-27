-- html-view: .html をヘッドレス Chrome でレンダリングし、プレビュー欄に画像表示する
-- ファイルの内容が変わると自動で再レンダリングされる
-- キャッシュ: /tmp/yazi-html-cache
local M = {}
local preview_cache = require("preview-cache")

local CACHE_DIR = "/tmp/yazi-html-cache"

-- Chrome 系ブラウザを候補から探す(Homebrew なし・ユーザー領域インストールにも対応)
local HOME = os.getenv("HOME") or ""
local chrome_found
local function chrome_bin()
	if not chrome_found then
		local cands = {
			"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
			HOME .. "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
			"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
			HOME .. "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
		}
		chrome_found = cands[1]
		for _, p in ipairs(cands) do
			if fs.cha(Url(p)) then
				chrome_found = p
				break
			end
		end
	end
	return chrome_found
end

function M:peek(job)
	local start = os.clock()
	local base = preview_cache.key(job, CACHE_DIR)
	if not base then
		return ya.preview_widget(job, ui.Text("元ファイルを読めません"):area(job.area))
	end
	local png = base .. ".png"
	if not fs.cha(Url(png)) then
		local script = [[
set -e
mkdir -p "$3"
d=$(mktemp -d)
trap 'rm -rf "$d"' EXIT
"]] .. chrome_bin() .. [[" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1024,768 --screenshot="$d/preview.png" "file://$1" >/dev/null 2>&1
mv "$d/preview.png" "$2"
]]
		local output, err = Command("/bin/sh")
			:arg({ "-c", script, "sh", tostring(job.file.url), png, CACHE_DIR })
			:output()
		if not output then
			return ya.preview_widget(job, ui.Text("Chrome を起動できません: " .. tostring(err)):area(job.area))
		elseif not output.status.success or not fs.cha(Url(png)) then
			return ya.preview_widget(job, ui.Text("HTML のレンダリングに失敗しました"):area(job.area))
		end
	end

	local shown = Url(png .. ".cache")
	if not fs.cha(shown) then
		local ok, e = ya.image_precache(Url(png), shown)
		if not ok then
			return ya.preview_widget(job, e)
		end
	end

	ya.sleep(math.max(0, rt.preview.image_delay / 1000 + start - os.clock()))
	local _, err = ya.image_show(shown, job.area)
	ya.preview_widget(job, err)
end

function M:seek() end

return M
