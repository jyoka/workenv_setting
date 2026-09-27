-- office: pptx / docx / xlsx などをプレビュー欄に表示する
-- 仕組み: LibreOffice (soffice) で裏で変換する
--   - スライド・文書 (pptx, docx など) → PDF → ページ画像 (J/K でページ送り)
--   - 表計算 (xlsx など) → タブ区切りテキスト → 列を揃えて表示
-- 変換結果は /tmp/yazi-office-cache に保存し、内容が変わらなければ再変換しない
local M = {}
local preview_cache = require("preview-cache")

local CACHE_DIR = "/tmp/yazi-office-cache"
local PROFILE = "-env:UserInstallation=file:///tmp/yazi-office-profile"

-- 環境ごとに置き場所が違うので候補から探す(Homebrew なしの Mac にも対応)
local HOME = os.getenv("HOME") or ""
local found = {}
local function find_bin(key, cands)
	if not found[key] then
		found[key] = cands[1]
		for _, p in ipairs(cands) do
			if fs.cha(Url(p)) then
				found[key] = p
				break
			end
		end
	end
	return found[key]
end
local function soffice_bin()
	return find_bin("soffice", {
		"/opt/homebrew/bin/soffice",
		"/usr/local/bin/soffice",
		"/Applications/LibreOffice.app/Contents/MacOS/soffice",
		HOME .. "/Applications/LibreOffice.app/Contents/MacOS/soffice",
		HOME .. "/.local/bin/soffice",
	})
end
local function pdftoppm_bin()
	return find_bin("pdftoppm", {
		"/opt/homebrew/bin/pdftoppm",
		"/usr/local/bin/pdftoppm",
		HOME .. "/.local/bin/pdftoppm",
	})
end

local SHEET_EXTS = { xlsx = true, xls = true, ods = true }

local function ext_of(url)
	return (tostring(url):match("%.(%w+)$") or ""):lower()
end

-- 表計算: 先頭シートを揃えたテキストにして表示
local function peek_sheet(job)
	local base = preview_cache.key(job, CACHE_DIR)
	if not base then
		return ya.preview_widget(job, ui.Text("元ファイルを読めません"):area(job.area))
	end
	local out = base .. ".txt"
	if not fs.cha(Url(out)) then
		local script = [[
set -e
mkdir -p "$3"
d=$(mktemp -d)
trap 'rm -rf "$d"' EXIT
]] .. '"' .. soffice_bin() .. '" ' .. PROFILE .. [[ --headless --convert-to "csv:Text - txt - csv (StarCalc):9,34,UTF8" "$1" --outdir "$d" >/dev/null 2>&1
f=$(ls "$d"/*.csv | head -1)
head -n 500 "$f" | /usr/bin/column -t -s "$(printf '\t')" > "$d/preview.txt"
mv "$d/preview.txt" "$2"
]]
		local output, err = Command("/bin/sh")
			:arg({ "-c", script, "sh", tostring(job.file.url), out, CACHE_DIR })
			:output()
		if not output then
			return ya.preview_widget(job, ui.Text("変換を開始できません: " .. tostring(err)):area(job.area))
		elseif not output.status.success then
			return ya.preview_widget(job, ui.Text("LibreOffice での変換に失敗しました"):area(job.area))
		end
	end

	local file = io.open(out, "r")
	if not file then
		return ya.preview_widget(job, ui.Text("変換結果を読めません"):area(job.area))
	end
	local limit = job.area.h
	local i, lines = 0, ""
	for line in file:lines() do
		i = i + 1
		if i > job.skip + limit then
			break
		end
		if i > job.skip then
			lines = lines .. line .. "\n"
		end
	end
	file:close()

	if job.skip > 0 and i <= job.skip then
		ya.emit("peek", { math.max(0, i - limit), only_if = job.file.url, upper_bound = true })
	else
		ya.preview_widget(job, ui.Text.parse(lines):area(job.area))
	end
end

-- スライド・文書: PDF に変換してページ画像を表示
local function peek_doc(job)
	local start = os.clock()
	local base = preview_cache.key(job, CACHE_DIR)
	if not base then
		return ya.preview_widget(job, ui.Text("元ファイルを読めません"):area(job.area))
	end
	local pdf = base .. ".pdf"
	if not fs.cha(Url(pdf)) then
		local script = [[
set -e
mkdir -p "$3"
d=$(mktemp -d)
trap 'rm -rf "$d"' EXIT
]] .. '"' .. soffice_bin() .. '" ' .. PROFILE .. [[ --headless --convert-to pdf "$1" --outdir "$d" >/dev/null 2>&1
mv "$d"/*.pdf "$2"
]]
		local output, err = Command("/bin/sh")
			:arg({ "-c", script, "sh", tostring(job.file.url), pdf, CACHE_DIR })
			:output()
		if not output then
			return ya.preview_widget(job, ui.Text("変換を開始できません: " .. tostring(err)):area(job.area))
		elseif not output.status.success then
			return ya.preview_widget(job, ui.Text("LibreOffice での変換に失敗しました"):area(job.area))
		end
	end

	local image = base .. "-" .. job.skip .. ".jpg"
	local cache = Url(image .. ".cache")
	if not fs.cha(cache) then
		local output, err = Command(pdftoppm_bin())
			:arg({
				"-f", job.skip + 1,
				"-l", job.skip + 1,
				"-singlefile",
				"-jpeg", "-jpegopt", "quality=" .. rt.preview.image_quality,
				pdf, image:sub(1, -5),
			})
			:output()
		if not output then
			return ya.preview_widget(job, Err("Failed to start `pdftoppm`, error: %s", err))
		elseif not output.status.success then
			-- 最終ページを超えたら最終ページに戻す
			local pages = job.skip > 0 and tonumber(output.stderr:match("the last page %((%d+)%)"))
			if pages and pages > 0 then
				return ya.emit("peek", { pages - 1, only_if = job.file.url, upper_bound = true })
			end
			return ya.preview_widget(job, Err("PDF から画像への変換に失敗: %s", output.stderr))
		end
		local ok, e = ya.image_precache(Url(image), cache)
		if not ok then
			return ya.preview_widget(job, e)
		end
	end

	ya.sleep(math.max(0, rt.preview.image_delay / 1000 + start - os.clock()))
	local _, err = ya.image_show(cache, job.area)
	ya.preview_widget(job, err)
end

function M:peek(job)
	if SHEET_EXTS[ext_of(job.file.url)] then
		return peek_sheet(job)
	end
	return peek_doc(job)
end

function M:seek(job)
	local h = cx.active.current.hovered
	if not h or h.url ~= job.file.url then
		return
	end
	local units = job.units
	if not SHEET_EXTS[ext_of(job.file.url)] then
		-- 文書はページ単位で送る
		units = ya.clamp(-1, job.units, 1)
	end
	ya.emit("peek", { math.max(0, cx.active.preview.skip + units), only_if = job.file.url })
end

return M
