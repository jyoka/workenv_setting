#!/bin/sh
# yazi から HTML ファイルを live-server で開く
# ファイルのあるフォルダを配信ルートにして、そのファイルをブラウザで開く
LIVE_SERVER=$(command -v live-server)
if [ -z "$LIVE_SERVER" ]; then
	for p in /opt/homebrew/bin/live-server "$HOME/.local/bin/live-server" "$HOME/.local/node/bin/live-server"; do
		[ -x "$p" ] && LIVE_SERVER="$p" && break
	done
fi
if [ -z "$LIVE_SERVER" ]; then
	echo "live-server が見つかりません(npm install -g live-server で導入してください)"
	echo "Enter キーで yazi に戻ります"
	read -r _
	exit 1
fi
cd "$(dirname "$1")" || exit 1
echo "live-server を起動します: $(basename "$1")"
echo "終了するには Ctrl+C(yazi に戻ります)"
exec "$LIVE_SERVER" --open="$(basename "$1")"
