#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: mteam_tg_tools_enhanced.py
# 描述: M-Team助手，用于搜索种子、添加到qBittorrent及管理任务。
# 安装三方依赖： pip install pytz requests python-telegram-bot qbittorrent-api

import asyncio
import html
import logging
import math
import os
import re
import sys
import warnings
from typing import Optional, List, Tuple, Dict, Any, Union, Literal
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import pytz
import requests
import telegram
import telegram.warnings
from qbittorrentapi import Client, APIError
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MTEAM_CATEGORY_DATA = {
    "100": "电影", "423": "PC游戏", "427": "电子書", "401": "电影/SD", "434": "Music(无损)",
    "403": "影剧/综艺/SD", "404": "纪录", "405": "动画", "407": "运动", "419": "电影/HD",
    "422": "软件", "402": "影剧/综艺/HD", "448": "TV遊戲", "105": "影剧/综艺", "442": "有聲書",
    "438": "影剧/综艺/BD", "444": "紀錄", "451": "教育影片", "406": "演唱", "420": "电影/DVDiSo",
    "435": "影剧/综艺/DVDiSo", "110": "Music", "409": "Misc(其他)", "421": "电影/Blu-Ray",
    "439": "电影/Remux", "447": "遊戲", "449": "動漫", "450": "其他", "115": "AV(有码)",
    "120": "AV(无码)", "445": "IV", "446": "H-ACG", "410": "AV(有码)/HD Censored",
    "429": "AV(无码)/HD Uncensored", "424": "AV(有码)/SD Censored", "430": "AV(无码)/SD Uncensored",
    "426": "AV(无码)/DVDiSo Uncensored", "437": "AV(有码)/DVDiSo Censored",
    "431": "AV(有码)/Blu-Ray Censored", "432": "AV(无码)/Blu-Ray Uncensored",
    "436": "AV(网站)/0Day", "425": "IV(写真影集)", "433": "IV(写真图集)", "411": "H-游戏",
    "412": "H-动漫", "413": "H-漫画", "440": "AV(Gay)/HD"
}


def get_mteam_category_name(category_id: str) -> str:
    return MTEAM_CATEGORY_DATA.get(str(category_id), f"分类ID:{category_id}")


def format_mteam_discount(discount_code: Optional[str]) -> str:
    if not discount_code or discount_code == "NORMAL":
        return ""
    discount_map = {
        "FREE": "🆓 免费!", "PERCENT_25": "💸 25% OFF", "PERCENT_50": "💸 50% OFF",
        "PERCENT_75": "💸 75% OFF", "FREE_2X": "🆓 2X Free!", "FREE_2X_PERCENT_50": "💸 2X 50% OFF"
    }
    return discount_map.get(discount_code.upper(), f"优惠: {html.escape(discount_code)}")


(
    CHOOSING_ACTION, ASK_ADD_MT_ID, SELECTING_ADD_CATEGORY, ASK_SETCAT_MT_ID,
    SELECTING_SETCAT_CATEGORY, ASK_DEL_MT_ID, CONFIRM_DEL_OPTIONS,
    ASK_SEARCH_KEYWORDS, SHOWING_SEARCH_RESULTS,
) = range(9)

ADD_TASK_BTN = "➕ 添加任务"
MODIFY_CAT_BTN = "🔄 修改分类"
DELETE_TASK_BTN = "🗑️ 删除任务"
SEARCH_TORRENT_BTN = "🔍 搜索种子"
CANCEL_BTN = "↩️ 返回菜单"

ADD_CAT_PREFIX = "addcat_"
MOD_CAT_PREFIX = "modcat_"
DEL_OPT_PREFIX = "delopt_"
SEARCH_PAGE_PREFIX = "searchpage_"
SEARCH_SELECT_PREFIX = "searchsel_"
SEARCH_CANCEL_PREFIX = "searchcancel_"


class Config:
    """管理机器人及服务配置信息"""

    def __init__(self):
        logger.info("⚙️ 初始化配置信息...")
        self.QBIT_HOST: str = os.environ.get("QBIT_HOST", "localhost")
        self.QBIT_PORT: int = int(os.environ.get("QBIT_PORT", "8080"))
        self.QBIT_USERNAME: str = os.environ.get("QBIT_USERNAME", "admin")
        self.QBIT_PASSWORD: str = os.environ.get("QBIT_PASSWORD", "adminadmin")
        self.QBIT_DEFAULT_CATEGORY_FOR_MT: str = os.environ.get("QBIT_DEFAULT_CATEGORY_FOR_MT", "M-Team-DL")
        tags_str: str = os.environ.get("QBIT_DEFAULT_TAGS_FOR_MT", "TG机器人")
        self.QBIT_DEFAULT_TAGS_FOR_MT: List[str] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        self.TG_BOT_TOKEN: Optional[str] = os.environ.get("TG_BOT_TOKEN")
        allowed_chat_ids_str: Optional[str] = os.environ.get("TG_ALLOWED_CHAT_IDS")
        self.TG_ALLOWED_CHAT_IDS: List[int] = []
        if allowed_chat_ids_str:
            try:
                self.TG_ALLOWED_CHAT_IDS = [int(chat_id.strip()) for chat_id in allowed_chat_ids_str.split(',') if
                                            chat_id.strip()]
                logger.info(f"ℹ️ 允许的Telegram聊天ID: {self.TG_ALLOWED_CHAT_IDS}")
            except ValueError:
                logger.error("🚫 TG_ALLOWED_CHAT_IDS 格式无效。")
                logger.warning("⚠️ TG_ALLOWED_CHAT_IDS 格式无效，不限制用户访问。")
        self.MT_HOST: Optional[str] = os.environ.get("MT_HOST", "https://api.m-team.cc")
        self.MT_APIKEY: Optional[str] = os.environ.get("MT_APIKEY")
        self.USE_IPV6_DOWNLOAD: bool = os.environ.get("USE_IPV6_DOWNLOAD", "False").lower() == 'true'
        self.LOCAL_TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Asia/Shanghai")
        self._validate_critical_configs()
        logger.info("👍 配置加载成功。")

    def _validate_critical_configs(self):
        critical_missing = [name for name, value in [
            ("QBIT_HOST", self.QBIT_HOST), ("QBIT_USERNAME", self.QBIT_USERNAME),
            ("QBIT_PASSWORD", self.QBIT_PASSWORD), ("TG_BOT_TOKEN", self.TG_BOT_TOKEN),
            ("MT_HOST", self.MT_HOST), ("MT_APIKEY", self.MT_APIKEY)
        ] if not value]
        if critical_missing:
            error_msg = f"关键环境变量未设置: {', '.join(critical_missing)}。"
            logger.critical(f"🚫 {error_msg} 脚本无法运行。")
            sys.exit(f"致命错误: {error_msg}")


class MTeamManager:
    """M-Team API 管理"""

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if self.config.MT_APIKEY:
            self.session.headers.update({"x-api-key": self.config.MT_APIKEY})
        else:
            logger.error("🚫 M-Team API 密钥未配置。")
        logger.info("🔑 M-Team API 会话已配置。")

    def get_torrent_details(self, torrent_id: str) -> Optional[Dict[str, Any]]:
        if not self.config.MT_APIKEY or not self.config.MT_HOST: return None
        url = f"{self.config.MT_HOST}/api/torrent/detail"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data:
                logger.warning(f"⚠️ M-Team API 获取种子 {torrent_id} 详情: {data.get('message', '未知错误')}")
                return None
            return data["data"]
        except Exception as e:
            logger.error(f"🚫 获取 M-Team 种子 {torrent_id} 详情失败: {e}")
        return None

    def get_torrent_download_url(self, torrent_id: str) -> Literal[b""] | None:
        if not self.config.MT_APIKEY or not self.config.MT_HOST: return None
        url = f"{self.config.MT_HOST}/api/torrent/genDlToken"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data or not data["data"]:
                logger.warning(f"⚠️ M-Team API 生成下载链接 {torrent_id}: {data.get('message', '无Token')}")
                return None
            token_url_part = data["data"]
            parsed_token_url = urlparse(token_url_part)
            query_params = parse_qs(parsed_token_url.query)
            query_params["https"] = ["1"]
            query_params["ipv6"] = ["1"] if self.config.USE_IPV6_DOWNLOAD else ["0"]
            base_parts = urlparse(self.config.MT_HOST) if not (
                    parsed_token_url.scheme and parsed_token_url.netloc) else parsed_token_url
            final_url_parts = base_parts._replace(path=parsed_token_url.path, query=urlencode(query_params, doseq=True))
            return urlunparse(final_url_parts)
        except Exception as e:
            logger.error(f"🚫 获取 M-Team 下载链接 {torrent_id} 失败: {e}")
        return None

    def search_torrents_by_keyword(self, keyword: str, search_mode: str = "normal", page_number: int = 1,
                                   page_size: int = 5) -> Optional[Dict[str, Any]]:
        if not self.config.MT_APIKEY or not self.config.MT_HOST: return None
        url = f"{self.config.MT_HOST}/api/torrent/search"
        payload = {"mode": search_mode, "keyword": keyword, "categories": [], "pageNumber": page_number,
                   "pageSize": page_size}
        logger.info(f"� M-Team API 搜索: {payload}")
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            api_response = response.json()
            if api_response.get("message", "").upper() != 'SUCCESS' or "data" not in api_response:
                logger.warning(f"⚠️ M-Team API 搜索 '{keyword}': {api_response.get('message', '未知错误')}")
                return None
            response_data_field = api_response.get("data")
            if not isinstance(response_data_field, dict):
                logger.warning(f"⚠️ M-Team API 搜索 '{keyword}' data格式错误.")
                return {"torrents": [], "total_results": 0, "current_page_api": 1, "total_pages_api": 0,
                        "items_per_page_api": page_size}

            torrents_list_raw = response_data_field.get("data", [])
            formatted_torrents = []
            for t in torrents_list_raw:
                title_to_display = t.get("smallDescr") or t.get("name", "未知标题")
                subtitle_text = ""
                if t.get("smallDescr") and t.get("name") != t.get("smallDescr"):
                    subtitle_text = t.get("name", "")

                display_text = (f"《<b>👉 {html.escape(title_to_display)}</b>》\n"
                                + (
                                    f"  ◉ 📝 种子名称: <i>{html.escape(subtitle_text[:72] + ('...' if len(subtitle_text) > 72 else subtitle_text))}</i>\n" if subtitle_text else "\n") +
                                f"  ◉ 🆔 MT资源ID: <code>{t.get('id', 'N/A')}</code>\n"
                                f"  ◉ 💾 资源大小: {QBittorrentManager.format_bytes(int(t.get('size', 0)))}\n"
                                f"  ◉ 📂 资源类型: {html.escape(get_mteam_category_name(str(t.get('category', '0'))))}\n"
                                f"  ◉ 💰 优惠状态: {format_mteam_discount(t.get('status', {}).get('discount', ''))}"
                                ).strip()
                formatted_torrents.append(
                    {"id": f"{t.get('id')}", "name": title_to_display, "display_text": display_text,
                     "api_details": t})

            return {
                "torrents": formatted_torrents,
                "total_results": response_data_field.get("total", 0),
                "current_page_api": response_data_field.get("pageNumber", page_number),
                "total_pages_api": response_data_field.get("totalPages", 0),
                "items_per_page_api": response_data_field.get("pageSize", page_size)
            }
        except Exception as e:
            logger.error(f"🚫 M-Team API 搜索 '{keyword}' 失败: {e}", exc_info=True)
        return None


def generate_qb_torrent_name_for_mt(mteam_id: str, api_details: Dict[str, Any], qb_category_name: str) -> str:
    title_source = api_details.get("smallDescr") or api_details.get("name", "未知M-Team标题")
    rename_parts = [f"[{mteam_id}]"]
    if qb_category_name:
        cleaned_qb_category = re.sub(r'[\\/*?:"<>|\s]', '_', qb_category_name)
        cleaned_qb_category = re.sub(r'_+', '_', cleaned_qb_category).strip('_')[:30].strip(".-_ ")
        if cleaned_qb_category: rename_parts.append(f"[{cleaned_qb_category}]")

    supplement_part_cleaned = ""
    if title_source:
        temp_name = re.sub(r'\[.*?]|\(.*?\)', '', title_source).strip()
        title_elements = temp_name.split('-')
        if len(title_elements) > 1 and title_elements[-1].isalnum() and not title_elements[-1].islower() and len(
                title_elements[-1]) < 12:
            temp_name = "-".join(title_elements[:-1]).strip()
        if temp_name:
            supplement_part_cleaned = re.sub(r'[\\/*?:"<>|]', '', temp_name.replace(' ', '.'))[:72].strip(".-_ ")
    if supplement_part_cleaned: rename_parts.append(f"[{supplement_part_cleaned}]")

    rename_value = "".join(rename_parts)
    return re.sub(r'\.+', '.', rename_value).strip('. ')[:250] or f"[{mteam_id}][M-Team_Torrent]"


class QBittorrentManager:
    """qBittorrent API 管理"""

    def __init__(self, config: Config, mteam_manager: MTeamManager):
        self.config = config
        self.client: Optional[Client] = None
        self.mteam_manager = mteam_manager

    def connect_qbit(self) -> bool:
        if self.client and self.client.is_logged_in: return True
        logger.info(f"🔗 [qB] 连接到: {self.config.QBIT_HOST}:{self.config.QBIT_PORT}")
        try:
            self.client = Client(host=self.config.QBIT_HOST, port=self.config.QBIT_PORT,
                                 username=self.config.QBIT_USERNAME, password=self.config.QBIT_PASSWORD,
                                 REQUESTS_ARGS={"timeout": (10, 30)})
            self.client.auth_log_in()
            logger.info(f"✅ [qB] 连接成功 (v{self.client.app.version})")
            return True
        except Exception as e:
            logger.error(f"🚫 [qB] 连接失败: {e}")
            self.client = None
        return False

    def disconnect_qbit(self) -> None:
        if self.client and self.client.is_logged_in:
            try:
                self.client.auth_log_out()
            except Exception:
                pass
        self.client = None

    @staticmethod
    def format_bytes(b: Union[int, str]) -> str:
        try:
            b_int = int(b)
        except (ValueError, TypeError):
            return str(b)
        if b_int == 0: return "0B"
        units = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(abs(b_int), 1024))) if abs(b_int) > 0 else 0
        i = min(i, len(units) - 1)
        val = round(b_int / math.pow(1024, i), 2)
        return f"{val}{units[i]}"

    @staticmethod
    def _get_torrent_state_emoji(state_str: str, progress: float) -> str:
        state_map = {
            "downloading": "📥", "forcedDL": "फोर्सDL", "metaDL": "🔗DL",
            "uploading": "📤", "forcedUP": "फोर्सUP", "stalledUP": "⚠️UP",
            "pausedDL": "⏸️DL", "pausedUP": "⏸️UP",
            "checkingDL": "🔄DL", "checkingUP": "🔄UP", "checkingResumeData": "🔄",
            "queuedDL": "⏳DL", "queuedUP": "⏳UP",
            "allocating": "💾", "moving": "🚚",
            "errored": "🚫", "missingFiles": "📄",
            "unknown": "❓"
        }
        if progress == 1.0:
            if state_str in ["uploading", "forcedUP", "stalledUP"]: return "✅📤"
            if state_str == "pausedUP": return "✅⏸️"
            return "✅"
        return state_map.get(state_str, "▶️")

    async def get_all_torrents_info(self, page: int = 1, items_per_page: int = 10) -> Tuple[
        bool, Union[Dict[str, Any], str]]:
        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        try:
            torrents_list = self.client.torrents_info(status_filter='all', sort="added_on", reverse=True) or None
            total_torrents = len(torrents_list)
            total_pages = math.ceil(total_torrents / items_per_page) or 0
            current_page = max(1, min(page, total_pages or 1))
            torrents_for_page = torrents_list[(current_page - 1) * items_per_page: current_page * items_per_page]
            parts = [
                f"{self._get_torrent_state_emoji(t.state, t.progress)} <b>{html.escape(t.name[:72])}{'...' if len(t.name) > 72 else ''}</b>\n  {t.progress * 100:.1f}% | {self.format_bytes(t.size)}"
                for t in torrents_for_page]
            return True, {"message_parts": parts, "total_torrents": total_torrents, "current_page": current_page,
                          "total_pages": total_pages}
        except Exception as e:
            logger.error(f"🚫 [qB] 获取任务列表出错: {e}", exc_info=True)
            return False, "❌ 获取qB任务列表时发生内部错误。"
        finally:
            self.disconnect_qbit()

    @staticmethod
    def extract_id_from_name(torrent_name: str) -> Optional[str]:
        match = re.match(r'^\[(\d+)]', torrent_name)
        return match.group(1) if match else None

    async def find_torrent_hash_by_mteam_id(self, mteam_id: str) -> Optional[str]:
        if not self.connect_qbit(): return None
        try:
            for torrent in (self.client.torrents_info() or []):
                if self.extract_id_from_name(torrent.name) == mteam_id: return torrent.hash
        except Exception as e:
            logger.error(f"🚫 [qB] 按M-Team ID ({mteam_id}) 查找种子出错: {e}")
        finally:
            self.disconnect_qbit()
        return None

    async def get_all_categories(self) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        try:
            categories = sorted(list((self.client.torrent_categories.categories or {}).keys()))
            msg = "📚 <b>qB分类列表:</b>\n" + ("\n".join(
                f"  👉  <b>{html.escape(name)}</b>" for name in categories) if categories else f"  👉  <b>无任何分类</b>")
            return True, msg
        except Exception as e:
            logger.error(f"🚫 [qB] 获取分类列表出错: {e}", exc_info=True)
            return False, "❌ 获取qB分类列表时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def get_qb_category_names_list(self) -> Tuple[bool, Union[List[str], str]]:
        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        try:
            return True, sorted(list((self.client.torrent_categories.categories or {}).keys()))
        except Exception as e:
            logger.error(f"🚫 [qB] 获取分类名称列表出错: {e}", exc_info=True)
            return False, "❌ 获取qB分类名称列表时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def set_torrent_category_by_hash(self, torrent_hash: str, new_category: str) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        cleaned_new_category = new_category.strip()
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents: return False, f"🤷 未找到 HASH 为 {torrent_hash[:8]}.. 的种子。"
            current_torrent = torrents[0]
            name_esc = html.escape(current_torrent.name[:72]) + ('...' if len(current_torrent.name) > 72 else '')
            new_cat_esc = html.escape(cleaned_new_category) or "<i>(无分类)</i>"
            if current_torrent.category == cleaned_new_category:
                return True, f"ℹ️ 分类未更改: {name_esc} 已是 {new_cat_esc}"
            self.client.torrents_set_category(torrent_hashes=torrent_hash, category=cleaned_new_category)
            act_txt = "移除分类" if not cleaned_new_category else "分类更新"
            return True, f"✅ {act_txt}成功: {name_esc} -> {new_cat_esc}"
        except APIError as e:
            if "incorrect category name" in str(e).lower() or "不正确的分类名" in str(e):
                return False, f"🚫 qB API错误: 分类 '{html.escape(cleaned_new_category)}' 无效或不存在。"
            return False, f"🚫 qB API错误: {html.escape(str(e))}"
        except Exception as e:
            logger.error(f"🚫 [qB] 设置分类出错: {e}", exc_info=True)
            return False, "❌ 设置分类时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def add_mteam_torrent(self, mteam_id_str: str, user_specified_qb_category: Optional[str]) -> Tuple[bool, str]:
        logger.info(f"ℹ️ [MT->qB] 添加M-Team种子 {mteam_id_str}...")
        api_details = await asyncio.to_thread(self.mteam_manager.get_torrent_details, mteam_id_str)
        if not api_details: return False, f"🤷 无法获取M-Team ID <code>{html.escape(mteam_id_str)}</code> 的详情。"

        display_title = api_details.get("smallDescr") or api_details.get("name", "未知标题")
        title_short_esc = html.escape(display_title[:60]) + ('...' if len(display_title) > 60 else '')
        mt_detail_url = f"{self.config.MT_HOST}/detail/{mteam_id_str}" if self.config.MT_HOST else f"https://m-team.cc/detail/{mteam_id_str}"

        actual_category = (
            user_specified_qb_category if user_specified_qb_category is not None else self.config.QBIT_DEFAULT_CATEGORY_FOR_MT).strip()
        actual_cat_esc = html.escape(actual_category) or "<i>(无分类)</i>"
        qb_name = generate_qb_torrent_name_for_mt(mteam_id_str, api_details, actual_category)
        qb_name_esc = html.escape(qb_name)

        download_url = await asyncio.to_thread(self.mteam_manager.get_torrent_download_url, mteam_id_str)
        if not download_url: return False, f"🤷 无法为M-Team ID '<code>{mteam_id_str}</code>' 生成下载链接。"

        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        try:
            res = self.client.torrents_add(urls=download_url, category=actual_category, rename=qb_name,
                                           tags=self.config.QBIT_DEFAULT_TAGS_FOR_MT, paused=False, sequential=True,
                                           first_last_piece_prio=True)
            msg_base = (f"  标题: {title_short_esc}\n"
                        f"  M-Team ID: <code>{mteam_id_str}</code> (<a href=\"{mt_detail_url}\">详情</a>)\n"
                        f"  qB任务名: {qb_name_esc}")
            if str(res).lower().strip() == "ok." or res is True:
                return True, f"✅ <b>成功添加种子到qB</b>\n{msg_base}\n  分类: {actual_cat_esc}"

            if any(t.name == qb_name and t.category == actual_category for t in (self.client.torrents_info() or [])):
                return True, f"ℹ️ <b>种子已在qB中 (名称分类匹配)</b>\n{msg_base}"
            logger.warning(f"qB添加种子响应非预期: {res}")
            return False, f"⚠️ 添加响应非 'Ok.' (实际: {html.escape(str(res))})。请检查qB客户端。"
        except APIError as e:
            if any(p in str(e).lower() for p in ["already in the download list", "种子已存在"]):
                return True, f"ℹ️ <b>种子已在qB中 (API报告重复)</b>\n  标题: {title_short_esc}\n  M-Team ID: <code>{mteam_id_str}</code>"
            logger.error(f"🚫 [qB] 添加种子API错误: {e}")
            return False, f"🚫 qB API错误: {html.escape(str(e))}"
        except Exception as e:
            logger.error(f"🚫 [qB] 添加种子出错: {e}", exc_info=True)
            return False, "❌ 添加种子到qB时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def delete_torrent_by_hash(self, torrent_hash: str, delete_files: bool) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到qB服务器。"
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents: return False, f"🤷 未找到HASH为 {torrent_hash[:8]}.. 的种子。"
            name = torrents[0].name
            self.client.torrents_delete(torrent_hashes=torrent_hash, delete_files=delete_files)
            act_desc = "并删除文件" if delete_files else "(未删除文件)"
            return True, f"🗑️ 种子 '{html.escape(name)}' 已从qB删除{act_desc}。"
        except Exception as e:
            logger.error(f"🚫 [qB] 删除种子出错: {e}", exc_info=True)
            return False, f"❌ 删除种子时发生内部错误: {html.escape(str(e))}"
        finally:
            self.disconnect_qbit()


async def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[ADD_TASK_BTN, MODIFY_CAT_BTN], [SEARCH_TORRENT_BTN, DELETE_TASK_BTN], [CANCEL_BTN]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user, chat_id = update.effective_user, update.effective_chat.id
    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权使用此机器人。")
        return ConversationHandler.END
    logger.info(f"/start by {user.id if user else '未知'} (chat: {chat_id})")
    await update.message.reply_html(f"您好，{user.mention_html()}！", reply_markup=await get_main_keyboard())
    return CHOOSING_ACTION


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.bot_data['config'].TG_ALLOWED_CHAT_IDS and update.effective_chat.id not in context.bot_data[
        'config'].TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权使用此机器人。")
        return
    help_text = (
        "<b>M-Team[馒头PT] 与 qBittorrent 管理助手</b>\n\n"
        "<b>主菜单操作:</b>\n"
        f"  {ADD_TASK_BTN}: 按 M-Team ID添加。\n"
        f"  {MODIFY_CAT_BTN}: 修改任务分类。\n"
        f"  {SEARCH_TORRENT_BTN}: 关键词搜索M-Team种子。\n"
        f"  {DELETE_TASK_BTN}: 删除任务。\n"
        f"  {CANCEL_BTN}: 返回主菜单。\n\n"
        "<b>命令:</b>\n"
        "  /start - 显示主菜单\n"
        "  /cancel - 取消当前操作\n"
        "  /help - 本帮助\n"
        "  /listcats - qB分类列表\n"
        "  /qbtasks [页码] - qB任务列表"
    )
    await update.message.reply_html(help_text, reply_markup=await get_main_keyboard())


async def list_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.bot_data['config'].TG_ALLOWED_CHAT_IDS and update.effective_chat.id not in context.bot_data[
        'config'].TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("无权限操作。")
        return
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    processing_msg = await update.message.reply_text("🔄 查询qB分类中...")
    success, message = await qb_manager.get_all_categories()
    try:
        await processing_msg.edit_text(message, parse_mode=ParseMode.HTML)
    except Exception:
        logger.warning(f"编辑分类列表消息失败，尝试发送新消息。原消息: {message[:100]}")
        await update.message.reply_html(message, reply_markup=await get_main_keyboard())


async def qbtasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.bot_data['config'].TG_ALLOWED_CHAT_IDS and update.effective_chat.id not in context.bot_data[
        'config'].TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("无权限操作。")
        return
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    await _display_torrent_page(update, context, context.bot_data['config'], context.bot_data['qb_manager'], page,
                                initial_command_message=update.message)


async def _display_torrent_page(update_obj: Union[Update, telegram.CallbackQuery], context, config, qb_manager,
                                page_num, initial_command_message=None):
    chat_id: Optional[int] = None
    if isinstance(update_obj, Update) and update_obj.effective_chat:
        chat_id = update_obj.effective_chat.id
    elif isinstance(update_obj, telegram.CallbackQuery) and update_obj.message and update_obj.message.chat:
        chat_id = update_obj.message.chat.id

    if not chat_id:
        logger.error("🚫 _display_torrent_page: 无法确定 chat_id。")
        return
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        if isinstance(update_obj, telegram.CallbackQuery): await update_obj.answer("无权限", show_alert=True)
        return

    msg_to_edit_id = None
    temp_msg_sent = False

    if isinstance(update_obj, telegram.CallbackQuery) and update_obj.message:
        message_to_edit = update_obj.message
        msg_to_edit_id = message_to_edit.message_id
        await update_obj.answer()
    elif initial_command_message:
        try:
            temp_msg = await initial_command_message.reply_text("🔄 查询qB任务中...")
            msg_to_edit_id = temp_msg.message_id
            temp_msg_sent = True
        except Exception as e:
            logger.error(f"为 _display_torrent_page 发送临时消息失败: {e}")
            return

    if not msg_to_edit_id:
        logger.warning("_display_torrent_page: 无消息可编辑或回复。")
        return

    success, data = await qb_manager.get_all_torrents_info(page=page_num)
    text, markup = "❌ 获取任务列表出错。", None
    if success and isinstance(data, dict):
        header = f"📊 <b>qB任务列表</b> (总数: {data.get('total_torrents', 0)}, 第 {data.get('current_page', 1)}/{data.get('total_pages', 0)} 页)"
        text = header + ("\n\n" + "\n\n".join(data.get('message_parts', [])) if data.get(
            'message_parts') else "\n\nℹ️ 当前页无任务。")
        if data.get('total_pages', 0) > 1:
            btns = []
            if data.get('current_page', 1) > 1: btns.append(
                InlineKeyboardButton("⬅️ 上一页", callback_data=f"qbtasks_page_{data.get('current_page', 1) - 1}"))
            if data.get('current_page', 1) < data.get('total_pages', 0): btns.append(
                InlineKeyboardButton("➡️ 下一页", callback_data=f"qbtasks_page_{data.get('current_page', 1) + 1}"))
            if btns: markup = InlineKeyboardMarkup([btns])
    elif isinstance(data, str):
        text = data

    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_to_edit_id, text=text, reply_markup=markup,
                                            parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"编辑任务列表消息失败: {e}")
            if temp_msg_sent and initial_command_message:
                await initial_command_message.reply_html(text, reply_markup=markup)
    except Exception as e:
        logger.error(f"显示任务列表页面出错: {e}", exc_info=True)
        if initial_command_message and temp_msg_sent:
            await initial_command_message.reply_text("显示任务列表时出错。", reply_markup=await get_main_keyboard())


async def qbtasks_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.message: return
    page = int(query.data.split("_")[-1])
    await _display_torrent_page(query, context, context.bot_data['config'], context.bot_data['qb_manager'], page,
                                initial_command_message=update.message)


async def common_input_ask(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, next_state: int,
                           operation: str) -> int:
    if context.bot_data['config'].TG_ALLOWED_CHAT_IDS and update.effective_chat.id not in context.bot_data[
        'config'].TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权执行此操作。", reply_markup=await get_main_keyboard())
        return ConversationHandler.END
    logger.info(f"请求用户进行 '{operation}' 操作 (ID: {update.effective_user.id})")
    await update.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())
    return next_state


async def ask_add_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入M-Team种子ID:", ASK_ADD_MT_ID, "添加M-Team ID")


async def ask_setcat_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入 qB 中任务的 M-Team 种子 ID:", ASK_SETCAT_MT_ID,
                                  "设置分类 M-Team ID")


async def ask_del_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入qB中要删除任务的M-Team ID:", ASK_DEL_MT_ID, "删除M-Team ID")


async def ask_search_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入M-Team搜索关键词:", ASK_SEARCH_KEYWORDS, "搜索关键词")


async def received_add_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text("M-Team ID应为数字，请重新输入。", reply_markup=await get_main_keyboard())
        return ASK_ADD_MT_ID
    context.user_data['add_mt_id'] = mt_id

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    config_instance: Config = context.bot_data['config']
    status, categories = await qb_manager.get_qb_category_names_list()
    buttons = []
    if status and isinstance(categories, list):
        for cat_name in categories[:20]:
            buttons.append([InlineKeyboardButton(f"📁 {cat_name}", callback_data=f"{ADD_CAT_PREFIX}{cat_name}")])
    buttons.extend(
        [
            [InlineKeyboardButton(f"{config_instance.QBIT_DEFAULT_CATEGORY_FOR_MT}",
                                  callback_data=f"{ADD_CAT_PREFIX}_default_")],
            [InlineKeyboardButton("🚫 无分类", callback_data=f"{ADD_CAT_PREFIX}_none_")],
            [InlineKeyboardButton("↩️ 取消", callback_data=f"{ADD_CAT_PREFIX}_cancel_")]
        ]
    )
    await update.message.reply_html(f"M-Team ID: <code>{html.escape(mt_id)}</code>\n请选择qB分类:",
                                    reply_markup=InlineKeyboardMarkup(buttons))
    return SELECTING_ADD_CATEGORY


async def handle_add_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_option = query.data[len(ADD_CAT_PREFIX):]

    if chosen_option == "_cancel_": return await cancel_conversation(update, context)

    mt_id = context.user_data.pop('add_mt_id', None)
    if not mt_id:
        await query.edit_message_text("内部错误：M-Team ID丢失。", reply_markup=None)
        return await cancel_conversation(update, context)

    config: Config = context.bot_data['config']
    selected_category = config.QBIT_DEFAULT_CATEGORY_FOR_MT if chosen_option == "_default_" else (
        "" if chosen_option == "_none_" else chosen_option)

    await query.edit_message_text(
        f"🔄 添加中 (ID: <b>{mt_id}</b>, 分类: {html.escape(selected_category) or '无'})...", reply_markup=None,
        parse_mode=ParseMode.HTML)
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    success, message = await qb_manager.add_mteam_torrent(mt_id, selected_category)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None)
    except telegram.error.TelegramError:
        await context.bot.send_message(query.message.chat.id, message, parse_mode=ParseMode.HTML)

    return CHOOSING_ACTION


async def received_setcat_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text("M-Team ID应为数字。", reply_markup=await get_main_keyboard())
        return ASK_SETCAT_MT_ID

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    processing_msg = await update.message.reply_text(f"🔄 查找M-Team ID {html.escape(mt_id)}...")
    torrent_hash = await qb_manager.find_torrent_hash_by_mteam_id(mt_id)

    if not torrent_hash:
        await processing_msg.edit_text(f"🤷 未找到ID为 {html.escape(mt_id)} 的任务。", reply_markup=None)
        return CHOOSING_ACTION

    context.user_data.update({'setcat_torrent_hash': torrent_hash, 'setcat_mteam_id_display': mt_id})

    name, current_cat = "未知", "未知"
    if qb_manager.connect_qbit():
        try:
            info = qb_manager.client.torrents_info(torrent_hashes=torrent_hash)
            if info: _, current_cat = info[0].name, info[0].category or "<i>(无分类)</i>"
        finally:
            qb_manager.disconnect_qbit()

    _, categories = await qb_manager.get_qb_category_names_list()
    buttons = [[InlineKeyboardButton(f"📁 {cat}", callback_data=f"{MOD_CAT_PREFIX}{cat}")] for cat in categories[:20] if
               isinstance(categories, list)]
    buttons.extend([
        [InlineKeyboardButton("🚫 移除分类", callback_data=f"{MOD_CAT_PREFIX}_remove_")],
        [InlineKeyboardButton("❌ 取消", callback_data=f"{MOD_CAT_PREFIX}_cancel_")]
    ])
    await processing_msg.edit_text(
        f"任务: {html.escape(name)}\nID: {html.escape(mt_id)}, HASH: <b>{torrent_hash[:8]}..</b>\n"
        f"当前分类: {current_cat}\n<b>请选择新分类:</b>",
        reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
    )
    return SELECTING_SETCAT_CATEGORY


async def handle_setcat_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_option = query.data[len(MOD_CAT_PREFIX):]

    if chosen_option == "_cancel_": return await cancel_conversation(update, context)

    data = context.user_data
    torrent_hash, mt_id_display = data.pop('setcat_torrent_hash', None), data.pop('setcat_mteam_id_display', '未知ID')
    if not torrent_hash:
        await query.edit_message_text("内部错误：HASH丢失。", reply_markup=None)
        return await cancel_conversation(update, context)

    new_category = "" if chosen_option == "_remove_" else chosen_option
    await query.edit_message_text(f"🔄 更新分类中 (ID {html.escape(mt_id_display)})...", reply_markup=None,
                                  parse_mode=ParseMode.HTML)
    success, message = await context.bot_data['qb_manager'].set_torrent_category_by_hash(torrent_hash, new_category)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None)
    except telegram.error.TelegramError:
        await context.bot.send_message(query.message.chat.id, message, parse_mode=ParseMode.HTML)
    return CHOOSING_ACTION


async def received_del_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text("M-Team ID应为数字。", reply_markup=await get_main_keyboard())
        return ASK_DEL_MT_ID

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    processing_msg = await update.message.reply_text(f"🔄 查找M-Team ID {html.escape(mt_id)}...")
    torrent_hash = await qb_manager.find_torrent_hash_by_mteam_id(mt_id)

    if not torrent_hash:
        await processing_msg.edit_text(f"🤷 未找到ID为 {html.escape(mt_id)} 的任务。", reply_markup=None)
        return CHOOSING_ACTION

    name = "未知任务"
    if qb_manager.connect_qbit():
        try:
            info = qb_manager.client.torrents_info(torrent_hashes=torrent_hash)
            if info: _ = info[0].name
        finally:
            qb_manager.disconnect_qbit()

    buttons = [
        [InlineKeyboardButton("🗑️ 删除任务和文件", callback_data=f"{DEL_OPT_PREFIX}{torrent_hash}_files")],
        [InlineKeyboardButton("➖ 仅删除任务", callback_data=f"{DEL_OPT_PREFIX}{torrent_hash}_nofiles")],
        [InlineKeyboardButton("🚫 取消", callback_data=f"{DEL_OPT_PREFIX}cancel_na")]
    ]
    await processing_msg.edit_text(
        f"任务: {html.escape(name)}\nID: {html.escape(mt_id)}, HASH: <b>{torrent_hash[:8]}..</b>\n"
        f"<b>确认删除 (不可逆):</b>",
        reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
    )
    return CONFIRM_DEL_OPTIONS


async def received_del_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    payload = query.data[len(DEL_OPT_PREFIX):]

    if payload.startswith("cancel"): return await cancel_conversation(update, context)

    parts = payload.split("_")
    if len(parts) < 2:
        await query.edit_message_text("回调数据错误。", reply_markup=None)
        return await cancel_conversation(update, context)

    torrent_hash, option = parts[0], parts[1]
    delete_files = (option == "files")

    await query.edit_message_text(f"🔄 删除中 (HASH: <b>{torrent_hash[:8]}..</b>)...", reply_markup=None,
                                  parse_mode=ParseMode.HTML)
    success, message = await context.bot_data['qb_manager'].delete_torrent_by_hash(torrent_hash, delete_files)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None)
    except telegram.error.TelegramError:
        await context.bot.send_message(query.message.chat.id, message, parse_mode=ParseMode.HTML)
    return CHOOSING_ACTION


async def received_search_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keywords = update.message.text.strip()
    if not keywords:
        await update.message.reply_text("关键词不能为空。", reply_markup=await get_main_keyboard())
        return ASK_SEARCH_KEYWORDS
    context.user_data.update({'search_keywords': keywords, 'search_mode': "normal"})
    return await display_search_results_page(update, context, page_num=0)


async def display_search_results_page(update: Union[Update, telegram.CallbackQuery], context: ContextTypes.DEFAULT_TYPE,
                                      page_num: int) -> int:
    chat_id: Optional[int] = None
    if isinstance(update, Update) and update.effective_chat:
        chat_id = update.effective_chat.id
    elif isinstance(update, telegram.CallbackQuery) and update.message and update.message.chat:
        chat_id = update.message.chat.id

    if not chat_id:
        logger.error("🚫 _display_torrent_page: 无法确定 chat_id。")
        return ConversationHandler.END

    message_to_handle = update.message
    # message_to_handle = update.message if isinstance(update, Update) else update.callback_query.message

    if isinstance(update, telegram.CallbackQuery): await update.answer()

    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        if isinstance(update, Update): await message_to_handle.reply_text("无权限。",
                                                                          reply_markup=await get_main_keyboard())
        return ConversationHandler.END

    keywords = context.user_data.get('search_keywords')
    if not keywords:
        err_msg = "内部错误：关键词丢失。"
        if isinstance(update, telegram.CallbackQuery):
            await message_to_handle.edit_text(err_msg, reply_markup=None)
        else:
            await message_to_handle.reply_text(err_msg, reply_markup=await get_main_keyboard())
        return ConversationHandler.END

    processing_msg = None
    if isinstance(update, Update):
        processing_msg = await message_to_handle.reply_text(f"🔍 搜索 “{html.escape(keywords)}”中...")

    results_data = await asyncio.to_thread(context.bot_data['mteam_manager'].search_torrents_by_keyword,
                                           keyword=keywords, page_number=page_num + 1)
    if processing_msg: await processing_msg.delete()

    if not results_data:
        err_msg = "搜索出错或无结果。"
        if isinstance(update, telegram.CallbackQuery):
            await message_to_handle.edit_text(err_msg, reply_markup=None)
        else:
            await message_to_handle.reply_text(err_msg, reply_markup=await get_main_keyboard())
        return SHOWING_SEARCH_RESULTS

    torrents, total_res = results_data.get("torrents", []), results_data.get("total_results", 0)
    curr_page_api = results_data.get("current_page_api", 1)
    raw_total_pages = results_data.get("total_pages_api")
    try:
        total_pages_api = int(raw_total_pages) if raw_total_pages is not None else 0
    except ValueError:
        logger.warning(f"M-Team API 返回了无法解析的totalPages: '{raw_total_pages}'. 默认为0.")
        total_pages_api = 0

    if not torrents and total_res == 0:
        msg = f"🤷 未找到 “{html.escape(keywords)}” 相关种子。"
        if isinstance(update, telegram.CallbackQuery):
            await message_to_handle.edit_text(msg, reply_markup=None)
        else:
            await message_to_handle.reply_text(msg)
        return CHOOSING_ACTION

    header = f"【🔎 <b>搜索结果: “{html.escape(keywords)}”</b> (共 {total_res} 个)】"
    content_parts = [t['display_text'] for t in torrents]
    kbd_rows = [[InlineKeyboardButton(f"📥 选择下载 (ID: {t['id']})", callback_data=f"{SEARCH_SELECT_PREFIX}{t['id']}")]
                for
                t in torrents]

    pg_btns = []
    if page_num > 0: pg_btns.append(
        InlineKeyboardButton("⬅️ 上一页", callback_data=f"{SEARCH_PAGE_PREFIX}{page_num - 1}"))
    if (page_num + 1) < total_pages_api: pg_btns.append(
        InlineKeyboardButton("➡️ 下一页", callback_data=f"{SEARCH_PAGE_PREFIX}{page_num + 1}"))
    if pg_btns: kbd_rows.append(pg_btns)
    kbd_rows.append([InlineKeyboardButton("❌ 取消搜索", callback_data=f"{SEARCH_CANCEL_PREFIX}end")])

    full_text = header + ("\n\n" + "\n\n".join(content_parts) if content_parts else "\n") + \
                (
                    f"\n\n\n    ✌️ 📄 第 <b>{curr_page_api} / {total_pages_api} </b>页 ✌️\n\n" if total_pages_api > 0 else "\n")

    try:
        if isinstance(update, telegram.CallbackQuery):
            await message_to_handle.edit_text(full_text, parse_mode=ParseMode.HTML,
                                              reply_markup=InlineKeyboardMarkup(kbd_rows))
        else:
            await context.bot.send_message(chat_id, full_text, parse_mode=ParseMode.HTML,
                                           reply_markup=InlineKeyboardMarkup(kbd_rows))
    except Exception as e:
        logger.error(f"显示搜索结果页出错: {e}")
        await context.bot.send_message(chat_id, "显示结果出错。", reply_markup=await get_main_keyboard())
        return CHOOSING_ACTION
    return SHOWING_SEARCH_RESULTS


async def handle_search_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    page_num = int(query.data[len(SEARCH_PAGE_PREFIX):])
    return await display_search_results_page(query, context, page_num=page_num)


async def handle_search_result_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mt_id = query.data[len(SEARCH_SELECT_PREFIX):]
    if not mt_id.isdigit():
        await query.message.chat.send_message(text="选择错误，ID无效。", reply_markup=None)
        return SHOWING_SEARCH_RESULTS
    context.user_data['add_mt_id'] = mt_id
    await query.message.chat.send_message(f"已选种子ID: {mt_id}. 请选择qB分类:", reply_markup=None,
                                          parse_mode=ParseMode.HTML)
    config: Config = context.bot_data['config']
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    _, categories = await qb_manager.get_qb_category_names_list()
    buttons = [[InlineKeyboardButton(f"📁 {cat}", callback_data=f"{ADD_CAT_PREFIX}{cat}")] for cat in categories[:20] if
               isinstance(categories, list)]
    buttons.extend([
        [InlineKeyboardButton(f"默认: {config.QBIT_DEFAULT_CATEGORY_FOR_MT}",
                              callback_data=f"{ADD_CAT_PREFIX}_default_")],
        [InlineKeyboardButton("🚫 无分类", callback_data=f"{ADD_CAT_PREFIX}_none_")],
        [InlineKeyboardButton("❌ 取消", callback_data=f"{ADD_CAT_PREFIX}_cancel_")]
    ])
    await context.bot.send_message(query.message.chat.id, "请为下载选择qB分类:",
                                   reply_markup=InlineKeyboardMarkup(buttons))
    return SELECTING_ADD_CATEGORY


async def handle_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.chat.send_message(text="搜索已取消", reply_markup=None)
    except Exception:
        pass
    return await cancel_conversation(update, context)


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user, chat_id = update.effective_user, update.effective_chat.id
    logger.info(f"用户 {user.id if user else '未知'} 取消操作 (chat: {chat_id})")
    context.user_data.clear()

    cancel_msg = "操作已取消。"
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(text=cancel_msg, reply_markup=None)
        except telegram.error.BadRequest:
            pass

    await context.bot.send_message(chat_id, f"{cancel_msg} 🏠 已返回主菜单。", reply_markup=await get_main_keyboard(),
                                   parse_mode=ParseMode.HTML)
    return CHOOSING_ACTION


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.bot_data['config'].TG_ALLOWED_CHAT_IDS and update.effective_chat.id not in context.bot_data[
        'config'].TG_ALLOWED_CHAT_IDS: return
    await update.message.reply_text("⚠️ 未知命令。请使用菜单或 /help。", reply_markup=await get_main_keyboard())


async def unknown_text_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"输入无效。请使用按钮或 /cancel 返回主菜单。",
                                    reply_markup=await get_main_keyboard())


async def post_init_hook(application: Application) -> None:
    commands = [BotCommand("start", "▶️ 主菜单"), BotCommand("cancel", "🚫 取消"), BotCommand("listcats", "📚 qB分类"),
                BotCommand("qbtasks", "📊 qB任务"), BotCommand("help", "ℹ️ 帮助")]
    try:
        await application.bot.set_my_commands(commands)
    except Exception as e:
        logger.error(f"设置命令失败: {e}")


def main_bot() -> None:
    try:
        config = Config()
    except SystemExit:
        return

    mteam_manager = MTeamManager(config)
    qb_manager = QBittorrentManager(config, mteam_manager)

    if not config.TG_BOT_TOKEN:
        logger.critical("🚫 TG_BOT_TOKEN 未配置!")
        sys.exit(1)

    app = Application.builder().token(config.TG_BOT_TOKEN).post_init(post_init_hook).build()
    app.bot_data.update({'config': config, 'qb_manager': qb_manager, 'mteam_manager': mteam_manager})

    # 独立命令处理器
    app.add_handler(CommandHandler("listcats", list_categories_command))
    app.add_handler(CommandHandler("qbtasks", qbtasks_command))
    app.add_handler(CommandHandler("help", help_command))

    warnings.filterwarnings("ignore", category=telegram.warnings.PTBUserWarning)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            MessageHandler(filters.Regex(f"^{ADD_TASK_BTN}$"), ask_add_mt_id),
            MessageHandler(filters.Regex(f"^{MODIFY_CAT_BTN}$"), ask_setcat_mt_id),
            MessageHandler(filters.Regex(f"^{DELETE_TASK_BTN}$"), ask_del_mt_id),
            MessageHandler(filters.Regex(f"^{SEARCH_TORRENT_BTN}$"), ask_search_keywords),
        ],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.Regex(f"^{ADD_TASK_BTN}$"), ask_add_mt_id),
                MessageHandler(filters.Regex(f"^{MODIFY_CAT_BTN}$"), ask_setcat_mt_id),
                MessageHandler(filters.Regex(f"^{DELETE_TASK_BTN}$"), ask_del_mt_id),
                MessageHandler(filters.Regex(f"^{SEARCH_TORRENT_BTN}$"), ask_search_keywords),
            ],
            ASK_ADD_MT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_add_mt_id)],
            SELECTING_ADD_CATEGORY: [CallbackQueryHandler(handle_add_category_selection, pattern=f"^{ADD_CAT_PREFIX}")],
            ASK_SETCAT_MT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_setcat_mt_id)],
            SELECTING_SETCAT_CATEGORY: [
                CallbackQueryHandler(handle_setcat_category_selection, pattern=f"^{MOD_CAT_PREFIX}")],
            ASK_DEL_MT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_del_mt_id)],
            CONFIRM_DEL_OPTIONS: [CallbackQueryHandler(received_del_option, pattern=f"^{DEL_OPT_PREFIX}")],
            ASK_SEARCH_KEYWORDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_search_keywords)],
            SHOWING_SEARCH_RESULTS: [
                CallbackQueryHandler(handle_search_pagination, pattern=f"^{SEARCH_PAGE_PREFIX}"),
                CallbackQueryHandler(handle_search_result_selection, pattern=f"^{SEARCH_SELECT_PREFIX}"),
                CallbackQueryHandler(handle_search_cancel, pattern=f"^{SEARCH_CANCEL_PREFIX}end"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("cancel", cancel_conversation),
            # help 已作为独立命令，此处也可保留以在会话中取消并显示帮助
            CommandHandler("help", help_command),
            MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=f"^{ADD_CAT_PREFIX}_cancel_"),
            CallbackQueryHandler(cancel_conversation, pattern=f"^{MOD_CAT_PREFIX}_cancel_"),
            CallbackQueryHandler(cancel_conversation, pattern=f"^{DEL_OPT_PREFIX}cancel_na"),
            # 确保未知命令和文本处理器在最后
            MessageHandler(filters.COMMAND, unknown_command),
            MessageHandler(filters.TEXT, unknown_text_in_conversation)
        ],
        name="mteam_qb_conv",
        allow_reentry=True,
    )

    app.add_handler(conv_handler)  # 会话处理器
    app.add_handler(CallbackQueryHandler(qbtasks_page_callback, pattern=r"^qbtasks_page_"))
    # 最后的捕获，如果其他处理器都未匹配
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("🤖 Telegram 机器人启动...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # 检查关键测试环境变量是否已设置 (避免使用 "your_..." 占位符运行)
    required_for_test = ["MT_APIKEY", "TG_BOT_TOKEN", "TG_ALLOWED_CHAT_IDS",
                         "QBIT_USERNAME", "QBIT_PASSWORD", "QBIT_HOST"]
    placeholders_found = [k for k in required_for_test if "your_" in os.environ.get(k, "")]

    if placeholders_found:
        print("=" * 60)
        print("⚠️  警告: 一个或多个关键环境变量仍使用占位符。")
        print(f"   请编辑脚本中的 if __name__ == '__main__': 部分，")
        print(f"   或通过实际的环境变量提供它们。")
        print(f"   当前包含占位符的变量: {', '.join(placeholders_found)}")
        print("=" * 60)
        if "CI" not in os.environ:
            logger.warning("测试环境变量包含占位符，脚本将继续运行，但功能可能受限。")
        else:
            logger.warning("CI 环境检测到，尽管存在占位符环境变量，仍将继续。")

    main_bot()
