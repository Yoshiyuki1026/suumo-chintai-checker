#!/usr/bin/env python3
"""
SUUMO賃貸物件チェッカー
春日部エリアの2LDK〜3LDK、家賃8万以下、駅徒歩10分以内の物件をチェック
"""

import json
import os
import logging
import time
import re

import requests
from bs4 import BeautifulSoup

# 設定
# せんげん台・一ノ割・武里・大袋、家賃8万以下、2LDK〜3LDK、駅徒歩10分以内
SEARCH_URL = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"
SEARCH_PARAMS = {
    "url": "/chintai/ichiran/FR301FC001/",
    "ar": "030",
    "bs": "040",
    "pc": "30",
    "smk": "",
    "po1": "12",
    "po2": "99",
    "co": ["1", "3", "4"],
    "tc": "0400901",
    "shkr1": "03",
    "shkr2": "03",
    "shkr3": "03",
    "shkr4": "03",
    "cb": "0.0",
    "ct": "8.0",
    "md": ["07", "08", "09", "10"],
    "et": "10",
    "mb": "0",
    "mt": "9999999",
    "cn": "9999999",
    "ra": "011",
    "ek": ["044006230", "044021380", "044022860", "044003110"],
    "rn": "0440",
    "ae": "04401",
}
COOKIE_URL = "https://suumo.jp/chintai/saitama/"
STATE_FILE = "state.json"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def fetch_all_properties(base_url, params):
    """全ページから物件情報を取得する"""
    all_rooms = []
    page = 1

    # Cookie 事前取得（SUUMO の /jj/ エンドポイントはセッション必須）
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.get(COOKIE_URL, timeout=10)

    while True:
        page_params = {**params, "page": str(page)}

        try:
            response = session.get(base_url, params=page_params, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            property_items = soup.select(".cassetteitem")

            if not property_items:
                logger.info(f"ページ {page}: 物件なし。終了。")
                break

            logger.info(f"ページ {page}: {len(property_items)} 件の物件を取得")

            for property_item in property_items:
                rooms = parse_property(property_item)
                all_rooms.extend(rooms)

            # 次ページチェック: .pagination-parts 内に次ページ番号のリンクがあるか
            pager = soup.select(".pagination-parts a")
            has_next = any(a.text.strip() == str(page + 1) for a in pager)
            if not has_next:
                logger.info("最終ページに到達。")
                break

            time.sleep(1)
            page += 1

        except requests.RequestException as e:
            logger.error(f"ページ {page} の取得エラー: {e}")
            break

    logger.info(f"合計 {len(all_rooms)} 件の部屋を取得")
    return all_rooms


def parse_property(property_item):
    """1つの物件ブロックから各部屋の情報を抽出する"""
    rooms = []

    # 物件基本情報
    name_elem = property_item.select_one(".cassetteitem_content-title")
    name = name_elem.text.strip() if name_elem else "名称不明"

    address_elem = property_item.select_one(".cassetteitem_detail-col1")
    address = address_elem.text.strip() if address_elem else "住所不明"

    station_elems = property_item.select(".cassetteitem_detail-text")
    station = station_elems[0].text.strip() if station_elems else "駅情報なし"

    detail_col3 = property_item.select_one(".cassetteitem_detail-col3")
    age = ""
    if detail_col3:
        divs = detail_col3.find_all("div")
        if divs:
            age = divs[0].text.strip()

    # 部屋行を取得
    room_rows = property_item.select("tbody tr.js-cassette_link")

    for row in room_rows:
        tds = row.select("td")
        if len(tds) < 9:
            continue

        # 各部屋の詳細リンクからUIDを取得
        detail_link = row.select_one("a[href*='/chintai/jnc_']")
        if not detail_link:
            continue
        detail_url_path = detail_link["href"]
        uid_match = re.search(r"jnc_(\d+)", detail_url_path)
        if not uid_match:
            continue
        uid = f"jnc_{uid_match.group(1)}"

        # td[2]=階, td[3]=家賃/管理費, td[5]=間取り/面積
        floor = " ".join(tds[2].text.split())

        rent_td = tds[3]
        rent_spans = rent_td.select("span")
        if len(rent_spans) >= 2:
            rent = rent_spans[0].text.strip()
            admin_fee = rent_spans[1].text.strip()
        else:
            rent_text = " ".join(rent_td.text.split())
            rent = rent_text
            admin_fee = ""

        layout_td = tds[5]
        layout_spans = layout_td.select("span")
        if len(layout_spans) >= 2:
            layout = layout_spans[0].text.strip()
            area = layout_spans[1].text.strip()
        else:
            layout_text = " ".join(layout_td.text.split())
            layout = layout_text
            area = ""

        room_data = {
            "name": name,
            "address": address,
            "station": station,
            "age": age,
            "floor": floor,
            "rent": rent,
            "admin_fee": admin_fee,
            "layout": layout,
            "area": area,
            "detail_url": f"https://suumo.jp{detail_url_path}",
            "uid": uid,
        }
        rooms.append(room_data)

    return rooms


def load_state():
    """前回のUIDリストを読み込む"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                state = json.load(f)
                if isinstance(state, list):
                    return state
            except json.JSONDecodeError:
                logger.warning("state.json の形式が不正。空リストで処理。")
    return []


def save_state(current_rooms):
    """現在のUIDリストを保存する"""
    uids = list({r["uid"] for r in current_rooms})
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(uids, f, ensure_ascii=False, indent=2)
    logger.info(f"状態を保存: {len(uids)} 件のUID")


def notify_slack(new_rooms):
    """新着物件をSlackに通知する"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL が未設定。通知をスキップ。")
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏠 SUUMO 新着物件のお知らせ！",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"春日部エリアで *{len(new_rooms)} 件* の新着物件が見つかりました。",
            },
        },
        {"type": "divider"},
    ]

    for room in new_rooms:
        text_lines = [
            f"*<{room['detail_url']}|{room['name']}>*",
            f"💰 {room['rent']} (管理費: {room['admin_fee']})",
            f"🏠 {room['layout']} / {room['area']}",
            f"📍 {room['address']}",
            f"🚉 {room['station']}",
            f"🏢 {room['age']} / {room['floor']}",
        ]
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(text_lines)},
            }
        )
        blocks.append({"type": "divider"})

    try:
        response = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
        if not response.ok:
            logger.error(
                f"Slack通知失敗: status={response.status_code}, body={response.text[:200]}"
            )
            return False
        logger.info(f"Slack へ {len(new_rooms)} 件の通知を送信。")
        return True
    except Exception as e:
        logger.error(f"Slack通知例外: {e}")
        return False


def main():
    logger.info("SUUMO 物件チェックを開始...")

    current_rooms = fetch_all_properties(SEARCH_URL, SEARCH_PARAMS)
    logger.info(f"取得完了: 合計 {len(current_rooms)} 件")

    previous_uids = load_state()

    new_rooms = [r for r in current_rooms if r["uid"] not in previous_uids]

    if new_rooms:
        logger.info(f"{len(new_rooms)} 件の新着物件を発見！")
        for r in new_rooms:
            logger.info(f"  新着: {r['name']} {r['rent']} {r['layout']} ({r['uid']})")
        notify_slack(new_rooms)
    else:
        logger.info("新着物件なし。")

    save_state(current_rooms)


if __name__ == "__main__":
    main()
