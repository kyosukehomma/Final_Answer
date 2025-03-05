# ベースイメージ
FROM ubuntu:20.04

# 非対話モードを設定
ENV DEBIAN_FRONTEND=noninteractive

# 日本語ロケールをインストール
RUN apt-get update && \
    apt-get install -y language-pack-ja-base language-pack-ja locales && \
    sed -i -e 's/# \(C.UTF-8\)/\1/' /etc/locale.gen && \
    locale-gen ja_JP.UTF-8 && \
    update-locale LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

# 環境変数を設定（コンテナ全体に適用）
ENV LANG=ja_JP.UTF-8 \
    LC_CTYPE=ja_JP.UTF-8 \
    LC_ALL=ja_JP.UTF-8

# ロケール設定を /etc/default/locale に反映
RUN echo "LANG=C.UTF-8" > /etc/default/locale && \
    echo 'export LC_CTYPE=C.UTF-8' >> /etc/default/locale && \
    echo "LC_ALL=C.UTF-8" >> /etc/default/locale

# タイムゾーンを設定する
RUN ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime

# 必要なパッケージをインストール
RUN apt-get update -o Acquire::http::Timeout=60 > /dev/null && \
    apt-get install -y \
        python3.8 \
        python3-pip \
        mysql-server \
        curl \
        unzip \
        tzdata \
        libnss3 \
        libgdk-pixbuf2.0-0 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        wget \
        gnupg2 \
        ca-certificates \
        # Google Chromeの依存関係
        fonts-liberation \
        libasound2 \
        libvulkan1 \
        xdg-utils \
        # 他に必要なパッケージを追加
        libxss1 \
        libappindicator3-1 \
        libindicator3-7 > /dev/null &&\
    apt-get clean

# Google Chromeをインストール
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb && \
    apt-get install -f -y && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get clean

# ChromeDriverをダウンロードして配置
RUN mkdir -p /usr/local/bin/chromedriver && \
    curl -sS https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip -o /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver/chromedriver

# MySQLのセットアップ
RUN mkdir -p /docker-entrypoint-initdb.d
COPY mysql-init.sql /docker-entrypoint-initdb.d/
COPY my.cnf /etc/mysql/my.cnf

# MySQLの起動前に環境変数を適用
RUN echo 'export LANG=C.UTF-8' >> /etc/profile && \
    echo 'export LC_CTYPE=C.UTF-8' >> /etc/profile && \
    echo 'export LC_ALL=C.UTF-8' >> /etc/profile

# Pythonの依存関係をインストール
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip3 install --no-cache-dir -r requirements.txt

# webdriver-manager を最新バージョンに更新
RUN pip install -U webdriver-manager

# スクリプトをコンテナにコピー
COPY 2-2.py /app/2-2.py

# MySQLとPythonスクリプトの起動を制御するエントリーポイントスクリプト
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# コンテナ起動時の実行コマンド
ENTRYPOINT ["/entrypoint.sh"]