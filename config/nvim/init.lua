-- Neovim config - Agentic Engineering Workflow
-- Keyboard-only fast navigation: relative numbers + Telescope fuzzy find.
-- Leader = <space>.  Bootstraps lazy.nvim on first launch.

-- ── Leader must be set before plugins load ──────────────────
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- ── Core options ────────────────────────────────────────────
local o = vim.opt
o.number = true            -- current absolute line
o.relativenumber = true    -- others relative -> fast jumps (5j / 12k)
o.mouse = 'a'
o.clipboard = 'unnamedplus'
o.ignorecase = true
o.smartcase = true
o.termguicolors = true
o.signcolumn = 'yes'
o.expandtab = true
o.shiftwidth = 2
o.tabstop = 2
o.smartindent = true
o.scrolloff = 8
o.splitright = true
o.splitbelow = true
o.undofile = true
o.updatetime = 250
o.completeopt = 'menuone,noselect,popup'  -- completion menu only on demand

-- quick escape + save
vim.keymap.set('i', 'jk', '<Esc>', { desc = 'Escape' })
vim.keymap.set('n', '<leader>w', '<cmd>w<cr>', { desc = 'Write' })
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<cr>', { desc = 'Clear search' })

-- ── Bootstrap lazy.nvim ─────────────────────────────────────
local lazypath = vim.fn.stdpath('data') .. '/lazy/lazy.nvim'
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    'git', 'clone', '--filter=blob:none',
    'https://github.com/folke/lazy.nvim.git', '--branch=stable', lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- ── Plugins ─────────────────────────────────────────────────
require('lazy').setup({
  -- Rose Pine Moon theme
  {
    'rose-pine/neovim',
    name = 'rose-pine',
    priority = 1000,
    config = function()
      require('rose-pine').setup({ variant = 'moon' })
      vim.cmd.colorscheme('rose-pine')
    end,
  },

  -- Telescope: fuzzy finder (files + live grep)
  {
    'nvim-telescope/telescope.nvim',
    branch = '0.1.x',
    dependencies = { 'nvim-lua/plenary.nvim' },
    config = function()
      local builtin = require('telescope.builtin')
      -- space f -> find files by name
      vim.keymap.set('n', '<leader>f', builtin.find_files, { desc = 'Find files' })
      -- space s -> live grep (search file contents, needs ripgrep)
      vim.keymap.set('n', '<leader>s', builtin.live_grep, { desc = 'Search (grep)' })
      vim.keymap.set('n', '<leader>b', builtin.buffers, { desc = 'Buffers' })
      vim.keymap.set('n', '<leader>h', builtin.help_tags, { desc = 'Help' })
      -- space d -> all diagnostics (errors/warnings) in a picker
      vim.keymap.set('n', '<leader>d', builtin.diagnostics, { desc = 'Diagnostics' })
    end,
  },

  -- Treesitter: better syntax highlighting (classic API lives on master)
  {
    'nvim-treesitter/nvim-treesitter',
    branch = 'master',
    build = ':TSUpdate',
    init = function()
      -- master predates Nvim 0.12, which always passes node lists to query
      -- handlers. Give its old-style (all = false) handlers a single node,
      -- else markdown code blocks (and LSP hover) throw errors.
      if vim.fn.has('nvim-0.12') == 0 then return end
      local query = vim.treesitter.query
      for _, fn in ipairs({ 'add_predicate', 'add_directive' }) do
        local orig = query[fn]
        query[fn] = function(name, handler, opts)
          if type(opts) == 'table' and opts.all == false then
            local inner = handler
            handler = function(match, ...)
              local last = {}
              for id, nodes in pairs(match) do last[id] = nodes[#nodes] end
              return inner(last, ...)
            end
          end
          return orig(name, handler, opts)
        end
      end
    end,
    config = function()
      require('nvim-treesitter.configs').setup({
        ensure_installed = { 'lua', 'vim', 'vimdoc', 'bash', 'python', 'javascript', 'typescript', 'json', 'markdown', 'zig' },
        auto_install = true,
        highlight = { enable = true },
      })
    end,
  },

  -- LSP: Mason installs the servers, nvim-lspconfig ships their configs
  { 'mason-org/mason.nvim', opts = { ui = { border = 'rounded' } } },
  {
    'mason-org/mason-lspconfig.nvim',
    dependencies = { 'mason-org/mason.nvim', 'neovim/nvim-lspconfig' },
    opts = {
      -- installed on first launch, then enabled via vim.lsp.enable()
      ensure_installed = { 'pyright', 'ts_ls', 'lua_ls', 'zls' },
      -- ruff / stylua are formatters (conform below), not language servers
      automatic_enable = { exclude = { 'ruff', 'stylua' } },
    },
  },

  -- Auto-install formatters on first launch (zig fmt ships with zig itself)
  {
    'WhoIsSethDaniel/mason-tool-installer.nvim',
    dependencies = { 'mason-org/mason.nvim' },
    opts = {
      ensure_installed = { 'ruff', 'prettier', 'stylua' },
    },
  },

  -- ── Format on save ───────────────────────────────────────
  -- Conform: runs the formatter for the filetype on every :w
  {
    'stevearc/conform.nvim',
    dependencies = { 'mason-org/mason.nvim' },
    opts = {
      formatters_by_ft = {
        python = { 'ruff_organize_imports', 'ruff_format' },
        javascript = { 'prettier' },
        javascriptreact = { 'prettier' },
        typescript = { 'prettier' },
        typescriptreact = { 'prettier' },
        json = { 'prettier' },
        markdown = { 'prettier' },
        lua = { 'stylua' },
        zig = { 'zigfmt' },
      },
      formatters = {
        -- no stylua.toml nearby -> keep this file's style (2 spaces, single quotes)
        stylua = {
          prepend_args = function(_, ctx)
            if vim.fs.find({ 'stylua.toml', '.stylua.toml' }, { upward = true, path = ctx.dirname })[1] then
              return {}
            end
            return { '--indent-type', 'Spaces', '--indent-width', '2', '--quote-style', 'AutoPreferSingle' }
          end,
        },
      },
      -- no formatter for the filetype -> use LSP formatting if attached, else skip
      default_format_opts = { lsp_format = 'fallback' },
      format_on_save = { timeout_ms = 1000, lsp_format = 'fallback' },
    },
  },

  -- ── Git ───────────────────────────────────────────────────
  -- Gitsigns: gutter signs per hunk (working tree vs index)
  {
    'lewis6991/gitsigns.nvim',
    config = function()
      require('gitsigns').setup({
        signs_staged_enable = true, -- staged hunks get their own (dimmer) signs
        on_attach = function(bufnr)
          local gs = require('gitsigns')
          local function map(mode, lhs, rhs, desc)
            vim.keymap.set(mode, lhs, rhs, { buffer = bufnr, desc = desc })
          end
          -- ]c / [c -> next/prev hunk (native ]c still works inside diff views)
          map('n', ']c', function()
            if vim.wo.diff then vim.cmd.normal({ ']c', bang = true }) else gs.nav_hunk('next') end
          end, 'Next hunk')
          map('n', '[c', function()
            if vim.wo.diff then vim.cmd.normal({ '[c', bang = true }) else gs.nav_hunk('prev') end
          end, 'Prev hunk')
          map('n', '<leader>gp', gs.preview_hunk, 'Preview hunk')
          -- stage = git add -p (one hunk); in visual mode only the selected lines
          map('n', '<leader>gs', gs.stage_hunk, 'Stage hunk')
          map('v', '<leader>gs', function()
            gs.stage_hunk({ vim.fn.line('.'), vim.fn.line('v') })
          end, 'Stage lines')
          map('n', '<leader>gr', gs.reset_hunk, 'Reset hunk')
          -- undo the last stage in this session (<leader>gs on a staged sign also unstages)
          map('n', '<leader>gu', gs.undo_stage_hunk, 'Undo stage hunk')
          map('n', '<leader>gb', function() gs.blame_line({ full = true }) end, 'Blame line')
        end,
      })
    end,
  },

  -- Diffview: side-by-side diffs and history (index vs working tree, branches)
  {
    'sindrets/diffview.nvim',
    dependencies = { 'nvim-tree/nvim-web-devicons' }, -- file icons (Nerd Font glyphs)
    config = function()
      require('diffview').setup({})
      -- space g d -> what changed: unstaged (tree vs index) + staged (index vs HEAD)
      vim.keymap.set('n', '<leader>gd', '<cmd>DiffviewOpen<cr>', { desc = 'Diff (tree/index/HEAD)' })
      vim.keymap.set('n', '<leader>gh', function()
        -- from the tree (or another non-file window), use the last file window
        if vim.bo.buftype ~= '' then vim.cmd('wincmd p') end
        vim.cmd('DiffviewFileHistory %')
      end, { desc = 'File history' })
      vim.keymap.set('n', '<leader>gH', '<cmd>DiffviewFileHistory<cr>', { desc = 'Repo history' })
      vim.keymap.set('n', '<leader>gq', '<cmd>DiffviewClose<cr>', { desc = 'Close diffview' })
    end,
  },

  -- Neo-tree: file tree sidebar with per-file git status
  {
    'nvim-neo-tree/neo-tree.nvim',
    branch = 'v3.x',
    dependencies = { 'nvim-lua/plenary.nvim', 'MunifTanjim/nui.nvim', 'nvim-tree/nvim-web-devicons' },
    config = function()
      require('neo-tree').setup({
        default_component_configs = {
          -- letters like `git status --short`; ● = in index (staged), ○ = working tree only
          git_status = {
            symbols = {
              added = 'A', modified = 'M', deleted = 'D', renamed = 'R',
              untracked = '?', ignored = '!', conflict = 'U',
              staged = '●', unstaged = '○',
            },
          },
        },
        filesystem = {
          follow_current_file = { enabled = true }, -- reveal the open file
        },
      })
      vim.keymap.set('n', '<leader>e', '<cmd>Neotree toggle reveal left<cr>', { desc = 'File tree' })
      -- space g t -> only changed files, like `git status`
      vim.keymap.set('n', '<leader>gt', '<cmd>Neotree toggle git_status left<cr>', { desc = 'Git status tree' })
    end,
  },
}, {
  ui = { border = 'rounded' },
})

-- ── LSP ─────────────────────────────────────────────────────
-- Built-in defaults (0.11+): K hover, grn rename, gra code action,
-- grr references, gri implementation, [d / ]d next/prev diagnostic.
vim.lsp.config('lua_ls', {
  -- lua_ls gives no diagnostics without a root, so a lone file
  -- (e.g. ~/.config/nvim/init.lua) uses its own folder. Never all of $HOME.
  root_dir = function(bufnr, on_dir)
    local root = vim.fs.root(bufnr, vim.lsp.config.lua_ls.root_markers or { '.git' })
    local name = vim.api.nvim_buf_get_name(bufnr)
    if not root and name ~= '' then
      local dir = vim.fs.dirname(name)
      if vim.uv.fs_realpath(dir) ~= vim.uv.fs_realpath(vim.env.HOME) then root = dir end
    end
    on_dir(root)
  end,
  settings = {
    Lua = {
      runtime = { version = 'LuaJIT' },
      diagnostics = { globals = { 'vim' } },
      -- know the Neovim API so gd / K work on vim.*
      workspace = { library = { vim.env.VIMRUNTIME }, checkThirdParty = false },
    },
  },
})

vim.api.nvim_create_autocmd('LspAttach', {
  callback = function(ev)
    local client = vim.lsp.get_client_by_id(ev.data.client_id)
    vim.keymap.set('n', 'gd', vim.lsp.buf.definition, { buffer = ev.buf, desc = 'Go to definition' })
    -- manual completion only: no popup while typing
    -- <C-x><C-o> always works; macOS grabs <C-Space> for input source by default
    if client and client:supports_method('textDocument/completion') then
      vim.lsp.completion.enable(true, client.id, ev.buf, { autotrigger = false })
      vim.keymap.set('i', '<C-Space>', vim.lsp.completion.get, { buffer = ev.buf, desc = 'LSP completion' })
    end
  end,
})

-- ── Diagnostics ─────────────────────────────────────────────
vim.diagnostic.config({
  virtual_text = true,       -- message at end of line
  signs = true,              -- marker in the sign column
  severity_sort = true,
  float = { border = 'rounded' },
})
