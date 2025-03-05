-- すべてのホスト ('%') から接続できる MySQL ユーザーを作成
DROP USER IF EXISTS 'user'@'%';
CREATE USER 'user'@'%' IDENTIFIED BY 'user_password';

-- ユーザーに ex2 データベースへの全権限を付与（セキュリティ対策）
GRANT ALL PRIVILEGES ON ex2.* TO 'user'@'%' WITH GRANT OPTION;

-- 権限を反映
FLUSH PRIVILEGES;

-- 文字コードを適用
SET NAMES utf8mb4;

-- データベースが存在しない場合は作成
CREATE DATABASE IF NOT EXISTS ex2
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ex2 を使用
USE ex2;

-- ex2_2 テーブルを作成（主キーとして ID を追加）
CREATE TABLE IF NOT EXISTS ex2_2 (
    ID BIGINT AUTO_INCREMENT PRIMARY KEY,
    `店舗名` VARCHAR(255),
    `電話番号` VARCHAR(30),
    `メールアドレス` VARCHAR(255),
    `都道府県` VARCHAR(255),
    `市区町村` VARCHAR(255),
    `番地` VARCHAR(255),
    `建物名` VARCHAR(255),
    `URL` VARCHAR(255),
    `SSL` TINYINT(1) DEFAULT 0
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;