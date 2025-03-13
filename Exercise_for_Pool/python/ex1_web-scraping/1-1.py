#!/usr/bin/python
# -*- coding: utf-8 -*-
"""ぐるなび店舗情報収集スクリプト

このモジュールは、ぐるなびのウェブサイトから店舗情報を収集します。
指定した件数を検索して、指定した情報をカラムとする CSVファイルを作成します。

"""
import requests                     # HTTPリクエストを送信する
import pandas as pd                 # データ処理・分析
import re                           # 正規表現を扱う
from bs4 import BeautifulSoup       # HTMLのスクレイピング
import os                           # ファイルの存在確認、ロック状態のチェック、パス操作
import json                         # JSONデータの読み書き
import ssl                          # SSL/TLSの処理
import socket                       # ネットワーク通信（IPアドレス取得など）
from urllib.parse import urlparse   # URL解析

# HTTPリクエスト時のヘッダー情報（ぐるなび側のブロックを防ぐためにUser-Agentを指定）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

def is_file_locked(file_path):
    """指定したファイルが開かれているかを確認する。

    Args:
        file_path (str): 確認するファイルのパス。

    Returns:
        bool: ファイルがロックされている場合は True、それ以外は False。
    """
    if not os.path.exists(file_path):
        return False                # ファイルが存在しなければロックされている心配はない

    try:
        with open(file_path, 'a'):  # 追記モードで開いてみる
            return False            # 開けたらロックされていない
    except IOError:
        return True                 # 開けなかったらロックされている

def get_rs_data_member(info_table, data_type):
    """店舗情報テーブルから指定されたデータを取得する汎用関数。

    Args:
        info_table (bs4.element.Tag): 店舗情報のHTMLテーブル。
        data_type (str): 取得する情報のタイプ ('name', 'phone', 'email')

    Returns:
        str: 取得したデータ、存在しない場合は空文字。
    """
    # 店舗名を取得
    if data_type == 'name':
        if info_table.find('p', id='info-name'):
            return info_table.find('p', id='info-name').get_text(strip=True)
        else:
            return ''

    # 電話番号を取得
    elif data_type == 'phone':
        phone_elem = info_table.find('tr', id='info-phone')
        if phone_elem:
            return phone_elem.find('span', class_='number').get_text(strip=True)
        else:
            return ''

    # メールアドレスを取得
    elif data_type == 'email':
        # メールアドレスの正規表現
        email_pattern = r'mailto:.*'
        email_elem = info_table.find(href=re.compile(email_pattern))
        if email_elem:
            return email_elem.get('href').replace('mailto:', '')
        else:
            return ''

    # 無効な data_type の場合に備えてエラーメッセージを出す
    if data_type not in ['name', 'phone', 'email']:
        raise ValueError(f"Invalid data_type: {data_type}")

    # 要素が見つからなければ空文字を返す
    return ''

def get_address(info_table):
    """住所情報（都道府県、市区町村、番地、建物名）を取得する。

    Args:
        info_table (bs4.element.Tag): 店舗情報のHTMLテーブル。

    Returns:
        dict: 住所情報 {'都道府県': str, '市区町村': str, '番地': str, '建物名': str}
    """
    # 各種変数を用意（エラー時には空文字を返す）
    region, prefecture, city, street, locality = '', '', '', '', ''
    # 住所・建物名の情報をもつ要素を取得する
    adr_slink = info_table.find('p', class_='adr slink')
    if adr_slink:
        # 住所を取得
        region_elem = adr_slink.find('span', class_='region')
        region = region_elem.get_text(strip=True) if region_elem else ''

        # 住所の正規表現（都道府県、市区町村、番地 の分割）
            # address_pattern = re.compile(r'(...??[都道府県])(.+?[市区町村].+?)(\d.*)')
        prefecture_pattern = r'(...??[都道府県])'
        city_pattern = \
            r'((?:旭川|伊達|石狩|盛岡|奥州|田村|南相馬|那須塩原|東村山|武蔵村山|羽村|十日町|上越|富山|野々市|大町|蒲郡|四日市|姫路|大和郡山|廿日市|下松|岩国|田川|大村)市.+?|' \
            r'.+?郡(?:玉村|大町|.+?)[町村].+?|' \
            r'.+?市.+?区|.+?[市区町村].+?)'
        street_pattern = r'(\d.*)'
        address_pattern = prefecture_pattern + city_pattern + street_pattern
        match = re.compile(address_pattern).match(region)
        if match:
            prefecture, city, street = match.groups()

        # 建物名を取得
        locality_elem = adr_slink.find('span', class_='locality')
        if locality_elem:
            locality = locality_elem.get_text(strip=True)

    return {
        '都道府県': prefecture,
        '市区町村': city,
        '番地': street,
        '建物名': locality
    }

def get_url(info_table, soup):
    """店舗公式URLを取得し、リダイレクト後の最終URLを返す。

    Args:
        info_table (bs4.element.Tag): 店舗情報のHTMLテーブル。
        soup (BeautifulSoup): 店舗ページ全体のBeautifulSoupオブジェクト。

    Returns:
        str or None: 実際にブラウザで開いたときの最終的なURL。取得できない場合は None。
    """
    # 店舗公式URLの情報をもつ要素を取得する
    link_elem = info_table.find('a', class_='url go-off')
    url = None
    if link_elem:
        # カスタムデータ属性 'data-o' から値を取得（JSON 形式の文字列が格納されている）
        try:
            data_o = link_elem.get('data-o')
            if data_o:
                # JSONデコード（&quot; を " に変換）
                data = json.loads(data_o)
                # プロトコルとドメインを結合
                url = f"{data['b']}://{data['a']}"
        # デコードエラー時は None を返す
        except (json.JSONDecodeError, KeyError):
            return None

    # 代替手段でURLを取得（'data-o' から取得できなかった場合）
    if not url:
        # IDが 'sv-site' の <ul> 要素を探す（代替URLが含まれている可能性がある）
        sv_site = soup.find('ul', id='sv-site')
        if sv_site:
            # クラス 'sv-of double' を持つ <a> 要素を探す
            link_elem = sv_site.find('a', class_='sv-of double')
            if link_elem:
                # href属性（URL）を取得し、返す
                url = link_elem.get('href')

    # 実際のブラウザで開いたときの最終的なURLを取得する
    try:
        # 明示的に None や "" の場合を除外
        if not url:
            return None
        # 指定したURLに GET リクエストを送り、ブラウザのように振る舞い、リダイレクトも自動追従する
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        # リダイレクト後の最終URL
        return response.url
    except requests.RequestException:
        # エラー時は元のURLを返す
        return url

def check_ssl_status(url):
    """URL の SSL 証明書を検証し、結果を data_dict に格納する。

    Args:
        data_dict (dict): 店舗情報を格納する辞書。'URL' キーを含む。

    Returns:
        None: data_dict に 'SSL' キーを追加・更新する。
    """
    if url:
        has_ssl, message = check_ssl_certificate(url)
        print(f"URL: {url} -> {message}")
        return has_ssl

def check_ssl_certificate(url):
    """指定されたURLのSSL証明書をチェックする。

    Args:
        url (str): チェックする対象のURL。

    Returns:
        tuple: (bool, str) のタプル。
            - True と "SSL証明書あり" : 証明書が存在する場合。
            - False と エラーメッセージ : 証明書が存在しない、またはエラーが発生した場合。
    """
    # テスト用URL (NOT SECURE!) -> http://www.hakarime.jp/
    parsed_url = urlparse(url)      # URLを解析し、スキーム・ドメイン・パスなどを取得
    hostname = parsed_url.netloc    # ドメイン名を取得

    # ホスト名が取得できない場合は無効なURLと判断
    if not hostname:
        return False, "Invalid URL"

    # デフォルトのSSLコンテキストを作成
    context = ssl.create_default_context()
    try:
        # 指定したホストに対してポート443（HTTPS）でソケット接続を確立
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            # SSL/TLSでソケットをラップし、ホスト名を検証
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # 証明書を取得できた場合、証明書の有効性もチェック
                cert = ssock.getpeercert()
                if cert:
                    # ここで証明書の有効性チェック（例: 有効期限の確認）
                    return True, "SSL Available"
    except ssl.SSLError as e:
        return False, f"SSL Error: {e}"
    except socket.timeout:
        return False, "Conn Timeout"
    except Exception as e:
        return False, f"SSL Not Available ({e})"

def get_rs_data(rs_url):
    """ぐるなびの店舗ページをスクレイピングし、店舗情報を取得する。

    Args:
        rs_url (str): 店舗ページのURL。

    Returns:
        dict: 取得した店舗情報を含む辞書。
            - '店舗名' (str): 店舗名
            - '電話番号' (str): 電話番号
            - 'メールアドレス' (str): メールアドレス
            - '都道府県' (str): 都道府県
            - '市区町村' (str): 市区町村
            - '番地' (str): 番地
            - '建物名' (str): 建物名
            - 'URL' (str): 店舗の公式URL
            - 'SSL' (bool): 店舗サイトのSSL対応状況
    """
    # デフォルトのデータ辞書（エラー時の初期値）
    data_dict = {
        '店舗名': '',
        '電話番号': '',
        'メールアドレス': '',
        '都道府県': '',
        '市区町村': '',
        '番地': '',
        '建物名': '',
        'URL': '',
        'SSL': False
    }

    try:
        # HTTPリクエストを送信
        response = requests.get(rs_url, headers=headers)
        if response.status_code != 200:
            return data_dict  # エラーレスポンス時はデフォルト値を返す

        # HTMLを解析
        soup = BeautifulSoup(response.content.decode("utf-8", "ignore"), "html.parser")

        # 店舗情報テーブルを取得
        info_table = soup.find('table', class_='basic-table')
        if not info_table:
            return data_dict  # テーブルがない場合もデフォルト値を返す

        # データ辞書に取得した値を格納
        data_dict['店舗名'] = get_rs_data_member(info_table, 'name')
        data_dict['電話番号'] = get_rs_data_member(info_table, 'phone')
        data_dict['メールアドレス'] = get_rs_data_member(info_table, 'email')
        data_dict.update(get_address(info_table))
        data_dict['URL'] = get_url(info_table, soup)
        data_dict['SSL'] = check_ssl_status(data_dict['URL'])

    except requests.exceptions.RequestException as e:
        # ネットワークエラー時の処理
        print(f"Request error: {e}")

    return data_dict

def main():
    """
    ぐるなびの店舗情報をスクレイピングし、CSVファイルに出力する。
    指定された件数分の店舗情報を取得し、"1-1.csv" に保存する。

    Specification:
        - ぐるなびの検索結果ページを順に巡回し、店舗URLを取得。
        - 各店舗ページの詳細情報を取得し、リストに格納。
        - 取得データをPandasのデータフレームに変換し、CSVとして保存。

    Raises:
        requests.exceptions.RequestException: HTTPリクエストのエラーが発生した場合。
    """
    # 出力するファイル名を指定
    file_name = '1-1.csv'
    # ファイルが開かれているかチェック
    if is_file_locked(file_name):
        print(f"Error: {file_name} is open. Please close it and try again.")
        return  # 処理を中断

    print('Processing start')   # 処理開始
    data = []                   # 店舗情報を格納するリスト
    pg_count = 1                # 現在の検索ページ番号
    rs_count = 0                # 取得した店舗数
    rs_demand = 50              # 取得したい店舗数（目標件数）

    # 検索結果のURLのベース（ページ番号を変えて巡回する）
    base_url = "https://r.gnavi.co.jp/area/jp/rs/?p="

    # 目標の件数を取得するまでループ
    while rs_count < rs_demand:
        # 検索結果ページのURLを生成
        search_url = base_url + str(pg_count)

        # HTTPリクエストを送信
        response = requests.get(search_url, headers=headers)

        # ページの取得に失敗した場合
        if response.status_code != 200:
            print("Page loading failed.")
            return  # 処理を中断

        # HTML解析
        soup = BeautifulSoup(response.text, 'html.parser')

        # 店舗のURLを格納するリスト
        rs_links = []

        # 店舗ページのリンクを取得
        for a in soup.select('a.style_titleLink__oiHVJ'):
            href = a.get('href')
            if href:
                # 絶対URLか相対URLかを判定し、完全なURLを生成
                rs_links.append(href if href.startswith("http") else search_url + href)

        # 残りの必要件数分だけ取得（上限を超えないように）
        rs_links = rs_links[:rs_demand - rs_count]

        # 各店舗の詳細情報を取得
        for link in rs_links:
            rs_data = get_rs_data(link) # 店舗情報を取得する関数
            if rs_data:
                data.append(rs_data)    # 取得したデータをリストに追加
                rs_count += 1           # 取得した店舗数をカウント
                print('Processing... ' + str(rs_count))

        # 30件ごとに次の検索ページに移動
        if rs_count % 30 == 0:
            pg_count += 1

    # 取得データをPandasのデータフレームに変換
    df = pd.DataFrame(data)

    # CSVファイルとして保存
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    print(file_name + " has been created!")

if __name__ == "__main__":
    main()  # スクリプトが直接実行される場合に main() 関数を呼び出す