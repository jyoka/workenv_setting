import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CACHE = ROOT / "config/yazi/plugins/preview-cache.yazi/main.lua"
PLUGINS = ROOT / "config/yazi/plugins"


@unittest.skipUnless(shutil.which("luajit"), "luajit is required")
class PreviewCacheTests(unittest.TestCase):
    def test_same_second_save_invalidates_both_preview_cache_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "index.html"
            file.write_text("first", encoding="utf-8")
            os.utime(file, (1_600_000_000, 1_600_000_000))
            script = (
                "function Command(exe)\n"
                "  return {arg = function(self, args)\n"
                "    return {output = function()\n"
                "      local handle = assert(io.popen(exe .. ' -q ' .. string.format('%q', args[2])))\n"
                "      local stdout = handle:read('*a')\n"
                "      local ok = handle:close()\n"
                "      return {stdout = stdout, status = {success = ok == true or ok == 0}}\n"
                "    end}\n"
                "  end}\n"
                "end\n"
                f"local cache = dofile({str(CACHE)!r})\n"
                f"local job = {{file = {{url = {str(file)!r}, cha = {{mtime = 1600000000}}}}}}\n"
                "for _, dir in ipairs({'/tmp/yazi-office-cache', '/tmp/yazi-html-cache'}) do\n"
                "  print(cache.key(job, dir))\n"
                "end\n"
            )
            first = subprocess.check_output(["luajit", "-e", script], text=True)
            file.write_text("later", encoding="utf-8")  # Same size and mtime.
            os.utime(file, (1_600_000_000, 1_600_000_000))
            second = subprocess.check_output(["luajit", "-e", script], text=True)
            third = subprocess.check_output(["luajit", "-e", script], text=True)
            self.assertEqual(len(first.splitlines()), 2)
            self.assertNotEqual(first, second)
            self.assertEqual(second, third)

    def test_plugins_load_and_reference_shared_cache(self):
        for name in ("office", "html-view"):
            path = PLUGINS / f"{name}.yazi/main.lua"
            source = path.read_text(encoding="utf-8")
            self.assertIn('require("preview-cache")', source)
            self.assertIn("preview_cache.key(job, CACHE_DIR)", source)
            subprocess.run(["luajit", "-e", f"assert(loadfile({str(path)!r}))"], check=True)
