# ~/.zshrc に追記する内容(このファイルの中身をコピーして貼り付ける)
# どの Mac でも動くよう、インストール場所を自動判定する書き方にしてある

# エディタ設定: 「エディタで開く」系ツール全般で micro を使う
export EDITOR=micro
export VISUAL=micro

# コマンド入力支援
# 履歴からの自動補完(灰色で候補表示、→キーで確定)
for _f in /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh \
          "$HOME/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh"; do
  [ -f "$_f" ] && source "$_f" && break
done
unset _f

# fzf 連携: Ctrl+R 履歴あいまい検索 / Ctrl+T ファイル名挿入 / Alt+C フォルダ移動
command -v fzf >/dev/null 2>&1 && source <(fzf --zsh)

# ユーザー権限で入れたバイナリの置き場所(管理者権限のない Mac 用)
export PATH="$HOME/.local/bin:$PATH"
