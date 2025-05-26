#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: mteam_tg_tools_enhanced_optimized.py
# 描述: M-Team助手，用于搜索种子、添加到qBittorrent及管理任务 (交互优化版)。
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
from qbittorrentapi import Client, APIError, TorrentInfoList
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
    "100": "电影", "423": "PC游戏", "427": "电子書", "401": "电影-SD", "434": "Music(无损)",
    "403": "影剧-综艺-SD", "404": "纪录", "405": "动画", "407": "运动", "419": "电影-HD",
    "422": "软件", "402": "影剧-综艺-HD", "448": "TV遊戲", "105": "影剧-综艺", "442": "有聲書",
    "438": "影剧-综艺-BD", "444": "紀錄", "451": "教育影片", "406": "演唱", "420": "电影-DVDiSo",
    "435": "影剧-综艺-DVDiSo", "110": "Music", "409": "Misc(其他)", "421": "电影-Blu-Ray",
    "439": "电影-Remux", "447": "遊戲", "449": "動漫", "450": "其他", "115": "AV(有码)",
    "120": "AV(无码)", "445": "IV", "446": "H-ACG", "410": "AV(有码)-HD Censored",
    "429": "AV(无码)-HD Uncensored", "424": "AV(有码)-SD Censored",
    "430": "AV(无码)-SD Uncensored",
    "426": "AV(无码)-DVDiSo Uncensored", "437": "AV(有码)-DVDiSo Censored",
    "431": "AV(有码)-Blu-Ray Censored", "432": "AV(无码)-Blu-Ray Uncensored",
    "436": "AV(网站)-0Day", "425": "IV(写真影集)", "433": "IV(写真图集)", "411": "H-游戏",
    "412": "H-动漫", "413": "H-漫画", "440": "AV(Gay)-HD"
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

ADD_TASK_BTN = "📥 添加任务"
MODIFY_CAT_BTN = "🔄 修改分类"
DELETE_TASK_BTN = "🗑️ 删除任务"
SEARCH_TORRENT_BTN = "🔍 搜索种子"
SUB_TORRENT_BTN = "👻 订阅剧集"
CANCEL_BTN = "↩️ 返回菜单"
CANCEL_OPT = "🛑 取消操作"

ADD_CAT_PREFIX = "addcat_"
MOD_CAT_PREFIX = "modcat_"
DEL_OPT_PREFIX = "delopt_"
SEARCH_PAGE_PREFIX = "searchpage_"
SEARCH_SELECT_PREFIX = "searchsel_"
SEARCH_CANCEL_PREFIX = "searchcancel_"
QBTASKS_PAGE_PREFIX = "qbtasks_page_"


class Config:
    def __init__(self):
        logger.info("⚙️ 初始化配置信息...")
        self.QBIT_HOST: str = os.environ.get("QBIT_HOST", "localhost")
        self.QBIT_PORT: int = int(os.environ.get("QBIT_PORT", "8080"))
        self.QBIT_USERNAME: str = os.environ.get("QBIT_USERNAME", "admin")
        self.QBIT_PASSWORD: str = os.environ.get("QBIT_PASSWORD", "adminadmin")
        self.QBIT_DEFAULT_CATEGORY_FOR_MT: str = os.environ.get("QBIT_DEFAULT_CATEGORY_FOR_MT", "M-Team-DL")
        tags_str: str = os.environ.get("QBIT_DEFAULT_TAGS_FOR_MT", "TG机器人")
        self.QBIT_DEFAULT_TAGS_FOR_MT: List[str] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        self.TG_BOT_TOKEN_MT: Optional[str] = os.environ.get("TG_BOT_TOKEN_MT")
        allowed_chat_ids_str: Optional[str] = os.environ.get("TG_ALLOWED_CHAT_IDS")
        self.TG_ALLOWED_CHAT_IDS: List[int] = []
        if allowed_chat_ids_str:
            try:
                self.TG_ALLOWED_CHAT_IDS = [int(chat_id.strip()) for chat_id in allowed_chat_ids_str.split(',') if
                                            chat_id.strip()]
                logger.info(f"💡 允许的Telegram聊天ID: {self.TG_ALLOWED_CHAT_IDS}")
            except ValueError:
                logger.error("🚫 TG_ALLOWED_CHAT_IDS 格式无效。将不限制用户访问。")
                self.TG_ALLOWED_CHAT_IDS = []
        else:
            logger.warning("⚠️ TG_ALLOWED_CHAT_IDS 未设置，不限制用户访问。")

        self.MT_HOST: Optional[str] = os.environ.get("MT_HOST", "https://api.m-team.cc")
        self.MT_APIKEY: Optional[str] = os.environ.get("MT_APIKEY")
        self.USE_IPV6_DOWNLOAD: bool = os.environ.get("USE_IPV6_DOWNLOAD", "False").lower() == 'true'
        self.LOCAL_TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Asia/Shanghai")
        self._validate_critical_configs()
        logger.info("👍 配置加载成功。")

    def _validate_critical_configs(self):
        critical_missing = [name for name, value in [
            ("QBIT_HOST", self.QBIT_HOST), ("QBIT_USERNAME", self.QBIT_USERNAME),
            ("QBIT_PASSWORD", self.QBIT_PASSWORD), ("TG_BOT_TOKEN_MT", self.TG_BOT_TOKEN_MT),
            ("MT_HOST", self.MT_HOST), ("MT_APIKEY", self.MT_APIKEY)
        ] if not value]
        if critical_missing:
            error_msg = f"关键环境变量未设置: {', '.join(critical_missing)}。"
            logger.critical(f"🚫 {error_msg} 脚本无法运行。")
            sys.exit(f"致命错误: {error_msg}")


class MTeamManager:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if self.config.MT_APIKEY:
            self.session.headers.update({"x-api-key": self.config.MT_APIKEY})
        else:
            logger.error("🚫 M-Team API 密钥未在配置中提供。M-Team相关功能将无法使用。")
        logger.info("🔑 M-Team API 会话已配置。")

    def get_torrent_details(self, torrent_id: str) -> Optional[Dict[str, Any]]:
        if not self.config.MT_APIKEY or not self.config.MT_HOST:
            logger.warning("🚫 M-Team API密钥或主机未配置，无法获取种子详情。")
            return None
        url = f"{self.config.MT_HOST}/api/torrent/detail"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data:
                logger.warning(f"⚠️ M-Team API 获取种子 {torrent_id} 详情响应异常: {data.get('message', '未知错误')}")
                return None
            return data["data"]
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 M-Team API 请求获取种子 {torrent_id} 详情失败: {e}")
        except Exception as e:
            logger.error(f"🚫 解析 M-Team 种子 {torrent_id} 详情响应时发生未知错误: {e}")
        return None

    def get_torrent_download_url(self, torrent_id: str) -> Literal[b""] | None:
        if not self.config.MT_APIKEY or not self.config.MT_HOST:
            logger.warning("🚫 M-Team API密钥或主机未配置，无法获取下载链接。")
            return None
        url = f"{self.config.MT_HOST}/api/torrent/genDlToken"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data or not data["data"]:
                logger.warning(f"⚠️ M-Team API 生成下载链接 {torrent_id} 响应异常: {data.get('message', '无Token')}")
                return None

            token_url_part = data["data"]
            parsed_token_url = urlparse(token_url_part)
            query_params = parse_qs(parsed_token_url.query)
            query_params["https"] = ["1"]
            query_params["ipv6"] = ["1"] if self.config.USE_IPV6_DOWNLOAD else ["0"]

            base_parts = urlparse(self.config.MT_HOST)
            if parsed_token_url.scheme and parsed_token_url.netloc:
                base_parts = base_parts._replace(scheme=parsed_token_url.scheme, netloc=parsed_token_url.netloc)

            final_url_parts = base_parts._replace(path=parsed_token_url.path, query=urlencode(query_params, doseq=True))
            return urlunparse(final_url_parts)
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 M-Team API 请求生成下载链接 {torrent_id} 失败: {e}")
        except Exception as e:
            logger.error(f"🚫 解析 M-Team 下载链接 {torrent_id} 响应时发生未知错误: {e}")
        return None

    def search_torrents_by_keyword(self, keyword: str, search_mode: str = "normal", page_number: int = 1,
                                   page_size: int = 5) -> Optional[Dict[str, Any]]:
        if not self.config.MT_APIKEY or not self.config.MT_HOST:
            logger.warning("🚫 M-Team API密钥或主机未配置，无法搜索种子。")
            return None
        url = f"{self.config.MT_HOST}/api/torrent/search"
        payload = {"mode": search_mode, "keyword": keyword, "categories": [], "pageNumber": page_number,
                   "pageSize": page_size}
        logger.info(f"🔍 M-Team API 搜索请求: {payload}")
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            api_response = response.json()
            if api_response.get("message", "").upper() != 'SUCCESS' or "data" not in api_response:
                logger.warning(f"⚠️ M-Team API 搜索 '{keyword}' 响应异常: {api_response.get('message', '未知错误')}")
                return None

            response_data_field = api_response.get("data")
            if not isinstance(response_data_field, dict):
                logger.warning(f"⚠️ M-Team API 搜索 '{keyword}' 返回的 'data' 字段格式错误，期望为字典。")
                return {"torrents": [], "total_results": 0, "current_page_api": 1, "total_pages_api": 0,
                        "items_per_page_api": page_size}

            torrents_list_raw = response_data_field.get("data", [])
            if not isinstance(torrents_list_raw, list):
                logger.warning(f"⚠️ M-Team API 搜索 '{keyword}' 返回的 'data.data' 字段格式错误，期望为列表。")
                torrents_list_raw = []

            formatted_torrents = []
            for t in torrents_list_raw:
                if not isinstance(t, dict):
                    logger.warning(f"⚠️ M-Team API 搜索结果中包含非字典类型的种子项: {t}")
                    continue

                title_to_display = t.get("smallDescr") or t.get("name", "未知标题")
                subtitle_text = ""
                if t.get("smallDescr") and t.get("name") != t.get("smallDescr"):
                    subtitle_text = t.get("name", "")

                display_text = (f"<b>👉 {html.escape(title_to_display)}</b>\n\n"
                                + (
                                    f"  ◉ 📝 种子名称: <i>{html.escape(subtitle_text[:72] + ('...' if len(subtitle_text) > 72 else ''))}</i>\n" if subtitle_text else "") +
                                f"  ◉ 🆔 MT资源ID: <code>{t.get('id', 'N/A')}</code>\n"
                                f"  ◉ 💾 资源大小: {QBittorrentManager.format_bytes(int(t.get('size', 0)))}\n"
                                f"  ◉ 📂 资源类型: {html.escape(get_mteam_category_name(str(t.get('category', '0'))))}\n"
                                f"  ◉ 💰 优惠状态: {format_mteam_discount(t.get('status', {}).get('discount', ''))}"
                                ).strip()
                formatted_torrents.append(
                    {"id": str(t.get('id')), "name": title_to_display, "display_text": display_text,
                     "api_details": t})

            return {
                "torrents": formatted_torrents,
                "total_results": response_data_field.get("total", 0),
                "current_page_api": response_data_field.get("pageNumber", page_number),
                "total_pages_api": response_data_field.get("totalPages", 0),
                "items_per_page_api": response_data_field.get("pageSize", page_size)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 M-Team API 搜索 '{keyword}' 请求失败: {e}")
        except Exception as e:
            logger.error(f"🚫 处理 M-Team API 搜索 '{keyword}' 响应时发生未知错误: {e}", exc_info=True)
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
        temp_name = re.sub(r'\[.*?]|\(.*?\)|【.*?】|（.*?）', '', title_source).strip()
        title_elements = temp_name.split('-')
        if len(title_elements) > 1 and title_elements[-1].isalnum() and not title_elements[-1].islower() and len(
                title_elements[-1]) < 12:
            temp_name = "-".join(title_elements[:-1]).strip()

        if temp_name:
            supplement_part_cleaned = re.sub(r'[\\/*?:"<>|]', '', temp_name.replace(' ', '.'))[:72].strip(".-_ ")

    if supplement_part_cleaned: rename_parts.append(f"[{supplement_part_cleaned}]")

    rename_value = "".join(rename_parts)
    final_name = re.sub(r'\.+', '.', rename_value).strip('. ')[:250]
    return final_name or f"[{mteam_id}][M-Team_Torrent]"


class QBittorrentManager:
    def __init__(self, config: Config, mteam_manager: MTeamManager):
        self.config = config
        self.client: Optional[Client] = None
        self.mteam_manager = mteam_manager

    def connect_qbit(self) -> bool:
        if self.client and self.client.is_logged_in: return True
        logger.info(f"🔗 [qBittorrent] 尝试连接到: {self.config.QBIT_HOST}:{self.config.QBIT_PORT}")
        try:
            self.client = Client(host=self.config.QBIT_HOST, port=self.config.QBIT_PORT,
                                 username=self.config.QBIT_USERNAME, password=self.config.QBIT_PASSWORD,
                                 REQUESTS_ARGS={"timeout": (10, 30)})
            self.client.auth_log_in()
            logger.info(
                f"✅ [qBittorrent] 连接成功 (qBittorrent v{self.client.app.version}, API v{self.client.app.web_api_version})")
            return True
        except APIError as e:
            logger.error(f"🚫 [qBittorrent] API登录失败: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 [qBittorrent] 连接请求失败: {e}")
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 连接时发生未知错误: {e}", exc_info=True)
        self.client = None
        return False

    def disconnect_qbit(self) -> None:
        if self.client and self.client.is_logged_in:
            try:
                self.client.auth_log_out()
                logger.info("🚪 [qBittorrent] 已断开连接。")
            except Exception as e:
                logger.warning(f"⚠️ [qBittorrent] 断开连接时发生错误: {e}")
        self.client = None

    @staticmethod
    def format_bytes(b: Union[int, str]) -> str:
        try:
            b_int = int(b)
        except (ValueError, TypeError):
            return str(b)
        if b_int == 0: return "0 B"
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        i = int(math.floor(math.log(abs(b_int), 1024))) if abs(b_int) > 0 else 0
        i = min(i, len(units) - 1)
        val = round(b_int / math.pow(1024, i), 2)
        return f"{val} {units[i]}"

    @staticmethod
    def _get_torrent_state_emoji(state_str: str, progress: float) -> str:
        state_map = {
            "downloading": "📥", "forcedDL": "फोर्सDL", "metaDL": "🔗DL",
            "uploading": "📤", "forcedUP": "फोर्सUP", "stalledUP": "⚠️UP",
            "pausedDL": "⏸️DL", "pausedUP": "⏸️UP",
            "checkingDL": "🔄DL", "checkingUP": "🔄UP", "checkingResumeData": "🔄 RES",
            "queuedDL": "⏳DL", "queuedUP": "⏳UP",
            "allocating": "💾 Alloc", "moving": "🚚 Moving",
            "errored": "🚫 ERROR", "missingFiles": "📄 Missing",
            "unknown": "❓ Unknown"
        }
        if progress == 1.0:
            if state_str in ["uploading", "forcedUP", "stalledUP"]: return "✅📤 Seeding"
            if state_str == "pausedUP": return "✅⏸️ Paused (Complete)"
            return "✅ Done"
        return state_map.get(state_str, f"🚀 {state_str[:10]}")

    async def get_all_torrents_info(self, page: int = 1, items_per_page: int = 10) -> Tuple[
        bool, Union[Dict[str, Any], str]]:
        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。请检查配置和服务器状态。"
        try:
            torrents_list: Optional[TorrentInfoList] = self.client.torrents_info(status_filter='all')
            if torrents_list is None: torrents_list = TorrentInfoList([], self.client)

            sorted_torrents = sorted(torrents_list, key=lambda t: t.added_on, reverse=True)

            total_torrents = len(sorted_torrents)
            total_pages = math.ceil(total_torrents / items_per_page) if total_torrents > 0 else 0
            current_page = max(1, min(page, total_pages or 1))

            start_index = (current_page - 1) * items_per_page
            end_index = start_index + items_per_page
            torrents_for_page = sorted_torrents[start_index:end_index]

            parts = []
            for t in torrents_for_page:
                original_name = t.name
                state_emoji = self._get_torrent_state_emoji(t.state, t.progress)

                parsed_id: Optional[str] = None
                parsed_category_from_name: Optional[str] = None
                parsed_title_text: str = original_name

                match = re.match(r'^\[(\d+)](?:\[([^]]*)])?(.*)$', original_name)
                if match:
                    parsed_id = match.group(1)
                    parsed_category_from_name = match.group(2) if match.group(2) else None
                    title_candidate = match.group(3).strip()
                    if title_candidate:
                        parsed_title_text = title_candidate
                    elif parsed_category_from_name:
                        parsed_title_text = f"<i>(ID: {parsed_id}, 分类: {parsed_category_from_name} - 无主标题)</i>"
                    else:
                        parsed_title_text = f"<i>(ID: {parsed_id} - 无主标题)</i>"

                title_display = html.escape(parsed_title_text[:60]) + ('...' if len(parsed_title_text) > 60 else '')
                if not parsed_title_text.strip() or parsed_title_text.startswith(
                        "<i>("):
                    if not match:
                        title_display = html.escape(original_name[:60]) + ('...' if len(original_name) > 60 else '')

                info_lines = [f"{state_emoji} <b>{title_display}</b>"]
                if parsed_id:
                    info_lines.append(f"└─◉ 🆔 MT ID: <code>{html.escape(parsed_id)}</code>")
                info_lines.append(f"└─◉ 💾 下载状态: {self.format_bytes(t.size)} | 📈 {t.progress * 100:.1f}%")
                info_lines.append(
                    f"└─◉ 🚀 当前速度: ↓{self.format_bytes(t.dlspeed)}/s ↑{self.format_bytes(t.upspeed)}/s")
                info_lines.append(f"└─◉ 🏷️ 当前分类: <code>{html.escape(t.category) if t.category else '无'}</code>")

                parts.append("\n".join(info_lines))

            return True, {"message_parts": parts, "total_torrents": total_torrents, "current_page": current_page,
                          "total_pages": total_pages}
        except Exception as e:
            logger.error(f"🚫 [qBittorrent"
                         f"] 获取任务列表时发生错误: {e}", exc_info=True)
            return False, "❌ 获取 qBittorrent 任务列表时发生内部错误。"
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
                if self.extract_id_from_name(torrent.name) == mteam_id:
                    logger.info(f"💡 [qBittorrent] 找到 M-Team ID {mteam_id} 对应的种子 HASH: {torrent.hash}")
                    return torrent.hash
            logger.info(f"💡 [qBittorrent] 未找到 M-Team ID {mteam_id} 对应的种子。")
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 按 M-Team ID ({mteam_id}) 查找种子时出错: {e}")
        finally:
            self.disconnect_qbit()
        return None

    async def get_all_categories(self) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。"
        try:
            categories_dict = self.client.torrent_categories.categories or {}
            categories = sorted(list(categories_dict.keys()))

            if not categories:
                msg = "🗂️ <b>分类列表:</b>\n\n  👉 当前没有任何分类。"
            else:
                cat_lines = [
                    f"  📁 <code>{html.escape(name)}</code>  -  [<code>{html.escape(categories_dict[name].get("savePath", "未知路径"))}</code>]\n"
                    for name in categories]
                msg = "🗂️ <b>分类列表:</b>\n\n" + "".join(cat_lines)
            return True, msg
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 获取分类列表出错: {e}", exc_info=True)
            return False, "❌ 获取 qBittorrent 分类列表时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def get_qb_category_names_list(self) -> Tuple[bool, Union[List[str], str]]:
        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。"
        try:
            categories = sorted(list((self.client.torrent_categories.categories or {}).keys()))
            return True, categories
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 获取分类名称列表出错: {e}", exc_info=True)
            return False, "❌ 获取 qBittorrent 分类名称列表时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def set_torrent_category_by_hash(self, torrent_hash: str, new_category: str) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。"
        cleaned_new_category = new_category.strip()
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents: return False, f"🤷 未在 qBittorrent 中找到 HASH 前缀为 {torrent_hash[:8]}.. 的种子。"

            current_torrent = torrents[0]
            name_esc = html.escape(current_torrent.name[:60]) + ('...' if len(current_torrent.name) > 60 else '')
            old_cat_esc = html.escape(current_torrent.category) if current_torrent.category else "<i>(无分类)</i>"
            new_cat_esc = html.escape(cleaned_new_category) if cleaned_new_category else "<i>(移除分类)</i>"

            if current_torrent.category == cleaned_new_category:
                return True, f"💡 分类未更改: 《{name_esc}》已在分类 {new_cat_esc} 中。"

            self.client.torrents_set_category(torrent_hashes=torrent_hash, category=cleaned_new_category)
            action_text = "移除分类成功" if not cleaned_new_category else "分类更新成功"
            return True, f"✅ {action_text}: 《{name_esc}》\n  旧分类: {old_cat_esc}\n  新分类: {new_cat_esc}"
        except APIError as e:
            if "incorrect category name" in str(e).lower() or "不正确的分类名" in str(e):
                return False, f"🚫 qBittorrent API错误: 分类 “{html.escape(cleaned_new_category)}” 无效或不存在。请先在qB中创建该分类。"
            logger.error(f"🚫 [qBittorrent] 设置分类API错误 (HASH: {torrent_hash}): {e}")
            return False, f"🚫 qBittorrent API错误: {html.escape(str(e))}"
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 设置分类时发生内部错误 (HASH: {torrent_hash}): {e}", exc_info=True)
            return False, "❌ 设置分类时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def add_mteam_torrent(self, mteam_id_str: str, user_specified_qb_category: Optional[str]) -> Tuple[bool, str]:
        logger.info(
            f"💡 [MT->qBittorrent] 准备添加 M-Team 种子 {mteam_id_str} (指定分类: {user_specified_qb_category})")

        api_details = await asyncio.to_thread(self.mteam_manager.get_torrent_details, mteam_id_str)
        if not api_details:
            return False, f"🤷 无法获取 M-Team ID <code>{html.escape(mteam_id_str)}</code> 的详细信息。请检查ID是否正确或 M-Team API 是否工作正常。"

        display_title = api_details.get("smallDescr") or api_details.get("name", "未知标题")
        title_short_esc = html.escape(display_title[:60]) + ('...' if len(display_title) > 60 else '')
        mt_detail_url = f"{self.config.MT_HOST}/detail/{mteam_id_str}" if self.config.MT_HOST else f"https://m-team.cc/detail/{mteam_id_str}"

        actual_category = (user_specified_qb_category if user_specified_qb_category is not None
                           else self.config.QBIT_DEFAULT_CATEGORY_FOR_MT).strip()
        actual_cat_esc = html.escape(actual_category) if actual_category else "<i>(无分类)</i>"

        qb_name = generate_qb_torrent_name_for_mt(mteam_id_str, api_details, actual_category)
        qb_name_esc = html.escape(qb_name)

        download_url = await asyncio.to_thread(self.mteam_manager.get_torrent_download_url, mteam_id_str)
        if not download_url:
            return False, f"🤷 无法为 M-Team ID <code>{html.escape(mteam_id_str)}</code> 生成下载链接。可能是M-Team API问题或种子已失效。"

        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。"
        try:
            existing_hash = await self.find_torrent_hash_by_mteam_id(mteam_id_str)
            if existing_hash:
                if not self.connect_qbit(): return False, "🚫 无法重新连接到 qBittorrent 服务器以检查现有任务。"
                existing_torrents = self.client.torrents_info(torrent_hashes=existing_hash)
                if existing_torrents:
                    existing_torrent_name = html.escape(existing_torrents[0].name)
                    existing_torrent_cat = html.escape(existing_torrents[0].category or '(无分类)')
                    return True, (f"💡 <b>种子已存在于 qBittorrent 中</b>\n"
                                  f"  标题: {title_short_esc} (<a href=\"{mt_detail_url}\">M-Team详情</a>)\n"
                                  f"  M-Team ID: <code>{mteam_id_str}</code>\n"
                                  f"  任务名称: {existing_torrent_name}\n"
                                  f"  任务分类: {existing_torrent_cat}")

            if not self.connect_qbit(): return False, "🚫 无法重新连接到 qBittorrent 服务器以添加任务。"

            res = self.client.torrents_add(
                urls=download_url,
                category=actual_category,
                rename=qb_name,
                tags=self.config.QBIT_DEFAULT_TAGS_FOR_MT,
                paused=False,
                sequential=True,
                first_last_piece_prio=True
            )

            msg_base = (f"  标题: {title_short_esc} (<a href=\"{mt_detail_url}\">M-Team详情</a>)\n"
                        f"  M-Team ID: <code>{mteam_id_str}</code>\n"
                        f"  qB任务名: {qb_name_esc}\n"
                        f"  qB分类: {actual_cat_esc}")

            if str(res).lower().strip() == "ok." or res is True:
                return True, f"✅ <b>成功添加种子到 qB</b>\n{msg_base}"

            logger.warning(f"qBittorrent 添加种子 {mteam_id_str} 响应非预期: {res}")
            return False, f"⚠️ 添加种子到 qBittorrent 时，服务器响应为 “{html.escape(str(res))}” 而非 “Ok.”。\n{msg_base}\n请检查 qBittorrent 客户端确认任务状态。"
        except APIError as e:
            if any(p in str(e).lower() for p in
                   ["already in the download list", "种子已存在", "torrent is already in the download session"]):
                return True, (f"💡 <b>种子已在 qBittorrent 下载会话中 (API报告重复)</b>\n"
                              f"  标题: {title_short_esc} (<a href=\"{mt_detail_url}\">M-Team详情</a>)\n"
                              f"  M-Team ID: <code>{mteam_id_str}</code>")
            logger.error(f"🚫 [qBittorrent] 添加种子 {mteam_id_str} 时发生 API 错误: {e}")
            return False, f"🚫 qBittorrent API 错误: {html.escape(str(e))}"
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 添加种子 {mteam_id_str} 时发生内部错误: {e}", exc_info=True)
            return False, "❌ 添加种子到 qBittorrent 时发生内部错误。"
        finally:
            self.disconnect_qbit()

    async def delete_torrent_by_hash(self, torrent_hash: str, delete_files: bool) -> Tuple[bool, str]:
        if not self.connect_qbit(): return False, "🚫 无法连接到 qBittorrent 服务器。"
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if not torrents: return False, f"🤷 未在 qBittorrent 中找到 HASH 前缀为 {torrent_hash[:8]}.. 的种子。"

            name = torrents[0].name
            name_esc = html.escape(name[:60]) + ('...' if len(name) > 60 else '')

            self.client.torrents_delete(torrent_hashes=torrent_hash, delete_files=delete_files)
            action_desc = "并删除了相关文件" if delete_files else "(任务已移除，文件未删除)"
            return True, f"🗑️ 种子 《{name_esc}》 已从 qBittorrent 删除 {action_desc}。"
        except APIError as e:
            logger.error(f"🚫 [qBittorrent] 删除种子 HASH {torrent_hash} 时发生 API 错误: {e}")
            return False, f"🚫 qBittorrent API 错误: {html.escape(str(e))}"
        except Exception as e:
            logger.error(f"🚫 [qBittorrent] 删除种子 HASH {torrent_hash} 时发生内部错误: {e}", exc_info=True)
            return False, f"❌ 删除种子时发生内部错误: {html.escape(str(e))}"
        finally:
            self.disconnect_qbit()


async def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [ADD_TASK_BTN, MODIFY_CAT_BTN],
				[SUB_TORRENT_BTN],
        [SEARCH_TORRENT_BTN, DELETE_TASK_BTN],
        [CANCEL_BTN, CANCEL_OPT]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']

    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        logger.warning(f"🚫 未授权访问: User {user.id if user else 'Unknown'} (Chat {chat_id}) tried to use /start.")
        await update.message.reply_text("抱歉，您无权使用此机器人。")
        return ConversationHandler.END

    logger.info(f"🚀 /start command initiated by user {user.id if user else 'Unknown'} in chat {chat_id}.")
    await update.message.reply_html(
        f"您好，{user.mention_html() if user else '用户'}！欢迎使用 M-Team 与 qBittorrent 管理助手。",
        reply_markup=await get_main_keyboard()
    )
    return CHOOSING_ACTION


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权使用此机器人。")
        return

    help_text = (
        "<b>💡 M-Team 与 qBittorrent 管理助手 - 帮助信息</b>\n\n"
        "<b>主菜单操作 (通过下方按钮触发):</b>\n"
        f"  <code>{ADD_TASK_BTN}</code>: 根据 M-Team 种子ID 添加下载任务到 qBittorrent。\n"
        f"  <code>{MODIFY_CAT_BTN}</code>: 修改 qBittorrent 中现有任务的分类。\n"
        f"  <code>{SEARCH_TORRENT_BTN}</code>: 通过关键词在 M-Team 网站搜索种子。\n"
        f"  <code>{DELETE_TASK_BTN}</code>: 从 qBittorrent 删除任务 (可选是否删除文件)。\n"
        f"  <code>{CANCEL_BTN}</code>: 取消当前操作并返回主菜单。\n\n"
        f"  <code>{CANCEL_OPT}</code>: 取消当前操。\n\n"
        "<b>快捷命令:</b>\n"
        "  <code>/start</code> - 显示主菜单，开始交互。\n"
        "  <code>/add &lt;M-Team ID&gt;</code> - 直接添加指定 M-Team ID 的种子到 qBittorrent。例如: <code>/add 12345</code>\n"
        "  <code>/cancel</code> - (在操作过程中) 取消当前操作。\n"
        "  <code>/help</code> - 显示此帮助信息。\n"
        "  <code>/listcats</code> - 显示 qBittorrent 中的所有分类及其保存路径。\n"
        "  <code>/qbtasks [页码]</code> - 分页显示 qBittorrent 中的任务列表。例如: <code>/qbtasks 2</code>。\n"
    )
    await update.message.reply_html(help_text, reply_markup=await get_main_keyboard())


async def list_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权执行此操作。")
        return

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    processing_msg = await update.message.reply_text("🔄 正在查询分类列表，请稍候...")

    success, message_or_data = await qb_manager.get_all_categories()

    reply_text = message_or_data if isinstance(message_or_data, str) else "获取分类列表时发生未知错误。"
    if not success and isinstance(message_or_data, str):
        reply_text = message_or_data
    elif not success:
        reply_text = "❌ 获取 qBittorrent 分类列表失败。"

    try:
        await processing_msg.edit_text(reply_text, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"编辑分类列表消息失败 ({e})，尝试发送新消息。")
            await update.message.reply_html(reply_text, reply_markup=await get_main_keyboard())
    except Exception as e:
        logger.error(f"编辑分类列表消息时发生未知错误: {e}", exc_info=True)
        await update.message.reply_html(reply_text, reply_markup=await get_main_keyboard())


async def qbtasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权执行此操作。")
        return

    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
        if page < 1: page = 1

    await _display_torrent_page(update, context, page, initial_command_message=update.message)


async def _display_torrent_page(
        update_obj: Union[Update, telegram.CallbackQuery],
        context: ContextTypes.DEFAULT_TYPE,
        page_num: int,
        initial_command_message: Optional[telegram.Message] = None
):
    config: Config = context.bot_data['config']
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']

    chat_id: Optional[int] = None
    message_to_edit: Optional[telegram.Message] = None

    if isinstance(update_obj, Update):
        if update_obj.effective_chat: chat_id = update_obj.effective_chat.id
        if initial_command_message:
            try:
                message_to_edit = await initial_command_message.reply_text(
                    f"🔄 正在查询任务列表 (第 {page_num} 页)...")
            except Exception as e:
                logger.error(f"为 _display_torrent_page 发送临时消息失败: {e}")
                return
    elif isinstance(update_obj, telegram.CallbackQuery):
        if update_obj.message and update_obj.message.chat:
            chat_id = update_obj.message.chat.id
            message_to_edit = update_obj.message
        await update_obj.answer(text=f"🔄 加载第 {page_num} 页...")

    if not chat_id or not message_to_edit:
        logger.error("🚫 _display_torrent_page: 无法确定 chat_id 或可编辑的消息。")
        return

    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        if isinstance(update_obj, telegram.CallbackQuery): await update_obj.answer("抱歉，您无权操作。", show_alert=True)
        return

    success, data = await qb_manager.get_all_torrents_info(page=page_num)

    text_content: str
    reply_markup_content: Optional[InlineKeyboardMarkup] = None

    if success and isinstance(data, dict):
        header = (
            f"📋 <b>任务列表</b> (共 {data.get('total_torrents', 0)} 个) - [ 第 <b>{data.get('current_page', 1)} / {data.get('total_pages', 0)}</b> 页 ]")

        if data.get('message_parts'):
            text_content = header + "\n\n" + "\n\n".join(data['message_parts'])
        elif data.get('total_torrents', 0) == 0:
            text_content = header + "\n\n💡 qBittorrent 中当前没有任何任务。"
        else:
            text_content = header + "\n\n💡 当前页没有任务显示。"

        if data.get('total_pages', 0) > 1:
            pagination_buttons = []
            if data.get('current_page', 1) > 1:
                pagination_buttons.append(
                    InlineKeyboardButton("⬅️ 上一页", callback_data=f"{QBTASKS_PAGE_PREFIX}{data['current_page'] - 1}")
                )
            if data.get('current_page', 1) < data.get('total_pages', 0):
                pagination_buttons.append(
                    InlineKeyboardButton("➡️ 下一页", callback_data=f"{QBTASKS_PAGE_PREFIX}{data['current_page'] + 1}")
                )
            if pagination_buttons:
                reply_markup_content = InlineKeyboardMarkup([pagination_buttons])
    elif isinstance(data, str):
        text_content = data
    else:
        text_content = "❌ 获取任务列表时发生未知错误。"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_to_edit.message_id,
            text=text_content,
            reply_markup=reply_markup_content,
            parse_mode=ParseMode.HTML
        )
    except telegram.error.BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"编辑任务列表消息失败 (ChatID: {chat_id}, MsgID: {message_to_edit.message_id}): {e}")
            if isinstance(update_obj, Update) and initial_command_message:
                await initial_command_message.reply_html(text_content, reply_markup=reply_markup_content)
    except Exception as e:
        logger.error(f"显示任务列表页面时发生未知错误: {e}", exc_info=True)
        if isinstance(update_obj, Update) and initial_command_message:
            await initial_command_message.reply_text("显示任务列表时出错。", reply_markup=await get_main_keyboard())


async def qbtasks_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.message:
        logger.warning("qbtasks_page_callback: 无效的回调数据。")
        if query: await query.answer("回调错误", show_alert=True)
        return

    try:
        page = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.error(f"qbtasks_page_callback: 无法从回调数据 {query.data} 中解析页码。")
        await query.answer("页码解析错误", show_alert=True)
        return
    await _display_torrent_page(query, context, page)


async def common_input_ask(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, next_state: int,
                           operation_name: str) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']

    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权执行此操作。", reply_markup=await get_main_keyboard())
        return ConversationHandler.END

    logger.info(
        f"用户 {user.id if user else 'Unknown'} (Chat {chat_id}) 请求进行 '{operation_name}' 操作。提示用户输入。")
    await update.message.reply_text(prompt, reply_markup=await get_main_keyboard())
    return next_state


async def ask_add_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入 M-Team 种子 ID:", ASK_ADD_MT_ID,
                                  "添加 M-Team 种子 ID")


async def ask_setcat_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入 M-Team 种子 ID:",
                                  ASK_SETCAT_MT_ID,
                                  "设置分类-输入 M-Team ID")


async def ask_del_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入 M-Team 种子 ID:",
                                  ASK_DEL_MT_ID, "删除任务-输入 M-Team ID")


async def ask_search_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await common_input_ask(update, context, "请输入搜索关键词:", ASK_SEARCH_KEYWORDS,
                                  "搜索种子-输入关键词")


async def _get_category_selection_buttons(context: ContextTypes.DEFAULT_TYPE, prefix: str) -> InlineKeyboardMarkup:
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    config_instance: Config = context.bot_data['config']

    buttons: List[List[InlineKeyboardButton]] = []
    status, categories_or_error = await qb_manager.get_qb_category_names_list()

    if status and isinstance(categories_or_error, list):
        for cat_name in categories_or_error[:15]:
            buttons.append([InlineKeyboardButton(f"📁 {html.escape(cat_name)}", callback_data=f"{prefix}{cat_name}")])
    elif isinstance(categories_or_error, str):
        logger.warning(f"获取分类列表失败: {categories_or_error}")

    buttons.append([InlineKeyboardButton(f"🌟 默认分类 ({html.escape(config_instance.QBIT_DEFAULT_CATEGORY_FOR_MT)})",
                                         callback_data=f"{prefix}_default_")])
    buttons.append([InlineKeyboardButton("🚫 无分类 (添加到根目录)", callback_data=f"{prefix}_none_")])
    buttons.append([InlineKeyboardButton("↩️ 取消操作", callback_data=f"{prefix}_cancel_")])

    return InlineKeyboardMarkup(buttons)


async def received_add_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ASK_ADD_MT_ID

    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text(
            "⚠️ M-Team ID 应该是纯数字，请检查后重新输入，或使用 /cancel 取消。",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_ADD_MT_ID

    context.user_data['add_mt_id'] = mt_id
    logger.info(f"用户 {update.effective_user.id} 输入了M-Team ID: {mt_id} 用于添加。")

    reply_markup = await _get_category_selection_buttons(context, ADD_CAT_PREFIX)
    await update.message.reply_html(
        f"已收到 M-Team ID: <code>{html.escape(mt_id)}</code>\n"
        f"请选择要将其添加到的 qBittorrent 分类:",
        reply_markup=reply_markup
    )
    return SELECTING_ADD_CATEGORY


async def handle_add_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data: return CHOOSING_ACTION
    await query.answer()

    chosen_option_full = query.data
    logger.info(f"用户 {query.from_user.id} 为添加任务选择了分类选项: {chosen_option_full}")

    if chosen_option_full == f"{ADD_CAT_PREFIX}_cancel_":
        try:
            await query.edit_message_text("操作已取消。", reply_markup=None)
        except telegram.error.BadRequest:
            pass
        return await cancel_conversation(update, context)

    chosen_option = chosen_option_full[len(ADD_CAT_PREFIX):]

    mt_id = context.user_data.pop('add_mt_id', None)
    if not mt_id:
        logger.error("内部错误：handle_add_category_selection 中 M-Team ID 丢失。")
        await query.edit_message_text("❌ 内部错误：M-Team ID 信息丢失，无法继续操作。", reply_markup=None)
        return await cancel_conversation(update, context)

    config: Config = context.bot_data['config']
    selected_category: str
    if chosen_option == "_default_":
        selected_category = config.QBIT_DEFAULT_CATEGORY_FOR_MT
    elif chosen_option == "_none_":
        selected_category = ""
    else:
        selected_category = chosen_option

    processing_text = (f"🔄 正在处理 M-Team ID <code>{html.escape(mt_id)}</code>...\n"
                       f"目标分类: {html.escape(selected_category) if selected_category else '<i>无分类</i>'}\n"
                       f"请稍候...")
    try:
        await query.edit_message_text(processing_text, reply_markup=None, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest:
        pass

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    success, message = await qb_manager.add_mteam_torrent(mt_id, selected_category)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None,
                                      disable_web_page_preview=True)
    except telegram.error.TelegramError as e:
        logger.warning(f"编辑添加结果消息失败 ({e})，发送新消息。")
        await context.bot.send_message(
            query.message.chat.id,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=await get_main_keyboard(),
            disable_web_page_preview=True
        )

    context.user_data.pop('search_keywords', None)
    context.user_data.pop('last_search_results', None)

    return CHOOSING_ACTION


async def received_setcat_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ASK_SETCAT_MT_ID

    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text(
            "⚠️ M-Team ID 应该是纯数字，请检查后重新输入，或使用 /cancel 取消。",
            reply_markup=await get_main_keyboard()
        )
        return ASK_SETCAT_MT_ID

    logger.info(f"用户 {update.effective_user.id} 输入了M-Team ID: {mt_id} 用于修改分类。")
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']

    processing_msg = await update.message.reply_text(
        f"🔄 正在 qBittorrent 中查找 M-Team ID <code>{html.escape(mt_id)}</code> 对应的任务...")

    torrent_hash = await qb_manager.find_torrent_hash_by_mteam_id(mt_id)

    if not torrent_hash:
        await processing_msg.edit_text(
            f"🤷 未在 qBittorrent 中找到与 M-Team ID <code>{html.escape(mt_id)}</code> 关联的任务。\n"
            f"请确保该任务已通过本机器人添加，或其名称以 <code>[{mt_id}]</code> 开头。",
            reply_markup=None, parse_mode=ParseMode.HTML
        )
        await update.message.reply_text("请选择其他操作:", reply_markup=await get_main_keyboard())
        return CHOOSING_ACTION

    context.user_data.update({'setcat_torrent_hash': torrent_hash, 'setcat_mteam_id_display': mt_id})

    torrent_name_display = "未知任务"
    current_category_display = "<i>未知</i>"
    if qb_manager.connect_qbit():
        try:
            info_list = qb_manager.client.torrents_info(torrent_hashes=torrent_hash)
            if info_list:
                torrent_info = info_list[0]
                torrent_name_display = html.escape(
                    torrent_info.name[:60] + ('...' if len(torrent_info.name) > 60 else ''))
                current_category_display = html.escape(
                    torrent_info.category) if torrent_info.category else "<i>(无分类)</i>"
        except Exception as e:
            logger.error(f"获取种子 {torrent_hash} 详情时出错: {e}")
        finally:
            qb_manager.disconnect_qbit()

    buttons_list: List[List[InlineKeyboardButton]] = []
    status, categories_or_error = await qb_manager.get_qb_category_names_list()
    if status and isinstance(categories_or_error, list):
        for cat_name in categories_or_error[:15]:
            buttons_list.append(
                [InlineKeyboardButton(f"📁 {html.escape(cat_name)}", callback_data=f"{MOD_CAT_PREFIX}{cat_name}")])

    buttons_list.append([InlineKeyboardButton("🚫 移除当前分类", callback_data=f"{MOD_CAT_PREFIX}_remove_")])
    buttons_list.append([InlineKeyboardButton("↩️ 取消操作", callback_data=f"{MOD_CAT_PREFIX}_cancel_")])

    await processing_msg.edit_text(
        f"找到任务: 《<b>{torrent_name_display}</b>》\n"
        f"M-Team ID: <code>{html.escape(mt_id)}</code> (HASH: <code>{torrent_hash[:8]}..</code>)\n"
        f"当前分类: {current_category_display}\n\n"
        f"<b>请选择新的分类:</b>",
        reply_markup=InlineKeyboardMarkup(buttons_list),
        parse_mode=ParseMode.HTML
    )
    return SELECTING_SETCAT_CATEGORY


async def handle_setcat_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data: return CHOOSING_ACTION
    await query.answer()

    chosen_option_full = query.data
    logger.info(f"用户 {query.from_user.id} 为修改分类选择了选项: {chosen_option_full}")

    if chosen_option_full == f"{MOD_CAT_PREFIX}_cancel_":
        try:
            await query.edit_message_text("操作已取消。", reply_markup=None)
        except telegram.error.BadRequest:
            pass
        return await cancel_conversation(update, context)

    chosen_option = chosen_option_full[len(MOD_CAT_PREFIX):]

    user_data = context.user_data
    torrent_hash = user_data.pop('setcat_torrent_hash', None)
    mt_id_display = user_data.pop('setcat_mteam_id_display', '未知ID')

    if not torrent_hash:
        logger.error("内部错误：handle_setcat_category_selection 中 torrent_hash 丢失。")
        await query.edit_message_text("❌ 内部错误：任务 HASH 信息丢失，无法继续操作。", reply_markup=None)
        return await cancel_conversation(update, context)

    new_category = "" if chosen_option == "_remove_" else chosen_option

    processing_text = (
        f"🔄 正在为 M-Team ID <code>{html.escape(mt_id_display)}</code> (HASH: <code>{torrent_hash[:8]}..</code>) 更新分类...\n"
        f"新分类目标: {html.escape(new_category) if new_category else '<i>移除分类</i>'}\n"
        f"请稍候...")
    try:
        await query.edit_message_text(processing_text, reply_markup=None, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest:
        pass

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    success, message = await qb_manager.set_torrent_category_by_hash(torrent_hash, new_category)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None)
    except telegram.error.TelegramError as e:
        logger.warning(f"编辑设置分类结果消息失败 ({e})，发送新消息。")
        await context.bot.send_message(
            query.message.chat.id,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=await get_main_keyboard()
        )
    return CHOOSING_ACTION


async def received_del_mt_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ASK_DEL_MT_ID

    mt_id = update.message.text.strip()
    if not mt_id.isdigit():
        await update.message.reply_text(
            "⚠️ M-Team ID 应该是纯数字，请检查后重新输入，或使用 /cancel 取消。",
            reply_markup=await get_main_keyboard()
        )
        return ASK_DEL_MT_ID

    logger.info(f"用户 {update.effective_user.id} 输入了M-Team ID: {mt_id} 用于删除任务。")
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']

    processing_msg = await update.message.reply_text(
        f"🔄 正在 qBittorrent 中查找 M-Team ID <code>{html.escape(mt_id)}</code> 对应的任务...")

    torrent_hash = await qb_manager.find_torrent_hash_by_mteam_id(mt_id)

    if not torrent_hash:
        await processing_msg.edit_text(
            f"🤷 未在 qBittorrent 中找到与 M-Team ID <code>{html.escape(mt_id)}</code> 关联的任务。",
            reply_markup=None, parse_mode=ParseMode.HTML
        )
        await update.message.reply_text("请选择其他操作:", reply_markup=await get_main_keyboard())
        return CHOOSING_ACTION

    torrent_name_display = "未知任务"
    if qb_manager.connect_qbit():
        try:
            info_list = qb_manager.client.torrents_info(torrent_hashes=torrent_hash)
            if info_list:
                torrent_name_display = html.escape(
                    info_list[0].name[:60] + ('...' if len(info_list[0].name) > 60 else ''))
        finally:
            qb_manager.disconnect_qbit()

    context.user_data['del_torrent_hash'] = torrent_hash
    context.user_data['del_torrent_name_display'] = torrent_name_display

    buttons = [
        [InlineKeyboardButton("🗑️ 删除任务和文件", callback_data=f"{DEL_OPT_PREFIX}delete_files")],
        [InlineKeyboardButton("➖ 仅删除任务 (保留文件)", callback_data=f"{DEL_OPT_PREFIX}delete_task_only")],
        [InlineKeyboardButton("↩️ 取消操作", callback_data=f"{DEL_OPT_PREFIX}cancel_delete")]
    ]
    await processing_msg.edit_text(
        f"确认删除任务: 《<b>{torrent_name_display}</b>》\n"
        f"M-Team ID: <code>{html.escape(mt_id)}</code> (HASH: <code>{torrent_hash[:8]}..</code>)\n\n"
        f"<b>请选择删除选项 (此操作不可逆):</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )
    return CONFIRM_DEL_OPTIONS


async def received_del_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data: return CHOOSING_ACTION
    await query.answer()

    chosen_option_full = query.data
    logger.info(f"用户 {query.from_user.id} 为删除任务选择了选项: {chosen_option_full}")

    if chosen_option_full == f"{DEL_OPT_PREFIX}cancel_delete":
        try:
            await query.edit_message_text("删除操作已取消。", reply_markup=None)
        except telegram.error.BadRequest:
            pass
        context.user_data.pop('del_torrent_hash', None)
        context.user_data.pop('del_torrent_name_display', None)
        return await cancel_conversation(update, context)

    option_part = chosen_option_full[len(DEL_OPT_PREFIX):]

    torrent_hash = context.user_data.pop('del_torrent_hash', None)
    torrent_name_display = context.user_data.pop('del_torrent_name_display', '该任务')

    if not torrent_hash:
        logger.error("内部错误：received_del_option 中 torrent_hash 丢失。")
        await query.edit_message_text("❌ 内部错误：任务 HASH 信息丢失，无法继续操作。", reply_markup=None)
        return await cancel_conversation(update, context)

    delete_files: bool
    if option_part == "delete_files":
        delete_files = True
        action_readable = "删除任务和文件"
    elif option_part == "delete_task_only":
        delete_files = False
        action_readable = "仅删除任务 (保留文件)"
    else:
        logger.error(f"未知的删除选项: {option_part}")
        await query.edit_message_text("❌ 未知的删除选项。", reply_markup=None)
        return await cancel_conversation(update, context)

    processing_text = (
        f"🔄 正在为 《{html.escape(torrent_name_display)}》 (HASH: <code>{torrent_hash[:8]}..</code>) 执行“{action_readable}”操作...\n"
        f"请稍候...")
    try:
        await query.edit_message_text(processing_text, reply_markup=None, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest:
        pass

    qb_manager: QBittorrentManager = context.bot_data['qb_manager']
    success, message = await qb_manager.delete_torrent_by_hash(torrent_hash, delete_files)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=None)
    except telegram.error.TelegramError as e:
        logger.warning(f"编辑删除结果消息失败 ({e})，发送新消息。")
        await context.bot.send_message(
            query.message.chat.id,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=await get_main_keyboard()
        )
    return CHOOSING_ACTION


async def received_search_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ASK_SEARCH_KEYWORDS

    keywords = update.message.text.strip()
    if not keywords:
        await update.message.reply_text(
            "⚠️ 搜索关键词不能为空，请输入有效的关键词，或使用 /cancel 取消。",
            reply_markup=await get_main_keyboard()
        )
        return ASK_SEARCH_KEYWORDS

    logger.info(f"用户 {update.effective_user.id} 输入了搜索关键词: '{keywords}'")
    context.user_data.update({'search_keywords': keywords, 'search_mode': "normal"})

    return await display_search_results_page(update, context, page_num=0)


async def display_search_results_page(
        update_obj: Union[Update, telegram.CallbackQuery],
        context: ContextTypes.DEFAULT_TYPE,
        page_num: int
) -> int:
    config: Config = context.bot_data['config']
    mteam_manager: MTeamManager = context.bot_data['mteam_manager']

    chat_id: Optional[int] = None
    message_to_handle: Optional[telegram.Message] = None

    if isinstance(update_obj, Update):
        if update_obj.effective_chat: chat_id = update_obj.effective_chat.id
        message_to_handle = update_obj.message
    elif isinstance(update_obj, telegram.CallbackQuery):
        if update_obj.message and update_obj.message.chat:
            chat_id = update_obj.message.chat.id
            message_to_handle = update_obj.message
        await update_obj.answer()

    if not chat_id or not message_to_handle:
        logger.error("🚫 display_search_results_page: 无法确定 chat_id 或要处理的消息。")
        return ConversationHandler.END

    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        if isinstance(update_obj, Update):
            await message_to_handle.reply_text("抱歉，您无权执行此操作。", reply_markup=await get_main_keyboard())
        return ConversationHandler.END

    keywords = context.user_data.get('search_keywords')
    if not keywords:
        logger.error("内部错误：display_search_results_page 中关键词丢失。")
        error_msg = "❌ 内部错误：搜索关键词信息丢失。"
        if isinstance(update_obj, telegram.CallbackQuery):
            await message_to_handle.edit_text(error_msg, reply_markup=None)
        else:
            await message_to_handle.reply_text(error_msg, reply_markup=await get_main_keyboard())
        return ConversationHandler.END

    processing_msg_obj: Optional[telegram.Message] = None
    if isinstance(update_obj, Update):
        processing_msg_obj = await message_to_handle.reply_text(
            f"🔍 正在为 “{html.escape(keywords)}” 搜索 M-Team 种子 (第 {page_num + 1} 页)..."
        )

    results_data = await asyncio.to_thread(
        mteam_manager.search_torrents_by_keyword,
        keyword=keywords,
        page_number=page_num + 1
    )

    if processing_msg_obj:
        try:
            await processing_msg_obj.delete()
        except Exception:
            pass

    if not results_data:
        error_msg = f"⚠️ 搜索 “{html.escape(keywords)}” 时出错，或 M-Team API 未返回有效数据。请稍后再试。"
        if isinstance(update_obj, telegram.CallbackQuery):
            await message_to_handle.edit_text(error_msg, reply_markup=None)
        else:
            await message_to_handle.reply_text(error_msg, reply_markup=await get_main_keyboard())
        return SHOWING_SEARCH_RESULTS

    context.user_data['last_search_results'] = results_data

    torrents = results_data.get("torrents", [])
    total_results = results_data.get("total_results", 0)
    current_page_api = results_data.get("current_page_api", page_num + 1)
    total_pages_api = 0
    try:
        total_pages_api = int(results_data.get("total_pages_api", 0))
    except ValueError:
        logger.warning(f"M-Team API 返回了无法解析的 totalPages: '{results_data.get('total_pages_api')}'. 默认为0.")

    if not torrents and total_results == 0:
        msg_no_results = f"🤷 未找到与 “{html.escape(keywords)}” 相关的 M-Team 种子。"
        if isinstance(update_obj, telegram.CallbackQuery):
            await message_to_handle.edit_text(msg_no_results, reply_markup=None)
        else:
            await message_to_handle.reply_text(msg_no_results, reply_markup=await get_main_keyboard())
        context.user_data.pop('search_keywords', None)
        context.user_data.pop('last_search_results', None)
        return CHOOSING_ACTION

    header = f"🔎 <b>搜索结果: “{html.escape(keywords)}”</b> (共 {total_results} 个)"
    content_parts = [t['display_text'] for t in torrents]

    keyboard_rows: List[List[InlineKeyboardButton]] = []
    for t in torrents:
        btn_text_name = t['name'][:30] + '...' if len(t['name']) > 30 else t['name']
        keyboard_rows.append([
            InlineKeyboardButton(f"📥 下载: {html.escape(btn_text_name)} (ID: {t['id']})",
                                 callback_data=f"{SEARCH_SELECT_PREFIX}{t['id']}")
        ])

    pagination_buttons_row: List[InlineKeyboardButton] = []
    if page_num > 0:
        pagination_buttons_row.append(
            InlineKeyboardButton("⬅️ 上一页", callback_data=f"{SEARCH_PAGE_PREFIX}{page_num - 1}")
        )
    if (page_num + 1) < total_pages_api:
        pagination_buttons_row.append(
            InlineKeyboardButton("➡️ 下一页", callback_data=f"{SEARCH_PAGE_PREFIX}{page_num + 1}")
        )
    if pagination_buttons_row:
        keyboard_rows.append(pagination_buttons_row)

    keyboard_rows.append(
        [InlineKeyboardButton("❌ 取消搜索并返回主菜单", callback_data=f"{SEARCH_CANCEL_PREFIX}end_search")])

    page_info_footer = ""
    if total_pages_api > 0:
        page_info_footer = f"\n\n📄 第 <b>{current_page_api} / {total_pages_api}</b> 页"

    separator = "\n" + "─" * 20 + "\n"
    full_text = header + "\n" + separator.join(content_parts) + page_info_footer

    final_reply_markup = InlineKeyboardMarkup(keyboard_rows)

    try:
        if isinstance(update_obj, telegram.CallbackQuery):
            await message_to_handle.edit_text(full_text, parse_mode=ParseMode.HTML, reply_markup=final_reply_markup,
                                              disable_web_page_preview=True)
        else:
            await context.bot.send_message(
                chat_id,
                full_text,
                parse_mode=ParseMode.HTML,
                reply_markup=final_reply_markup,
                disable_web_page_preview=True
            )
    except telegram.error.BadRequest as e:
        if "message is too long" in str(e).lower():
            simplified_text = header + "\n\n搜索结果过多，无法在此完整显示。\n请尝试缩小搜索范围或使用分页按钮。" + page_info_footer
            if isinstance(update_obj, telegram.CallbackQuery):
                await message_to_handle.edit_text(simplified_text, parse_mode=ParseMode.HTML,
                                                  reply_markup=final_reply_markup)
            else:
                await context.bot.send_message(chat_id, simplified_text, parse_mode=ParseMode.HTML,
                                               reply_markup=final_reply_markup)
        elif "message is not modified" not in str(e).lower():
            logger.error(f"编辑/发送搜索结果页时出错: {e}")
            await context.bot.send_message(chat_id, "显示搜索结果时出错，请重试。",
                                           reply_markup=await get_main_keyboard())
            return CHOOSING_ACTION
    except Exception as e:
        logger.error(f"显示搜索结果页时发生未知错误: {e}", exc_info=True)
        await context.bot.send_message(chat_id, "显示搜索结果时发生严重错误。", reply_markup=await get_main_keyboard())
        return CHOOSING_ACTION

    return SHOWING_SEARCH_RESULTS


async def handle_search_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data: return SHOWING_SEARCH_RESULTS

    try:
        page_num = int(query.data[len(SEARCH_PAGE_PREFIX):])
    except (ValueError, IndexError):
        logger.error(f"handle_search_pagination: 无法从回调数据 {query.data} 解析页码。")
        await query.answer("页码错误", show_alert=True)
        return SHOWING_SEARCH_RESULTS

    logger.info(f"用户 {query.from_user.id} 请求搜索结果第 {page_num + 1} 页。")
    return await display_search_results_page(query, context, page_num=page_num)


async def handle_search_result_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data or not query.message: return SHOWING_SEARCH_RESULTS
    await query.answer()

    mt_id = query.data[len(SEARCH_SELECT_PREFIX):]
    logger.info(f"用户 {query.from_user.id} 从搜索结果中选择了 M-Team ID: {mt_id}")

    if not mt_id.isdigit():
        logger.warning(f"无效的 M-Team ID 从搜索选择回调中获得: {mt_id}")
        await query.message.chat.send_message("⚠️ 选择的种子ID无效，请重试。", reply_markup=None)
        return SHOWING_SEARCH_RESULTS

    context.user_data['add_mt_id'] = mt_id

    selected_torrent_name = f"M-Team ID {html.escape(mt_id)}"
    last_search_results = context.user_data.get('last_search_results', {}).get('torrents', [])
    for torrent_data in last_search_results:
        if str(torrent_data.get('id')) == mt_id:
            selected_torrent_name = html.escape(torrent_data.get('name', selected_torrent_name))
            break

    category_reply_markup = await _get_category_selection_buttons(context, ADD_CAT_PREFIX)

    selection_confirmation_text = (
        f"您已选择种子: 《<b>{selected_torrent_name}</b>》 (ID: <code>{html.escape(mt_id)}</code>)\n\n"
        f"请选择要将其添加到的 qBittorrent 分类:"
    )

    try:
        await query.message.chat.send_message(
            selection_confirmation_text,
            reply_markup=category_reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except telegram.error.BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"编辑消息以选择分类失败 ({e})，发送新消息。")
            await context.bot.send_message(
                query.message.chat.id,
                selection_confirmation_text,
                reply_markup=category_reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"处理搜索结果选择时发生未知错误: {e}", exc_info=True)
        await context.bot.send_message(query.message.chat.id, "处理选择时出错，请重试。",
                                       reply_markup=await get_main_keyboard())
        return CHOOSING_ACTION

    return SELECTING_ADD_CATEGORY


async def handle_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return CHOOSING_ACTION

    await query.answer()
    logger.info(f"用户 {query.from_user.id} 取消了搜索操作。")

    try:
        await query.message.chat.send_message("搜索已取消。", reply_markup=None)
    except telegram.error.BadRequest:
        pass

    context.user_data.pop('search_keywords', None)
    context.user_data.pop('last_search_results', None)

    return await cancel_conversation(update, context)


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id

    action_source = "未知来源"
    if update.message:
        action_source = f"消息 ({update.message.text[:20] if update.message.text else ''})"
    elif update.callback_query:
        action_source = f"回调 ({update.callback_query.data})"

    logger.info(f"用户 {user.id if user else 'Unknown'} (Chat {chat_id}) 通过 {action_source} 取消/结束了当前操作。")

    keys_to_clear = ['add_mt_id', 'setcat_torrent_hash', 'setcat_mteam_id_display',
                     'del_torrent_hash', 'del_torrent_name_display',
                     'search_keywords', 'last_search_results']
    for key in keys_to_clear:
        context.user_data.pop(key, None)

    cancel_feedback_msg = "操作已取消。"

    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(text=cancel_feedback_msg, reply_markup=None)
        except telegram.error.BadRequest:
            pass
        except Exception as e:
            logger.warning(f"取消操作时编辑消息失败: {e}")

    await context.bot.send_message(
        chat_id,
        f"{cancel_feedback_msg} 您已返回主菜单。",
        reply_markup=await get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_ACTION


async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id

    action_source = "未知来源"
    if update.message:
        action_source = f"消息 ({update.message.text[:20] if update.message.text else ''})"
    elif update.callback_query:
        action_source = f"回调 ({update.callback_query.data})"

    logger.info(f"用户 {user.id if user else 'Unknown'} (Chat {chat_id}) 通过 {action_source} 取消/结束了当前操作。")

    keys_to_clear = ['add_mt_id', 'setcat_torrent_hash', 'setcat_mteam_id_display',
                     'del_torrent_hash', 'del_torrent_name_display',
                     'search_keywords', 'last_search_results']
    for key in keys_to_clear:
        context.user_data.pop(key, None)

    cancel_feedback_msg = "操作已取消。"

    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(text=cancel_feedback_msg, reply_markup=None)
        except telegram.error.BadRequest:
            pass
        except Exception as e:
            logger.warning(f"取消操作时编辑消息失败: {e}")

    await context.bot.send_message(
        chat_id,
        f"{cancel_feedback_msg} 您已返回主菜单。",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_ACTION


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']
    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        return

    logger.info(
        f"用户 {update.effective_user.id if update.effective_user else 'Unknown'} 在 Chat {chat_id} 输入了未知命令: {update.message.text if update.message else 'N/A'}")
    await update.message.reply_text(
        "⚠️ 未知命令。\n请使用下方的菜单按钮操作，或输入 /help 查看可用命令列表。",
        reply_markup=await get_main_keyboard()
    )


async def unknown_text_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_state = context.conversation_state
    logger.warning(
        f"用户 {update.effective_user.id if update.effective_user else 'Unknown'} 在会话状态 {current_state} 中输入了意外文本: {update.message.text[:50] if update.message and update.message.text else 'N/A'}")

    await update.message.reply_text(
        "⚠️ 当前操作无法识别您的输入。\n"
        "请使用提供的按钮进行选择，或通过 /cancel 返回主菜单。",
        reply_markup=await get_main_keyboard()
    )


async def direct_add_torrent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    config: Config = context.bot_data['config']
    qb_manager: QBittorrentManager = context.bot_data['qb_manager']

    if config.TG_ALLOWED_CHAT_IDS and chat_id not in config.TG_ALLOWED_CHAT_IDS:
        await update.message.reply_text("抱歉，您无权执行此操作。")
        return

    if not context.args or len(context.args) == 0:
        await update.message.reply_html("请提供 M-Team 种子 ID。\n用法示例: <code>/add 966696</code>")
        return

    mt_id = context.args[0].strip()
    if not mt_id.isdigit():
        await update.message.reply_html(f"⚠️ M-Team ID “{html.escape(mt_id)}” 无效，ID应为纯数字。")
        return

    logger.info(f"🚀 用户 {user.id if user else 'Unknown'} 通过 /add 命令直接添加 M-Team ID: {mt_id}")

    processing_msg = await update.message.reply_html(
        f"🔄 正在添加 M-Team ID <code>{html.escape(mt_id)}</code> 到 qBittorrent...\n"
        f"将使用默认分类: {html.escape(config.QBIT_DEFAULT_CATEGORY_FOR_MT)}"
    )

    success, message = await qb_manager.add_mteam_torrent(mt_id, config.QBIT_DEFAULT_CATEGORY_FOR_MT)

    try:
        await processing_msg.edit_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=None,
            disable_web_page_preview=True
        )
    except telegram.error.TelegramError as e:
        logger.warning(f"编辑直接添加结果消息失败 ({e})，发送新消息。")
        await update.message.reply_html(
            message,
            reply_markup=await get_main_keyboard(),
            disable_web_page_preview=True
        )
    await update.message.reply_text("请选择下一步操作：", reply_markup=await get_main_keyboard())


async def post_init_hook(application: Application) -> None:
    commands = [
        BotCommand("start", "🚀 开始"),
				BotCommand("cancel", "🛑 取消当前操作"),
        BotCommand("add", "📥 添加下载任务"),
        BotCommand("listcats", "🗂️ 查看分类列表"),
        BotCommand("qbtasks", "📋 查看任务列表"),
        BotCommand("help", "💡 获取帮助信息")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info(f"机器人命令设置成功: {[cmd.command for cmd in commands]}")
    except Exception as e:
        logger.error(f"设置机器人命令失败: {e}")


def main_bot() -> None:
    try:
        config = Config()
    except SystemExit:
        return

    mteam_manager = MTeamManager(config)
    qb_manager = QBittorrentManager(config, mteam_manager)

    if not config.TG_BOT_TOKEN_MT:
        logger.critical("🚫 TG_BOT_TOKEN_MT 未在配置中找到! 机器人无法启动。")
        sys.exit("错误: Telegram Bot Token 未设置。")

    application_builder = Application.builder().token(config.TG_BOT_TOKEN_MT)
    application_builder.post_init(post_init_hook)
    app = application_builder.build()

    app.bot_data.update({
        'config': config,
        'qb_manager': qb_manager,
        'mteam_manager': mteam_manager
    })

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
                CallbackQueryHandler(handle_search_cancel, pattern=f"^{SEARCH_CANCEL_PREFIX}end_search"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("cancel", cancel_operation),
            CommandHandler("help", help_command),
            MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_conversation),
            MessageHandler(filters.Regex(f"^{CANCEL_OPT}$"), cancel_operation),
            MessageHandler(filters.TEXT, unknown_text_in_conversation)
        ],
        name="mteam_qb_main_conversation",
        persistent=False,
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("listcats", list_categories_command))
    app.add_handler(CommandHandler("qbtasks", qbtasks_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", direct_add_torrent_command))

    app.add_handler(conv_handler)

    app.add_handler(CallbackQueryHandler(qbtasks_page_callback, pattern=f"^{QBTASKS_PAGE_PREFIX}"))

    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("🤖 Telegram 机器人正在启动轮询...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("👋 Telegram 机器人已停止。")


if __name__ == "__main__":
    required_env_vars = ["MT_APIKEY", "TG_BOT_TOKEN_MT", "TG_ALLOWED_CHAT_IDS",
                         "QBIT_USERNAME", "QBIT_PASSWORD", "QBIT_HOST"]
    placeholders_detected = [var for var in required_env_vars if os.environ.get(var, "").startswith("your_")]

    if placeholders_detected:
        print("-" * 70)
        print("⚠️  警告: 检测到以下关键环境变量可能仍使用占位符值:")
        for var in placeholders_detected:
            print(f"   - {var}")
        print("   请确保已在您的环境中正确设置这些变量，否则机器人可能无法正常工作。")
        print("-" * 64)
        logger.warning(f"检测到占位符环境变量: {', '.join(placeholders_detected)}. 脚本将继续尝试运行。")

    main_bot()
