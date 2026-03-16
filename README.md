# SUUMO 賃貸チェッカー

SUUMO の賃貸検索結果をスクレイピングし、新着物件を Slack に通知する。

## 検索条件

- エリア: 埼玉県春日部市
- 家賃: 8万円以下
- 間取り: 2LDK / 3K / 3DK / 3LDK
- 駅徒歩: 10分以内

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

```bash
# ローカル実行（Slack通知なし）
python suumo_checker.py

# Slack通知あり
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... python suumo_checker.py
```

## 仕組み

1. SUUMO の検索結果ページを全ページ取得
2. 各物件の部屋情報を解析
3. `state.json` と比較して新着物件を検出
4. 新着があれば Slack に Block Kit で通知
5. 現在の物件リストを `state.json` に保存

## GitHub Actions

毎時 0分・30分に自動実行。`SLACK_WEBHOOK_URL` を GitHub Secrets に設定すること。

## 検索条件の変更

`suumo_checker.py` 冒頭の `SEARCH_URL` と `SEARCH_PARAMS` を変更する。

### 間取りコード（md パラメータ）

| コード | 間取り |
|--------|--------|
| 01 | ワンルーム |
| 02 | 1K |
| 03 | 1DK |
| 04 | 1LDK |
| 05 | 2K |
| 06 | 2DK |
| 07 | 2LDK |
| 08 | 3K |
| 09 | 3DK |
| 10 | 3LDK |
