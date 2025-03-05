#!/usr/bin/python
# -*- coding: utf-8 -*-
"""ぐるなび店舗情報収集スクリプト

このモジュールは、ぐるなびのウェブサイトから店舗情報を収集します。

"""
import pandas as pd                     # データ処理・分析
import re                               # 正規表現を扱う
import os                               # OS関連: 環境変数を扱う際に使用
import json                             # JSONデータの読み書き
import ssl                              # SSL/TLSの処理
import socket                           # ネットワーク通信（IPアドレス取得など）
from urllib.parse import urlparse       # URL解析
from selenium import webdriver                                      # Selenium WebDriverをインポート
from selenium.webdriver.common.by import By  			            # WebElementを指定するためのByをインポート
from selenium.webdriver.support import expected_conditions as EC    # 特定の条件が満たされるのを待つためのモジュール
from selenium.webdriver.support.ui import WebDriverWait             # WebDriverの待機処理を提供するモジュール
from selenium.webdriver.chrome.service import Service  		        # ChromeDriverのサービスをインポート
from webdriver_manager.chrome import ChromeDriverManager	        # ChromeDriverの自動インストール

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

def set_webdriver():
    """Selenium 用の Chrome WebDriver を設定して返す。

    Returns:
        selenium.webdriver.Chrome: 設定済みの Chrome WebDriver インスタンス。

    """
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    return webdriver.Chrome(service=service, options=options)

def get_rs_data_member(driver, info_table, data_type):
    """指定された種類の店舗情報を取得する。

    Args:
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。
        info_table (selenium.webdriver.remote.webelement.WebElement): 店舗情報を含むテーブルの WebElement。
        data_type (str): 取得するデータの種類 ('name', 'phone', 'email' のいずれか)。

    Returns:
        str: 取得したデータの文字列。該当する情報がない場合は空文字を返す。

    Raises:
        ValueError: `data_type` が 'name', 'phone', 'email' 以外の場合。

    Notes:
        - `name`: ID が 'info-name' の要素から店舗名を取得する。
        - `phone`: ID が 'info-phone' の要素内のクラス 'number' から電話番号を取得する。
        - `email`: `mailto:` リンクを検索し、最初に見つかったメールアドレスを取得する。
        - 要素が見つからない場合は空文字を返す。
    """
    # 店舗名を取得
    if data_type == 'name':
        name_elem = info_table.find_element(By.ID, 'info-name')
        if name_elem:
            return name_elem.text.strip()
        else:
            return ''

    # 電話番号を取得
    elif data_type == 'phone':
        phone_elem = info_table.find_element(By.ID, 'info-phone')
        phone_number = phone_elem.find_element(By.CLASS_NAME, 'number')
        if phone_number:
            return phone_number.text.strip()
        else:
            return ''

    # メールアドレスを取得
    elif data_type == 'email':
        try:
            email_elems = info_table.find_elements(By.XPATH, "//a[contains(@href, 'mailto:')]")
            for email_elem in email_elems:
                href = email_elem.get_attribute('href')
                if href and href.startswith('mailto:'):
                    return href.replace('mailto:', '')
            return ''
        except Exception:
            return ''

    # 無効な data_type の場合に備えてエラーメッセージを出す
    if data_type not in ['name', 'phone', 'email']:
        raise ValueError(f"Invalid data_type: {data_type}")

    # 要素が見つからなければ空文字を返す
    return ''

def get_address(driver, info_table):
    """住所情報（都道府県、市区町村、番地、建物名）を取得する。

    Args:
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。
        info_table (selenium.webdriver.remote.webelement.WebElement): 店舗情報を含むテーブルの WebElement。

    Returns:
        dict: 住所情報を格納した辞書。キーは以下のとおり。
            - '都道府県' (str): 抽出された都道府県。該当しない場合は空文字。
            - '市区町村' (str): 抽出された市区町村。該当しない場合は空文字。
            - '番地' (str): 抽出された番地。該当しない場合は空文字。
            - '建物名' (str): 抽出された建物名。該当しない場合は空文字。

    Notes:
        - `adr.slink` クラスの要素から住所情報を取得する。
        - 正規表現を使用して `都道府県`, `市区町村`, `番地` を分割する。
        - `locality` クラスの要素が存在する場合、建物名を取得する。
        - 該当する要素が見つからない場合、それぞれの値は空文字となる。

    """
    # 各種変数を用意（エラー時には空文字を返す）
    region, prefecture, city, street, locality = '', '', '', '', ''

    # 住所・建物名の情報を持つ要素を取得
    adr_slink = info_table.find_element(By.CLASS_NAME, 'adr.slink')
    if adr_slink:
        # 住所を取得
        region_elem = adr_slink.find_element(By.CLASS_NAME, 'region')
        region = region_elem.text.strip()

        # 住所の正規表現（都道府県、市区町村、番地 の分割）
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
            print(street)
        # 建物名を取得
        try:
            locality_elem = adr_slink.find_element(By.CLASS_NAME, 'locality')
            if locality_elem:
                locality = locality_elem.text.strip()
        except Exception:
            print("Error in extracting locality")
            pass

    return {
        '都道府県': prefecture,
        '市区町村': city,
        '番地': street,
        '建物名': locality
    }

def get_url(driver, info_table):
    """店舗公式URLを取得する。

    取得方法は以下の 2 段階で行う。
    1. `data-o` 属性に格納されている JSON 形式のデータを解析し、URL を構築する。
    2. `data-o` から取得できない場合、代替手段として `sv-site` ID 内のリンクを取得する。

    Args:
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。
        info_table (selenium.webdriver.remote.webelement.WebElement): 店舗情報を含むテーブルの WebElement。

    Returns:
        str or None: 店舗公式URL。取得できない場合は None。

    Notes:
        - `data-o` は JSON 形式で `{ "b": "https", "a": "example.com" }` のように格納されている。
        - `data-o` から取得できなかった場合、 `sv-site` ID の要素内にある `sv-of double` クラスのリンクを代替として使用する。
        - 例外発生時には `None` を返し、エラーメッセージを出力する。

    """
    # 店舗公式URLの情報をもつ要素を取得する
    try:
        link_elem = info_table.find_element(By.CLASS_NAME, 'url.go-off')
        if link_elem:
            # カスタムデータ属性 'data-o' から値を取得（JSON 形式の文字列が格納されている）
            data_o = link_elem.get_attribute('data-o')
            if data_o:
                data = json.loads(data_o)           # JSONデコード（&quot; を " に変換）
                return f"{data['b']}://{data['a']}" # プロトコルとドメインを結合
    except Exception:
        print("No official URL. Proceed to alternative method.")
        pass  # エラーが発生した場合は、代替手段に進む

    # 代替手段でURLを取得（'data-o' から取得できなかった場合）
    try:
        sv_site = driver.find_element(By.ID, 'sv-site')
        if sv_site:
            link_elem = sv_site.find_element(By.CLASS_NAME, 'sv-of.double')
            if link_elem:
                return link_elem.get_attribute('href')
    except Exception as e:
        print(f"Error in extracting URL: {e}")
        pass  # エラーが発生した場合は、Noneを返す

    # どの手段でも取得できなかった場合
    return None

def check_ssl_status(url):
    """URL の SSL 証明書を検証し、その結果を返す。

    Args:
        url (str): SSL 証明書を検証したい URL。

    Returns:
        bool: URL が SSL 証明書を持っていれば `True`、そうでなければ `False` を返す。

    Notes:
        - SSL 証明書の検証は `check_ssl_certificate` 関数を利用して行う。
        - URL が指定されていない場合は `False` を返す。

    """
    if url:
        has_ssl, message = check_ssl_certificate(url)
        print(f"URL: {url} -> {message}")
    else:
        has_ssl = False

    return has_ssl

def check_ssl_certificate(url):
    """指定された URL の SSL 証明書を検証し、その結果を返す。

    Args:
        url (str): SSL 証明書を検証したい URL。

    Returns:
        tuple:  SSL 証明書が有効であれば `(True, 'SSL Available')` を返し、
                無効または接続に失敗した場合は `(False, エラーメッセージ)` を返す。

    Exceptions:
        - socket.timeout: 接続タイムアウトが発生した場合。
        - ssl.SSLError: SSL/TLS 接続エラーが発生した場合。
        - その他の例外: その他のエラーが発生した場合。

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

def get_rs_data(driver, rs_url):
    """指定された店舗ページから店舗情報を取得する。
    Selenium を用いて店舗ページを開き、テーブルから必要な情報を抽出する。
    取得できなかった場合は、デフォルト値を持つ辞書を返す。

    Args:
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。
        rs_url (str): 店舗ページの URL。

    Returns:
        dict: 店舗情報を格納した辞書。
            - '店舗名' (str): 店舗の名前。
            - '電話番号' (str): 店舗の電話番号。
            - 'メールアドレス' (str): 店舗のメールアドレス。
            - '都道府県' (str): 店舗の所在地（都道府県）。
            - '市区町村' (str): 店舗の所在地（市区町村）。
            - '番地' (str): 店舗の所在地（番地）。
            - '建物名' (str): 店舗の所在地（建物名）。
            - 'URL' (str): 店舗のウェブサイト URL。
            - 'SSL' (bool): URL が HTTPS かどうかを判定した結果。

    Raises:
        TimeoutException: 指定された要素が一定時間内に読み込まれなかった場合。

    Notes:
        - 店舗情報はテーブル要素 (.basic-table) から取得する。
        - `get_rs_data_member`, `get_address`, `get_url`, `check_ssl_status` を使用して情報を取得する。
        - ページに情報がない場合はデフォルトの空データを返す。

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

    # Seleniumを使ってページを開く
    driver.get(rs_url)

    # ページの読み込みを待機
    driver.implicitly_wait(3)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'basic-table')))

    # 店舗情報テーブルを取得
    info_table = driver.find_element(By.CLASS_NAME, 'basic-table')
    if not info_table:
        return data_dict  # テーブルがない場合もデフォルト値を返す

    # データ辞書に取得した値を格納
    data_dict['店舗名'] = get_rs_data_member(driver, info_table, 'name')
    data_dict['電話番号'] = get_rs_data_member(driver, info_table, 'phone')
    data_dict['メールアドレス'] = get_rs_data_member(driver, info_table, 'email')
    data_dict.update(get_address(driver, info_table))
    data_dict['URL'] = get_url(driver, info_table)
    data_dict['SSL'] = check_ssl_status(data_dict['URL'])

    return data_dict


def loop_rs_links(data, driver, rs_links, rs_count, rs_demand):
    """店舗ページの URL を巡回し、店舗情報を取得してリストに追加する。

    Args:
        data (list): 取得した店舗情報を格納するリスト。
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。
        rs_links (list): 店舗ページの URL のリスト。
        rs_count (int): 取得済みの店舗数。
        rs_demand (int): 目標取得件数。

    Returns:
        tuple: 更新後の `data` (list) と `rs_count` (int) を含むタプル。

    Notes:
        - `rs_demand` の桁数に応じてゼロ埋めした店舗番号を表示する。
        - 各店舗の詳細情報を取得し、リストに追加する。

    """
    rs_digits = len(str(rs_demand))             # rs_demandの桁数 (ゼロ埋め用)

    for link in rs_links:
        id = rs_count + 1
        num = str(id).zfill(rs_digits)
        print(f'\nProcessing {num} -> {link}')
        rs_data = get_rs_data(driver, link)     # 店舗情報を取得する関数
        if rs_data:
            data.append(rs_data)                # 取得したデータをリストに追加
            rs_count += 1                       # 取得した店舗数をカウント

    return data, rs_count

def get_rs_links(driver):
    """検索結果ページから店舗ページのURLを取得してリストとして返す。

    Args:
        driver (selenium.webdriver.Chrome): Selenium の WebDriver インスタンス。

    Returns:
        list: 取得した店舗ページの URL のリスト。

    """
    rs_links = []
    elements = driver.find_elements(By.CSS_SELECTOR, 'a.style_titleLink__oiHVJ')
    for element in elements:
        href = element.get_attribute('href')
        if href:
            rs_links.append(href)   # 絶対URLか相対URLかを判定し、完全なURLを生成

    return rs_links

def main():
    """ぐるなびの店舗情報を取得し、CSVファイルに保存する。
    1. Selenium を用いて「ぐるなび」の検索ページを巡回し、各店舗の詳細情報を取得する。
    2. 取得したデータは Pandas のデータフレームに変換し、CSVファイルとして保存する。

    Raises:
        Exception: WebDriver の起動やページの取得に失敗した場合に発生する可能性がある。

    Notes:
        - 目標件数 (rs_demand) は 50 に設定されている。
        - 検索結果の 30 件ごとに次のページへ移動する。
        - 取得した情報を '2-2.csv' というファイルに保存する。
        - 既にファイルが開かれている場合はエラーメッセージを出力して処理を中断する。

    """
    # 出力するファイル名を指定
    file_name = '1-2.csv'
    # ファイルが開かれているかチェック
    if is_file_locked(file_name):
        print(f"Error: {file_name} is open. Please close it and try again.")
        return  # 処理を中断

    data = []                   # 店舗情報を格納するリスト
    pg_count = 1                # 現在の検索ページ番号
    rs_count = 0                # 取得した店舗数
    rs_demand = 50              # 取得したい店舗数（目標件数）
    rs_links = []               # 店舗のURLを格納するリスト
    driver = set_webdriver()    # SeleniumのChromeドライバーオプションを設定する関数

    # 検索結果のURLのベース（ページ番号を変えて巡回する）
    base_url = "https://r.gnavi.co.jp/area/jp/rs/?p="

    # 目標の件数を取得するまでループ
    while rs_count < rs_demand:
        search_url = base_url + str(pg_count)       # 検索結果ページのURLを生成
        driver.get(search_url)                      # Seleniumでページを開く
        driver.implicitly_wait(3)                   # ページが読み込まれるのを待機
        rs_links = get_rs_links(driver)             # 店舗ページのリンクを取得する関数
        rs_links = rs_links[:rs_demand - rs_count]  # 残りの必要件数分だけ取得（上限を超えないように）

        # 各店舗の詳細情報を取得
        data, rs_count = loop_rs_links(data, driver, rs_links, rs_count, rs_demand)

        # 30件ごとに次の検索ページに移動
        if rs_count % 30 == 0:
            pg_count += 1

    # ドライバーを閉じる
    driver.quit()

    # 取得データをPandasのデータフレームに変換
    df = pd.DataFrame(data)

    # CSVファイルとして保存
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    print(file_name + " has been created!")

if __name__ == "__main__":
    print('Processing start')
    main()  # スクリプトが直接実行される場合に main() 関数を呼び出す