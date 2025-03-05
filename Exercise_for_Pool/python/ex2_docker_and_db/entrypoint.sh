#!/bin/bash
# 改行コードがLFであるか注意

# エラー発生時には実行停止
set -e

# 環境変数の設定
export LANG=C.UTF-8
export LC_CTYPE=C.UTF-8
export LC_ALL=C.UTF-8

# MySQL をフォアグラウンドで起動
service mysql start

# MySQL の起動を待機
echo "Waiting for MySQL to be ready..."
timeout=60
while ! mysqladmin ping --silent; do
    sleep 1
    timeout=$((timeout - 1))
    if [ $timeout -le 0 ]; then
        echo "MySQL failed to start"
        exit 1
    fi
done
echo "MySQL is up and running"

# 文字コードを UTF-8 に設定（エラーが出ても続行）
mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SET NAMES utf8mb4;" || true

# 2-2.py を実行
echo "Running the Python script..."
if python3 /app/2-2.py; then
    echo "Python script executed successfully"
else
    echo "Python script failed"
    exit 1
fi

# 任意の引数を受け取れるように変更　
exec "$@"