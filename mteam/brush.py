#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: brush.py
# 描述: 刷流脚本，自动从 MTeam 获取种子并添加到 qBittorrent。

import asyncio
import html
import json
import logging
import os
import random
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union

import pytz
import requests
from dateutil import parser as date_parser
# qbittorrentapi 相关导入，不再尝试导入 TorrentInfo
from qbittorrentapi import Client, LoginFailed, APIConnectionError, APIError, TorrentInfoList
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Config:
    """管理脚本的所有配置项。"""

    def __init__(self):
        logger.info("⚙️ 初始化配置...")

        self.QBIT_HOST: str = os.environ.get("QBIT_HOST", "localhost")
        self.QBIT_PORT: int = int(os.environ.get("QBIT_PORT", "8080"))
        self.QBIT_USERNAME: str = os.environ.get("QBIT_USERNAME", "admin")
        self.QBIT_PASSWORD: str = os.environ.get("QBIT_PASSWORD", "adminadmin")
        qbit_tags_str: str = os.environ.get("QBIT_TAGS", "刷流")
        self.QBIT_TAGS: List[str] = [tag.strip() for tag in qbit_tags_str.split(',') if tag.strip()]
        self.QBIT_CATEGORY: str = os.environ.get("QBIT_CATEGORY", "刷流")
        self.QBIT_SAVE_PATH: str = os.environ.get("QBIT_SAVE_PATH", "/vol1/1000/Media/MTBrush")

        self.MT_HOST: Optional[str] = os.environ.get("MT_HOST")
        self.MT_APIKEY: Optional[str] = os.environ.get("MT_APIKEY")
        self.MT_RSS_URL: Optional[str] = os.environ.get("MT_RSS_URL")

        self.TG_BOT_TOKEN: Optional[str] = os.environ.get("TG_BOT_TOKEN")
        self.TG_CHAT_ID: Optional[str] = os.environ.get("TG_CHAT_ID")

        self.DATA_FILE_PATH: str = os.environ.get("DATA_FILE_PATH", "mteam/flood_data.json")

        self.DISK_SPACE_LIMIT_GB: float = float(os.environ.get("DISK_SPACE_LIMIT_GB", 80))
        self.MAX_TORRENT_SIZE_GB: float = float(os.environ.get("MAX_TORRENT_SIZE_GB", 30))
        self.MIN_TORRENT_SIZE_GB: float = float(os.environ.get("MIN_TORRENT_SIZE_GB", 1))
        self.SEED_FREE_TIME_HOURS: int = int(os.environ.get("SEED_FREE_TIME_HOURS", 8))
        self.SEED_PUBLISH_BEFORE_HOURS: int = int(os.environ.get("SEED_PUBLISH_BEFORE_HOURS", 24))
        self.DOWNLOADERS_TO_SEEDERS_RATIO: float = float(os.environ.get("DOWNLOADERS_TO_SEEDERS_RATIO", 1.0))
        self.USE_IPV6_DOWNLOAD: bool = os.environ.get("USE_IPV6_DOWNLOAD", "False").lower() == 'true'

        self.MAX_UNFINISHED_DOWNLOADS: int = int(os.environ.get("MAX_UNFINISHED_DOWNLOADS", 50))

        self.API_REQUEST_DELAY_MIN: float = float(os.environ.get("API_REQUEST_DELAY_MIN", 1.5))
        self.API_REQUEST_DELAY_MAX: float = float(os.environ.get("API_REQUEST_DELAY_MAX", 3.5))

        self.SEED_FREE_TIME_SECONDS: int = self.SEED_FREE_TIME_HOURS * 3600
        self.SEED_PUBLISH_BEFORE_SECONDS: int = self.SEED_PUBLISH_BEFORE_HOURS * 3600

        self.TZ_INFOS: Dict[str, pytz.BaseTzInfo] = {"CST": pytz.timezone("Asia/Shanghai")}
        self.LOCAL_TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Asia/Shanghai")

        if not self.MT_HOST:
            self.MT_HOST = "https://api.m-team.cc"
            logger.info("MT_HOST 未在环境变量中设置，使用默认值: https://api.m-team.cc")

        self._validate_critical_configs()
        logger.info(f"👍 配置加载成功。未完成任务数限制: {self.MAX_UNFINISHED_DOWNLOADS}")

    def _validate_critical_configs(self):
        critical_missing = []
        if not self.MT_APIKEY:
            critical_missing.append("MTeam API密钥 (MT_APIKEY)")
        if not self.MT_RSS_URL:
            critical_missing.append("MTeam RSS订阅URL (MT_RSS_URL)")

        if critical_missing:
            error_msg = "、".join(critical_missing) + " 未设置。脚本无法运行。"
            logger.critical(f"🚫 {error_msg}")
            sys.exit(f"CRITICAL: {error_msg}")

        if not self.TG_BOT_TOKEN or not self.TG_CHAT_ID:
            logger.warning("⚠️ Telegram机器人Token (TG_BOT_TOKEN) 或频道ID (TG_CHAT_ID) 未配置。通知功能将不可用。")


class Utils:
    @staticmethod
    def convert_gb_to_bytes(gb_size: float) -> int:
        return int(gb_size * 1024 * 1024 * 1024)

    @staticmethod
    def format_size(size_bytes: Union[int, float]) -> str:
        if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
            if size_bytes == -1: return "N/A (RSS)"
            return "N/A"
        if size_bytes == 0: return "0 B"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        size = float(size_bytes)
        for unit in ["KiB", "MiB", "GiB", "TiB"]:
            size /= 1024
            if size < 1024:
                return f"{size:.2f} {unit}"
        return f"{size:.2f} PiB"

    @staticmethod
    def get_current_time_localized(local_timezone: pytz.BaseTzInfo) -> datetime:
        return datetime.now(local_timezone)

    @staticmethod
    async def random_delay_async(min_delay: float, max_delay: float):
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"⏳ 执行 {delay:.2f} 秒的异步随机延迟...")
        await asyncio.sleep(delay)


class QBittorrentManager:
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[Client] = None
        self._connect()

    def _connect(self) -> None:
        logger.info(f"🔗 尝试连接到 qBittorrent: {self.config.QBIT_HOST}:{self.config.QBIT_PORT}")
        conn_info = {
            "host": self.config.QBIT_HOST,
            "port": self.config.QBIT_PORT,
            "username": self.config.QBIT_USERNAME,
            "password": self.config.QBIT_PASSWORD,
            "REQUESTS_ARGS": {"timeout": (10, 30)}
        }
        try:
            self.client = Client(**conn_info)
            self.client.auth_log_in()
            logger.info(
                f"✅ 成功连接并登录到 qBittorrent (版本: {self.client.app.version}, API 版本: {self.client.app.web_api_version})")
        except LoginFailed as e:
            logger.critical(f"🚫 qBittorrent 登录失败: {e}. 请检查凭据。")
            self.client = None
            raise
        except APIConnectionError as e:
            logger.critical(f"🚫 无法连接到 qBittorrent ({self.config.QBIT_HOST}:{self.config.QBIT_PORT}): {e}")
            self.client = None
            raise
        except Exception as e:
            logger.critical(f"🚫 创建 qBittorrent 客户端时发生未知错误 ({type(e).__name__}): {e}")
            self.client = None
            raise

    def disconnect(self) -> None:
        if self.client and self.client.is_logged_in:
            try:
                self.client.auth_log_out()
                logger.info("🔌 已成功从 qBittorrent 注销。")
            except Exception as e:
                logger.error(f"⚠️ 从 qBittorrent 注销时发生错误: {e}")
        self.client = None

    def get_free_disk_space(self) -> Optional[int]:
        if not self.client or not self.client.is_logged_in: return None
        try:
            main_data = self.client.sync_maindata()
            if main_data and hasattr(main_data.server_state, 'free_space_on_disk'):
                free_space = main_data.server_state.free_space_on_disk
                logger.info(f"💾 获取到磁盘剩余空间: {Utils.format_size(free_space)}")
                return free_space
            logger.warning("⚠️ 无法从 qBittorrent 获取 server_state 或 free_space_on_disk。")
            return None
        except Exception as e:
            logger.error(f"⚠️ 获取磁盘剩余空间时出错: {e}")
            return None

    def get_unfinished_torrents_count(self) -> Optional[int]:
        """获取所有未完成（进度 < 100%）的种子数量。"""
        if not self.client or not self.client.is_logged_in:
            logger.warning("⚠️ qBittorrent 客户端未连接，无法获取未完成任务数。")
            return None
        try:
            # torrents_info() 返回 TorrentInfoList 对象，它本身可迭代，其元素是类字典对象
            torrents: Optional[TorrentInfoList] = self.client.torrents_info(status_filter='all')
            unfinished_count = 0
            if torrents:
                for torrent in torrents:  # 此处的 torrent 是一个类字典对象，可以直接访问属性
                    if torrent.progress < 1.0:
                        unfinished_count += 1
            logger.info(f"📊 qBittorrent 中当前未完成的下载任务数量: {unfinished_count}")
            return unfinished_count
        except APIError as e:
            logger.error(f"🚫 获取 qBittorrent 未完成任务数时 API 出错: {e}")
            return None
        except Exception as e:
            logger.error(f"🚫 获取 qBittorrent 未完成任务数时发生意外错误 ({type(e).__name__}): {e}")
            return None

    def add_torrent_by_url(self, torrent_url: str, rename_value: Optional[str] = None) -> bool:
        if not self.client or not self.client.is_logged_in: return False
        params = {
            'urls': torrent_url,
            'save_path': self.config.QBIT_SAVE_PATH,
            'category': self.config.QBIT_CATEGORY,
            'tags': self.config.QBIT_TAGS,
            'paused': False,
            'sequentialDownload': True,
            'firstLastPiecePrio': True,
        }
        if rename_value: params['rename'] = rename_value

        log_name = rename_value if rename_value else torrent_url[:70] + "..."
        logger.info(f"➕ 准备向 qBittorrent 添加种子: '{log_name}'")
        try:
            response_ok = self.client.torrents_add(**params)
            if response_ok == "Ok." or response_ok is True:
                logger.info(f"👍 种子 '{log_name}' 添加请求已成功发送到 qBittorrent。")
                return True
            else:
                torrents_info_list: Optional[TorrentInfoList] = self.client.torrents_info(
                    status_filter='all', category=self.config.QBIT_CATEGORY
                )
                if torrents_info_list:
                    url_torrent_file_part_match = re.search(r'/([^/?]+\.torrent)', torrent_url)
                    url_identifier_for_check = url_torrent_file_part_match.group(
                        1) if url_torrent_file_part_match else torrent_url

                    for torrent_info_item in torrents_info_list:  # torrent_info_item 是类字典对象
                        if (rename_value and torrent_info_item.name == rename_value) or \
                                (torrent_info_item.name in url_identifier_for_check):
                            logger.info(
                                f"ℹ️ 种子 '{log_name}' 添加请求未明确成功，但似乎已存在于下载列表中 (名称匹配: {torrent_info_item.name})。")
                            return True
                logger.warning(
                    f"🤔 种子 '{log_name}' 添加请求未明确成功 ({response_ok})，且未在列表中找到。qBittorrent 可能拒绝了它。")
                return False
        except APIError as e:
            if "torrent is already in the download list" in str(e).lower() or \
                    ("failed to add torrent" in str(e).lower() and "already present" in str(e).lower()) or \
                    ("already in the session" in str(e).lower()):
                logger.info(f"ℹ️ 种子 '{log_name}' 已存在于下载列表中 (APIError: {e})。")
                return True
            logger.error(f"🚫 通过 URL 添加种子 '{log_name}' 时 API 出错: {e}")
            return False
        except Exception as e:
            logger.error(f"🚫 通过 URL 添加种子 '{log_name}' 时发生意外错误 ({type(e).__name__}): {e}")
            return False


class TelegramNotifier:
    def __init__(self, config: Config):
        self.config = config
        self.bot: Optional[Bot] = None
        if self.config.TG_BOT_TOKEN and self.config.TG_CHAT_ID:
            try:
                self.bot = Bot(token=self.config.TG_BOT_TOKEN)
                logger.info("🤖 Telegram机器人已成功初始化。")
            except Exception as e:
                logger.error(f"🚫 初始化Telegram机器人失败: {e}")
                self.bot = None
        else:
            logger.warning("⚠️ Telegram BOT_TOKEN 或 CHAT_ID 未配置。")

    @staticmethod
    def _escape_html(text: str) -> str:
        if not isinstance(text, str): return ""
        return html.escape(text, quote=True)

    async def send_message(self, message: str, use_html: bool = True) -> None:
        if not self.bot or not self.config.TG_CHAT_ID:
            logger.debug(f"💬 Telegram通知跳过 (未配置)。消息: {message[:100]}...")
            return
        try:
            chat_id_int = int(self.config.TG_CHAT_ID)
            max_len = 4000
            if use_html and len(message) > max_len:
                logger.warning(f"Telegram 消息过长 ({len(message)} > {max_len})，将被截断。")
                safe_cutoff = message.rfind('\n', 0, max_len - 30)
                if safe_cutoff == -1: safe_cutoff = max_len - 30
                message = message[:safe_cutoff] + "\n... (消息过长被截断)"

            await self.bot.send_message(
                chat_id=chat_id_int, text=message,
                parse_mode=ParseMode.HTML if use_html else None,
                disable_web_page_preview=True
            )
            log_msg_preview = message.replace('\n', ' ')[:100]
            logger.info(f"✅ Telegram消息发送成功 (前100字符): {log_msg_preview}")
        except ValueError:
            logger.error(f"🚫 无效的Telegram频道ID: '{self.config.TG_CHAT_ID}'。请确保它是一个有效的数字。")
        except TelegramError as e:
            logger.error(f"🚫 Telegram消息发送失败: {e}")
        except Exception as e:
            logger.error(f"🚫 发送Telegram消息时意外错误 ({type(e).__name__}): {e}")

    def format_bulk_torrent_add_success(self, added_torrents: List[Dict[str, Any]],
                                        duration_seconds: Optional[float]) -> str | None:
        if not added_torrents:
            logger.info(f"🤷 MTeam刷流脚本：本轮运行未添加任何新种子。\n⏱️ 任务耗时: {duration_seconds:.2f} 秒")
            return None

        count = len(added_torrents)
        message_lines = [
            f"<b>🎉 MTeam刷流脚本：本轮成功添加 {count} 个新种子！</b>",
            "🌸➖➖➖➖➖➖➖➖🌸"
        ]
        for torrent_info_dict in added_torrents:  # Renamed for clarity
            name = self._escape_html(torrent_info_dict.get("name", "N/A"))
            renamed_to = self._escape_html(torrent_info_dict.get("renamed_to", "N/A"))
            size_str = Utils.format_size(torrent_info_dict.get("size_bytes", 0))
            discount = self._escape_html(torrent_info_dict.get("discount", "N/A"))
            ls_ratio = self._escape_html(torrent_info_dict.get("ls_ratio", "N/A"))
            mteam_id = torrent_info_dict.get("mteam_id", "")
            detail_url = f"https://kp.m-team.cc/detail/{mteam_id}" if mteam_id else "#"

            entry = (
                f"🔗 <a href='{detail_url}'><b>{name[:60]}...</b></a>\n"
                f"↳ 🏷️ {renamed_to[:60]}...\n"
                f"  💾 {size_str} | 🎁 {discount} | 📊 {ls_ratio}"
            )
            message_lines.append(entry)
            message_lines.append("🌸➖➖➖➖➖➖➖➖🌸")

        if duration_seconds is not None:
            message_lines.append(f"⏱️ <b>任务总耗时:</b> {duration_seconds:.2f} 秒")
        return "\n".join(message_lines)

    def format_script_status(self, status: str, details: Optional[str] = None) -> str | None:
        if status == "start":
            logger.info(f"🚀 MTeam刷流脚本: 任务已启动，等待添加种子 ... ")
            return None
        elif status == "error":
            escaped_details = self._escape_html(details) if details else "未知错误"
            return f"<b>☠️ MTeam刷流脚本:</b> 严重错误 - {escaped_details}。脚本中止。"
        elif status == "warning_disk_space":
            escaped_details = self._escape_html(details) if details else "磁盘空间不足"
            return f"<b>📉 MTeam刷流脚本警告:</b> {escaped_details}"
        return self._escape_html(status)

    @staticmethod
    def format_max_unfinished_torrents_warning(count: int, limit: int) -> str:
        return (f"<b>⚠️ MTeam刷流脚本警告:</b>\n\n"
                f"检测到 qBittorrent 中未完成的下载任务数量 (<b>{count}</b>) "
                f"已超过设定的限制 (<b>{limit}</b>)。\n\n"
                f"为了避免 qBittorrent 负载过高，本轮刷流操作已暂停，将不会添加新的种子。\n"
                f"请检查 qBittorrent 中的任务情况。")


class MTeamManager:
    def __init__(self, config: Config):
        self.config = config
        if not self.config.MT_APIKEY or not self.config.MT_HOST:
            logger.critical("🚫 MTeam API密钥或主机未配置。")
            raise ValueError("MTeam API Key or Host not configured.")
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.config.MT_APIKEY})
        logger.info("🔑 MTeam API会话已配置。")

    def get_torrent_details(self, torrent_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.config.MT_HOST}/api/torrent/detail"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data:
                logger.warning(f"⚠️ MTeam API报告种子 {torrent_id} 问题: {data.get('message', '未知错误')}.")
                return None

            torrent_data = data["data"]
            details = {
                "name": torrent_data.get("name"), "size": int(torrent_data.get("size", 0)),
                "discount": torrent_data.get("status", {}).get("discount"),
                "discount_end_time_str": torrent_data.get("status", {}).get("discountEndTime"),
                "seeders": int(torrent_data.get("status", {}).get("seeders", 0)),
                "leechers": int(torrent_data.get("status", {}).get("leechers", 0)),
                "discount_end_time": None
            }
            if not details["name"] or details["size"] is None:
                logger.warning(f"⚠️ 种子 {torrent_id} 缺少名称或大小信息。")
                return None
            if details["discount_end_time_str"]:
                try:
                    dt_naive = datetime.strptime(details["discount_end_time_str"], "%Y-%m-%d %H:%M:%S")
                    details["discount_end_time"] = self.config.LOCAL_TIMEZONE.localize(dt_naive)
                except ValueError:
                    logger.debug(f"无法解析种子 {torrent_id} 的优惠结束时间 '{details['discount_end_time_str']}'。")
            return details
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 获取MTeam种子ID {torrent_id} 详细信息失败: {e}.")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"🚫 解析MTeam种子ID {torrent_id} 详细信息失败: {e}.")
        return None

    def get_torrent_download_url(self, torrent_id: str) -> str or None:
        url = f"{self.config.MT_HOST}/api/torrent/genDlToken"
        try:
            response = self.session.post(url, data={"id": torrent_id}, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("message", "").upper() != 'SUCCESS' or "data" not in data or not data["data"]:
                logger.warning(f"⚠️ MTeam API无法为种子 {torrent_id} 生成下载URL: {data.get('message', '无令牌')}.")
                return None

            token_url_part = data["data"]
            if "?" in token_url_part:
                base_url, params_str = token_url_part.split("?", 1)
            else:
                base_url = token_url_part
                params_str = ""

            params = dict(p.split("=", 1) for p in params_str.split("&") if "=" in p) if params_str else {}
            params["useHttps"] = "true"
            params["type"] = "ipv6" if self.config.USE_IPV6_DOWNLOAD else "ipv4"

            final_url = base_url
            if params:
                final_url += "?" + '&'.join([f'{k}={v}' for k, v in params.items()])
            return final_url
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 获取MTeam种子ID {torrent_id} 下载URL失败: {e}.")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"🚫 解析MTeam种子ID {torrent_id} 下载URL失败: {e}.")
        return None

    def get_rss_feed_items(self) -> List[Dict[str, Any]]:
        if not self.config.MT_RSS_URL:
            logger.error("🚫 MTeam RSS URL 未配置。")
            return []
        logger.info(f"📰 正在从 RSS 订阅源获取项目: {self.config.MT_RSS_URL[:100]}...")
        try:
            response = self.session.get(self.config.MT_RSS_URL, timeout=45)
            response.raise_for_status()

            xml_content = response.text
            xml_content = "".join(
                ch for ch in xml_content if unicodedata.category(ch)[0] != "C" or ch in ('\t', '\n', '\r'))

            root = ET.fromstring(xml_content)
            rss_items = []
            for item_element in root.findall(".//item"):
                try:
                    link = item_element.findtext("link")
                    if not link: continue
                    torrent_id_match = re.search(r"(?:id=|detail/)(\d+)", link)
                    if not torrent_id_match: continue
                    torrent_id = torrent_id_match.group(1)

                    title = item_element.findtext("title", "N/A")
                    pub_date_str = item_element.findtext("pubDate")
                    if not pub_date_str: continue

                    bracketed_parts = re.findall(r'\[([^]]*)]', title)
                    category_rss, subtitle_rss = None, None
                    if len(bracketed_parts) >= 1: category_rss = bracketed_parts[0].strip().replace("/", "-")

                    if len(bracketed_parts) >= 2:
                        potential_subtitle = bracketed_parts[1].strip()
                        tech_spec_pattern = r'\b(?:\d{3,4}p|x26[45]|HEVC|AVC|DTS|HDR|REMUX|BluRay|WEB-DL|\d+(\.\d+)?\s*(GB|MB|TB))\b'
                        if not re.search(tech_spec_pattern, potential_subtitle, re.IGNORECASE):
                            subtitle_rss = potential_subtitle
                        elif len(bracketed_parts) >= 3:
                            potential_subtitle_2 = bracketed_parts[2].strip()
                            if not re.search(tech_spec_pattern, potential_subtitle_2, re.IGNORECASE):
                                subtitle_rss = potential_subtitle_2

                    size_bytes = -1
                    enclosure = item_element.find("enclosure")
                    if enclosure is not None and enclosure.get("length"):
                        try:
                            size_bytes = int(enclosure.get("length"))
                        except ValueError:
                            logger.debug(f"RSS item {torrent_id}: Invalid size in enclosure: {enclosure.get('length')}")

                    if size_bytes == -1 and bracketed_parts:
                        last_bracket_content = bracketed_parts[-1]
                        size_match = re.search(r"(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB|PB)",
                                               last_bracket_content.replace("，", ","), re.IGNORECASE)
                        if size_match:
                            try:
                                size_value = float(size_match.group(1))
                                unit_multipliers = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3,
                                                    "TB": 1024 ** 4, "PB": 1024 ** 5}
                                size_unit = size_match.group(2).upper()
                                if size_unit in unit_multipliers:
                                    size_bytes = int(size_value * unit_multipliers[size_unit])
                            except ValueError:
                                logger.debug(
                                    f"RSS item {torrent_id}: Invalid size in title bracket: {last_bracket_content}")

                    rss_items.append({
                        "id": torrent_id, "title": title, "publish_time_str": pub_date_str,
                        "size_bytes_rss": size_bytes, "category_rss": category_rss, "subtitle_rss": subtitle_rss,
                    })
                except Exception as e:
                    logger.warning(
                        f"⚠️ 解析RSS项目时出错: {e}. 项目标题: '{item_element.findtext('title', 'N/A')[:50]}...'. 跳过此项目。")
            logger.info(f"📊 从RSS订阅源解析到 {len(rss_items)} 个项目。")
            return rss_items
        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 获取MTeam RSS订阅源失败: {e}.")
        except ET.ParseError as e:
            logger.error(f"🚫 解析MTeam RSS XML失败: {e}")
        except Exception as e:
            logger.error(f"🚫 处理RSS订阅源时发生未知错误: {e}")
        return []


class DataManager:
    def __init__(self, config: Config):
        self.config = config
        self.file_path = self.config.DATA_FILE_PATH

    def load_processed_torrents(self) -> List[Dict[str, Any]]:
        logger.info(f"📂 尝试从 {self.file_path} 加载已处理的种子数据...")
        if not os.path.exists(self.file_path):
            logger.info(f"ℹ️ 数据文件 {self.file_path} 不存在，将创建新的。")
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.warning(f"⚠️ {self.file_path} 中的数据不是列表格式。将尝试备份并视为空。")
                self._backup_corrupted_file()
                return []
            valid_records = []
            for r in data:
                if isinstance(r, dict) and "id" in r:
                    valid_records.append(r)
                else:
                    logger.warning(f"⚠️ 在 {self.file_path} 中发现无效记录: {str(r)[:100]}... 已跳过。")
            logger.info(f"✅ 成功从 {self.file_path} 加载 {len(valid_records)} 条有效记录。")
            return valid_records
        except json.JSONDecodeError as e:
            logger.error(f"🚫 从 {self.file_path} 解码JSON出错: {e}。将尝试备份并视为空。")
            self._backup_corrupted_file()
        except IOError as e:
            logger.error(f"🚫 无法读取文件 {self.file_path}: {e}。")
        except Exception as e:
            logger.error(f"🚫 加载数据时意外错误 ({type(e).__name__}): {e}。")
        return []

    def _backup_corrupted_file(self):
        """
        备份损坏的数据文件。
        新的策略是只保留一个名为 <file_path>.backup 的备份文件。
        """
        if not os.path.exists(self.file_path):
            logger.debug(f"🐛 _backup_corrupted_file 调用时文件 {self.file_path} 不存在，无需备份。")
            return

        backup_path = self.file_path + ".backup"

        try:
            logger.info(f"🔄 准备将损坏的文件 {self.file_path} 备份为 {backup_path}。")

            if os.path.exists(backup_path):
                try:
                    if os.path.isdir(backup_path):
                        logger.error(f"🚫 目标备份路径 {backup_path} 是一个目录，无法作为备份文件。请手动检查并移除。")
                        return
                    os.remove(backup_path)
                    logger.info(f"🗑️ 已移除旧的备份文件: {backup_path}。")
                except OSError as rm_err:
                    logger.error(f"⚠️ 无法移除已存在的备份文件 {backup_path}: {rm_err}。继续尝试重命名原文件。")

            os.rename(self.file_path, backup_path)
            logger.info(
                f"✅ 已将损坏的数据文件 (原路径: {self.file_path}) 备份到 {backup_path}。现在最多只有一个备份文件。")

        except OSError as bak_err:
            logger.error(f"🚫 无法将 {self.file_path} 重命名/备份到 {backup_path}: {bak_err}")
        except Exception as e:
            logger.error(f"💥 备份文件 {self.file_path} 时发生未知错误 ({type(e).__name__}): {e}")

    def save_processed_torrents(self, torrents_data: List[Dict[str, Any]]) -> None:
        logger.info(f"💾 正在将 {len(torrents_data)} 条记录保存到 {self.file_path}...")
        try:
            dir_name = os.path.dirname(self.file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(torrents_data, f, ensure_ascii=False, indent=4)
            logger.info(f"✅ 数据成功保存到 {self.file_path}。")
        except IOError as e:
            logger.error(f"🚫 保存数据到文件 {self.file_path} 时发生IO错误: {e}")
        except Exception as e:
            logger.error(f"🚫 保存数据时意外错误 ({type(e).__name__}): {e}")


class TorrentProcessor:
    def __init__(self, config: Config, qbit_manager: QBittorrentManager,
                 mteam_manager: MTeamManager, notifier: TelegramNotifier,
                 data_manager: DataManager):
        self.config = config
        self.qbit_manager = qbit_manager
        self.mteam_manager = mteam_manager
        self.notifier = notifier
        self.data_manager = data_manager
        self.processed_torrents: List[Dict[str, Any]] = []
        self.successfully_added_torrents_info: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__class__.__name__)

    @staticmethod
    def _generate_torrent_rename_name(torrent_id: str, rss_item: Dict[str, Any],
                                      api_details: Dict[str, Any]) -> str:
        category_rss = rss_item.get('category_rss')
        subtitle_rss = rss_item.get('subtitle_rss')
        rss_title_original = rss_item.get('title', '')
        api_torrent_name = api_details.get("name", "未知名称")
        rename_parts = [f"[{torrent_id}]"]

        if category_rss:
            cleaned_category = re.sub(r'[\\/*?:"<>|]', '', category_rss)[:60].strip()
            if cleaned_category:
                rename_parts.append(f"[{cleaned_category}]")

        supplement_part = ""
        if subtitle_rss:
            temp_subtitle = subtitle_rss.replace(' ', '.')
            supplement_part = re.sub(r'[\\/*?:"<>|]', '', temp_subtitle)[:72].strip()
        elif rss_title_original:
            clean_rss_title = rss_title_original
            if category_rss:
                clean_rss_title = clean_rss_title.replace(f"[{rss_item.get('category_rss')}]", "")
            clean_rss_title = re.sub(r'\[.*?]', '', clean_rss_title).strip()
            clean_rss_title = re.sub(r'\(.*?\)', '', clean_rss_title).strip()
            title_elements = clean_rss_title.split('-')
            if len(title_elements) > 1 and title_elements[-1].isalpha() and len(title_elements[-1]) < 10:
                clean_rss_title = "-".join(title_elements[:-1]).strip()
            else:
                clean_rss_title = clean_rss_title.strip()
            if clean_rss_title:
                temp_title_part = clean_rss_title.replace(' ', '.')
                supplement_part = re.sub(r'[\\/*?:"<>|]', '', temp_title_part)[:72].strip()
        if supplement_part:
            rename_parts.append(f"[{supplement_part}]")

        if len(rename_parts) <= ("Category" in str(rename_parts)) + 1 and api_torrent_name:
            name_part_match = re.match(r'^([^\[]+)', api_torrent_name)
            name_part_for_rename = name_part_match.group(1).strip() if name_part_match else api_torrent_name.strip()
            name_part_for_rename = re.sub(r'[\\/*?:"<>|]', '', name_part_for_rename)
            name_part_for_rename = name_part_for_rename.replace(' ', '.')[:50].strip()
            if name_part_for_rename and name_part_for_rename.lower() not in "".join(rename_parts).lower():
                rename_parts.append(f"[{name_part_for_rename}]")

        rename_value = "".join(rename_parts)
        rename_value = rename_value.replace("][", "][")
        rename_value = re.sub(r'\.+', '.', rename_value)
        rename_value = rename_value.strip('. ')

        test_val = rename_value.replace(f"[{torrent_id}]", "").replace("[]", "").strip(" .")
        if not test_val:
            fallback_api_name = re.sub(r'[\\/*?:"<>|]', '', api_torrent_name).replace(' ', '.')[:60].strip(".-_ ")
            rename_value = f"[{torrent_id}][{fallback_api_name}]"
        return rename_value[:200]

    async def run(self) -> int:
        self.logger.info("🚀 开始执行刷流处理任务...")
        self.processed_torrents = self.data_manager.load_processed_torrents()
        self.successfully_added_torrents_info.clear()

        if not self.qbit_manager.client or not self.qbit_manager.client.is_logged_in:
            self.logger.error("🚫 qBittorrent 客户端不可用。脚本无法继续。")
            return 0

        unfinished_downloads_count = self.qbit_manager.get_unfinished_torrents_count()
        if unfinished_downloads_count is None:
            self.logger.warning("⚠️ 无法获取qBittorrent未完成任务数，将跳过此检查并继续。")
        elif unfinished_downloads_count > self.config.MAX_UNFINISHED_DOWNLOADS:
            run_warning_msg = (f"qBittorrent中未完成的下载任务数量 ({unfinished_downloads_count}) "
                               f"已超过设定的限制 ({self.config.MAX_UNFINISHED_DOWNLOADS})。")
            self.logger.warning(f"🚦 {run_warning_msg} 本轮刷流将暂停。")
            await self.notifier.send_message(
                self.notifier.format_max_unfinished_torrents_warning(unfinished_downloads_count,
                                                                     self.config.MAX_UNFINISHED_DOWNLOADS)
            )
            self.data_manager.save_processed_torrents(self.processed_torrents)
            return 0

        current_disk_space = self.qbit_manager.get_free_disk_space()
        if current_disk_space is None:
            self.logger.error("🚫 无法确定磁盘空间。脚本无法继续。")
            await self.notifier.send_message(self.notifier.format_script_status("error", details="无法获取磁盘空间"))
            self.data_manager.save_processed_torrents(self.processed_torrents)
            return 0

        space_limit_bytes = Utils.convert_gb_to_bytes(self.config.DISK_SPACE_LIMIT_GB)
        if current_disk_space <= space_limit_bytes:
            msg = f"初始磁盘空间 ({Utils.format_size(current_disk_space)}) 已低于限制 ({Utils.format_size(space_limit_bytes)})。添加新种子失败。"
            self.logger.warning(f"📉 {msg}")
            await self.notifier.send_message(self.notifier.format_script_status("warning_disk_space", details=msg))
            self.data_manager.save_processed_torrents(self.processed_torrents)
            return 0

        rss_items = self.mteam_manager.get_rss_feed_items()
        if not rss_items:
            self.logger.info("ℹ️ RSS订阅源中未找到项目或加载失败。")
            self.data_manager.save_processed_torrents(self.processed_torrents)
            return 0

        min_size_bytes = Utils.convert_gb_to_bytes(self.config.MIN_TORRENT_SIZE_GB)
        max_size_bytes = Utils.convert_gb_to_bytes(self.config.MAX_TORRENT_SIZE_GB)
        now_localized = Utils.get_current_time_localized(self.config.LOCAL_TIMEZONE)

        for item in rss_items:
            torrent_id = item["id"]
            self.logger.debug(f"🔍 处理RSS项目: ID={torrent_id}, 标题='{item.get('title', 'N/A')[:60]}...'")

            if any(str(p_torrent.get("id")) == str(torrent_id) for p_torrent in self.processed_torrents):
                self.logger.debug(f"✅ 种子ID {torrent_id}: 已处理过，跳过。")
                continue

            try:
                publish_time_naive = date_parser.parse(item["publish_time_str"], tzinfos=self.config.TZ_INFOS)
                if publish_time_naive.tzinfo is None or publish_time_naive.tzinfo.utcoffset(publish_time_naive) is None:
                    publish_time_aware = self.config.LOCAL_TIMEZONE.localize(publish_time_naive)
                else:
                    publish_time_aware = publish_time_naive.astimezone(self.config.LOCAL_TIMEZONE)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ 种子ID {torrent_id}: 解析发布时间 '{item.get('publish_time_str')}' 失败: {e}。跳过。")
                continue

            if (now_localized - publish_time_aware).total_seconds() > self.config.SEED_PUBLISH_BEFORE_SECONDS:
                self.logger.debug(
                    f"⏰ 种子ID {torrent_id}: 发布时间 ({publish_time_aware}) 过早，已超过 {self.config.SEED_PUBLISH_BEFORE_HOURS} 小时限制。跳过。")
                continue

            rss_torrent_size = item.get("size_bytes_rss", -1)
            if rss_torrent_size > 0:
                if not (min_size_bytes <= rss_torrent_size <= max_size_bytes):
                    self.logger.debug(
                        f"📏 种子ID {torrent_id}: RSS大小 {Utils.format_size(rss_torrent_size)} 超出范围 "
                        f"({Utils.format_size(min_size_bytes)} - {Utils.format_size(max_size_bytes)})。跳过。")
                    continue
                if (current_disk_space - rss_torrent_size) < space_limit_bytes:
                    self.logger.debug(
                        f"📉 种子ID {torrent_id}: RSS大小 {Utils.format_size(rss_torrent_size)} 将导致磁盘空间 "
                        f"({Utils.format_size(current_disk_space - rss_torrent_size)}) 低于限制 "
                        f"({Utils.format_size(space_limit_bytes)})。跳过。")
                    continue

            await Utils.random_delay_async(self.config.API_REQUEST_DELAY_MIN, self.config.API_REQUEST_DELAY_MAX)
            details = self.mteam_manager.get_torrent_details(torrent_id)
            if not details:
                self.logger.warning(f"⚠️ 种子ID {torrent_id}: 获取MTeam详细信息失败。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "api_detail_failed", "time": now_localized.isoformat()})
                continue

            api_torrent_name = details.get("name", "未知名称")
            api_torrent_size = details.get("size", 0)
            if api_torrent_size == 0:
                self.logger.warning(f"⚠️ 种子ID {torrent_id} ({api_torrent_name}): API返回大小为0，可能无效，跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "api_zero_size", "time": now_localized.isoformat()})
                continue

            if not (min_size_bytes <= api_torrent_size <= max_size_bytes):
                self.logger.debug(
                    f"📏 种子ID {torrent_id} ({api_torrent_name}): API大小 {Utils.format_size(api_torrent_size)} "
                    f"不符合大小范围 ({Utils.format_size(min_size_bytes)} - {Utils.format_size(max_size_bytes)})。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "size_mismatch_api", "time": now_localized.isoformat()})
                continue

            if (current_disk_space - api_torrent_size) < space_limit_bytes:
                self.logger.info(
                    f"📉 种子ID {torrent_id} ({api_torrent_name}): API大小 {Utils.format_size(api_torrent_size)} "
                    f"将导致磁盘空间不足。剩余: {Utils.format_size(current_disk_space)}, 限制: {Utils.format_size(space_limit_bytes)}。")
                if not self.successfully_added_torrents_info:
                    await self.notifier.send_message(self.notifier.format_script_status("warning_disk_space",
                                                                                        details=f"尝试添加 {api_torrent_name} ({Utils.format_size(api_torrent_size)}) 将导致空间不足。剩余空间检查无法通过。"))
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "disk_space_insufficient_api", "time": now_localized.isoformat()})
                continue

            torrent_discount = details.get("discount", "UNKNOWN")
            if torrent_discount not in ["FREE", "_2X_FREE"]:
                self.logger.debug(f"💰 种子ID {torrent_id} ({api_torrent_name}): 非免费 ({torrent_discount})。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "not_free", "time": now_localized.isoformat()})
                continue

            if details.get("discount_end_time"):
                min_required_free_end_time = now_localized + timedelta(seconds=self.config.SEED_FREE_TIME_SECONDS)
                if details["discount_end_time"] < min_required_free_end_time:
                    self.logger.debug(
                        f"⏳ 种子ID {torrent_id} ({api_torrent_name}): 免费时间 ({details['discount_end_time']}) "
                        f"不足 {self.config.SEED_FREE_TIME_HOURS} 小时。跳过。")
                    self.processed_torrents.append(
                        {"id": torrent_id, "status": "free_time_insufficient", "time": now_localized.isoformat()})
                    continue

            seeders = details.get("seeders", 0)
            leechers = details.get("leechers", 0)
            if seeders <= 0:
                self.logger.debug(f"🌱 种子ID {torrent_id} ({api_torrent_name}): 无(或0)做种者 ({seeders})。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "no_seeders", "time": now_localized.isoformat()})
                continue

            current_ls_ratio = (leechers / seeders) if seeders > 0 else float('inf')
            if current_ls_ratio < self.config.DOWNLOADERS_TO_SEEDERS_RATIO:
                self.logger.debug(
                    f"📊 种子ID {torrent_id} ({api_torrent_name}): L/S比例 ({leechers}/{seeders} = {current_ls_ratio:.2f}) "
                    f"低于设定阈值 {self.config.DOWNLOADERS_TO_SEEDERS_RATIO}。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "ls_ratio_low", "time": now_localized.isoformat()})
                continue

            ls_ratio_str = f"{leechers}/{seeders} = {current_ls_ratio:.2f}"
            self.logger.info(
                f"🎉 种子ID {torrent_id} ({api_torrent_name}): 条件满足，准备下载。L/S: {ls_ratio_str}, 大小: {Utils.format_size(api_torrent_size)}")

            rename_value = self._generate_torrent_rename_name(torrent_id, item, details)
            self.logger.info(f"ℹ️ 种子ID {torrent_id}: 计划重命名为 '{rename_value}'")

            await Utils.random_delay_async(self.config.API_REQUEST_DELAY_MIN, self.config.API_REQUEST_DELAY_MAX)
            download_url = self.mteam_manager.get_torrent_download_url(torrent_id)
            if not download_url:
                self.logger.warning(f"⚠️ 种子ID {torrent_id} ({api_torrent_name}): 获取下载链接失败。跳过。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "download_url_failed", "time": now_localized.isoformat()})
                continue

            if self.qbit_manager.add_torrent_by_url(download_url, rename_value=rename_value):
                self.logger.info(f"✅ 已成功为种子ID {torrent_id} ({api_torrent_name}) 发起下载。")
                self.successfully_added_torrents_info.append({
                    "mteam_id": torrent_id, "name": api_torrent_name, "renamed_to": rename_value,
                    "size_bytes": api_torrent_size, "discount": torrent_discount, "ls_ratio": ls_ratio_str
                })
                self.processed_torrents.append({
                    "id": torrent_id, "name": api_torrent_name,
                    "renamed_name_in_qb": rename_value,
                    "added_time": now_localized.isoformat(),
                    "size_bytes": api_torrent_size,
                    "status": "added_to_qb"
                })
                current_disk_space -= api_torrent_size

                if current_disk_space <= space_limit_bytes:
                    msg = (f"添加种子 '{api_torrent_name}' ({Utils.format_size(api_torrent_size)}) 后，"
                           f"磁盘空间 ({Utils.format_size(current_disk_space)}) 已低于限制 ({Utils.format_size(space_limit_bytes)})。"
                           f"停止添加更多种子。")
                    self.logger.info(f"📉 {msg}")
                    await self.notifier.send_message(
                        self.notifier.format_script_status("warning_disk_space", details=msg))
                    break
            else:
                self.logger.error(f"🚫 种子ID {torrent_id} ({api_torrent_name}): 添加到qBittorrent失败。")
                self.processed_torrents.append(
                    {"id": torrent_id, "status": "qb_add_failed", "time": now_localized.isoformat()})

        final_processed_map = {}
        for record in self.processed_torrents:
            existing_record = final_processed_map.get(record['id'])
            if not existing_record or \
                    (record.get('status') == 'added_to_qb' and existing_record.get('status') != 'added_to_qb') or \
                    (record.get('time', '') > existing_record.get('time', '')):
                final_processed_map[record['id']] = record
        self.processed_torrents = list(final_processed_map.values())

        self.data_manager.save_processed_torrents(self.processed_torrents)
        return len(self.successfully_added_torrents_info)


async def main():
    script_start_time = time.monotonic()
    logger.info(f"🏁 ===== 脚本执行开始: {datetime.now(pytz.utc).isoformat()} =====")

    notifier_instance: Optional[TelegramNotifier] = None
    qbit_manager_instance: Optional[QBittorrentManager] = None
    exit_code = 0

    try:
        config_instance = Config()
        notifier_instance = TelegramNotifier(config_instance)
        # await notifier_instance.send_message(notifier_instance.format_script_status("start"))
        qbit_manager_instance = QBittorrentManager(config_instance)
        if not qbit_manager_instance.client:
            raise ConnectionError("qBittorrent 客户端初始化失败或未连接。")

        mteam_manager = MTeamManager(config_instance)
        data_manager = DataManager(config_instance)
        processor = TorrentProcessor(config_instance, qbit_manager_instance, mteam_manager, notifier_instance,
                                     data_manager)
        num_added = await processor.run()

        duration = time.monotonic() - script_start_time
        summary_message = notifier_instance.format_bulk_torrent_add_success(
            processor.successfully_added_torrents_info, duration
        )
        if summary_message:
            await notifier_instance.send_message(summary_message)

        if num_added == 0 and not processor.successfully_added_torrents_info:
            logger.info("ℹ️ 本轮未添加任何新种子。")
        else:
            logger.info(f"✅ 本轮成功添加 {num_added} 个新种子。")

    except (LoginFailed, APIConnectionError, ConnectionError) as e:
        logger.critical(f"🚫 qBittorrent 连接或登录失败: {e}。脚本中止。")
        if notifier_instance: await notifier_instance.send_message(
            notifier_instance.format_script_status("error", details=f"qBittorrent连接问题: {e}"))
        exit_code = 1
    except ValueError as e:
        logger.critical(f"🚫 初始化管理器时发生配置或数值错误: {e}。脚本中止。")
        if notifier_instance: await notifier_instance.send_message(
            notifier_instance.format_script_status("error", details=f"配置/初始化错误: {e}"))
        exit_code = 1
    except SystemExit as e:
        logger.critical(f"🚫 配置初始化失败导致脚本中止: {e}")
        if notifier_instance and notifier_instance.bot:
            await notifier_instance.send_message(
                notifier_instance.format_script_status("error", details=f"严重配置错误导致中止: {e}")
            )
        else:
            if temp_tg_token and temp_tg_chat_id:
                try:
                    main_emergency_notifier = TelegramNotifier(Config())
                    if main_emergency_notifier.bot:
                        await main_emergency_notifier.send_message(
                            main_emergency_notifier.format_script_status("error", details=f"严重配置错误导致中止: {e}")
                        )
                except Exception as tg_init_err:
                    logger.error(f"🚫 创建或发送Telegram通知时发生错误: {tg_init_err}")
        exit_code = 1
    except Exception as e:
        logger.critical(f"🚫 执行过程中发生未捕获的严重错误 ({type(e).__name__}): {e}", exc_info=True)
        if notifier_instance: await notifier_instance.send_message(
            notifier_instance.format_script_status("error",
                                                   details=f"未捕获的严重错误: {type(e).__name__} - {str(e)[:100]}..."))
        exit_code = 1
    finally:
        if qbit_manager_instance:
            qbit_manager_instance.disconnect()

        elapsed_time = time.monotonic() - script_start_time
        if exit_code == 0:
            logger.info(f"🎉 ===== 脚本执行完毕，耗时 {elapsed_time:.2f} 秒. =====")
        else:
            logger.error(f"🚫 ===== 脚本因错误中止，耗时 {elapsed_time:.2f} 秒. =====")

        if notifier_instance and notifier_instance.bot:
            await asyncio.sleep(2)


if __name__ == "__main__":
    required_env_vars = ["MT_APIKEY", "MT_RSS_URL", "QBIT_HOST", "QBIT_USERNAME", "QBIT_PASSWORD"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        error_message = f"错误：以下必要的环境变量未设置: {', '.join(missing_vars)}。请设置后再运行。"
        print(error_message)
        logger.critical(error_message)

        temp_tg_token = os.environ.get("TG_BOT_TOKEN")
        temp_tg_chat_id = os.environ.get("TG_CHAT_ID")
        if temp_tg_token and temp_tg_chat_id:
            try:
                emergency_notifier = TelegramNotifier(Config())
                if emergency_notifier.bot:
                    async def notify_critical_env_error():
                        await emergency_notifier.send_message(
                            emergency_notifier.format_script_status("error",
                                                                    details=f"环境变量缺失: {', '.join(missing_vars)}")
                        )
                        await asyncio.sleep(1)


                    asyncio.run(notify_critical_env_error())
            except Exception as tg_err:
                print(f"发送Telegram通知失败: {tg_err}")
        sys.exit(1)

    if not os.environ.get("TG_BOT_TOKEN") or not os.environ.get("TG_CHAT_ID"):
        warning_msg = "警告：Telegram 环境变量 TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，通知功能将不可用。"
        print(warning_msg)
        logger.warning(warning_msg)

    asyncio.run(main())
