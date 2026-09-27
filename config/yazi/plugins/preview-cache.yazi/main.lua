-- Content-based cache identity shared by the Office and HTML previewers.
-- Yazi's cha.mtime is an integer, so it cannot distinguish two saves in one second.
local M = {}

function M.key(job, dir)
	local path = tostring(job.file.url)
	local output = Command("/sbin/md5"):arg({ "-q", path }):output()
	if not output or not output.status.success then
		return nil
	end
	local digest = output.stdout:match("^(%x+)")
	if not digest then
		return nil
	end
	local path_hash = 5381
	for i = 1, #path do
		path_hash = (path_hash * 33 + path:byte(i)) % 4294967296
	end
	return dir .. "/" .. string.format("%08x", path_hash) .. digest
end

return M
