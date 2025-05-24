#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import html
import json
import logging
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Set, Union

import pytz
import requests
from dateutil import parser as date_parser
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Global constant for category data
CATEGORY_JSON_DATA = """
{"movie":["401","419","420","421","439"],"music":["406","434"],"list":[{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-26 23:50:33","id":"100","order":"1","nameChs":"电影","nameCht":"電影","nameEng":"Movie","image":"","parent":null},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-05-22 13:05:21","id":"423","order":"1","nameChs":"PC游戏","nameCht":"PC遊戲","nameEng":"PCGame","image":"game-pc-3.jpeg","parent":"447"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2025-05-01 12:09:56","id":"427","order":"1","nameChs":"電子書","nameCht":"電子書","nameEng":"E-Book","image":"ebook-4.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"401","order":"1","nameChs":"电影/SD","nameCht":"電影/SD","nameEng":"Movie/SD","image":"moviesd.png","parent":"100"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:52:09","id":"434","order":"1","nameChs":"Music(无损)","nameCht":"Music(無損)","nameEng":"Music(Lossless)","image":"flac.png","parent":"110"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:50:37","id":"403","order":"1","nameChs":"影剧/综艺/SD","nameCht":"影劇/綜藝/SD","nameEng":"TV Series/SD","image":"tvsd.png","parent":"105"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:52:05","id":"404","order":"1","nameChs":"纪录","nameCht":"紀錄","nameEng":"Record","image":"bbc.png","parent":"444"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 17:25:00","id":"405","order":"1","nameChs":"动画","nameCht":"動畫","nameEng":"Anime","image":"anime.png","parent":"449"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 17:25:04","id":"407","order":"1","nameChs":"运动","nameCht":"運動","nameEng":"Sports","image":"sport.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"419","order":"2","nameChs":"电影/HD","nameCht":"電影/HD","nameEng":"Movie/HD","image":"moviehd.png","parent":"100"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 17:25:06","id":"422","order":"2","nameChs":"软件","nameCht":"軟體","nameEng":"Software","image":"software.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:50:42","id":"402","order":"2","nameChs":"影剧/综艺/HD","nameCht":"影劇/綜藝/HD","nameEng":"TV Series/HD","image":"tvhd.png","parent":"105"},{"createdDate":"2024-04-13 17:16:22","lastModifiedDate":"2024-04-13 17:16:31","id":"448","order":"2","nameChs":"TV遊戲","nameCht":"TV遊戲","nameEng":"TvGame","image":"pcgame.png","parent":"447"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-26 23:50:36","id":"105","order":"2","nameChs":"影剧/综艺","nameCht":"影劇/綜藝","nameEng":"TV Series","image":"","parent":null},{"createdDate":"2024-04-13 02:03:17","lastModifiedDate":"2024-06-15 02:26:21","id":"442","order":"3","nameChs":"有聲書","nameCht":"有聲書","nameEng":"AuiBook","image":"Study_Audio.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:50:45","id":"438","order":"3","nameChs":"影剧/综艺/BD","nameCht":"影劇/綜藝/BD","nameEng":"TV Series/BD","image":"tvbd.png","parent":"105"},{"createdDate":"2024-04-13 16:40:33","lastModifiedDate":"2024-04-13 16:40:33","id":"444","order":"3","nameChs":"紀錄","nameCht":"紀錄","nameEng":"BBC","image":null,"parent":null},{"createdDate":"2025-05-03 14:22:10","lastModifiedDate":"2025-05-03 16:55:12","id":"451","order":"3","nameChs":"教育影片","nameCht":"教育影片","nameEng":"教育影片","image":"Study_Video.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:52:15","id":"406","order":"3","nameChs":"演唱","nameCht":"演唱","nameEng":"MV","image":"mv.png","parent":"110"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"420","order":"3","nameChs":"电影/DVDiSo","nameCht":"電影/DVDiSo","nameEng":"Movie/DVDiSo","image":"moviedvd.png","parent":"100"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 16:50:26","id":"435","order":"4","nameChs":"影剧/综艺/DVDiSo","nameCht":"影劇/綜藝/DVDiSo","nameEng":"TV Series/DVDiSo","image":"tvdvd.png","parent":"105"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-26 23:50:49","id":"110","order":"4","nameChs":"Music","nameCht":"Music","nameEng":"Music","image":"","parent":null},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-04-13 17:25:08","id":"409","order":"4","nameChs":"Misc(其他)","nameCht":"Misc(其他)","nameEng":"Misc(Other)","image":"other.png","parent":"450"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"421","order":"4","nameChs":"电影/Blu-Ray","nameCht":"電影/Blu-Ray","nameEng":"Movie/Blu-Ray","image":"moviebd.png","parent":"100"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"439","order":"5","nameChs":"电影/Remux","nameCht":"電影/Remux","nameEng":"Movie/Remux","image":"movieremux.png","parent":"100"},{"createdDate":"2024-04-13 17:15:28","lastModifiedDate":"2024-04-13 17:15:37","id":"447","order":"6","nameChs":"遊戲","nameCht":"遊戲","nameEng":"遊戲","image":null,"parent":null},{"createdDate":"2024-04-13 17:22:46","lastModifiedDate":"2024-04-13 17:22:55","id":"449","order":"7","nameChs":"動漫","nameCht":"動漫","nameEng":"Anime","image":null,"parent":null},{"createdDate":"2024-04-13 17:24:09","lastModifiedDate":"2024-04-13 17:24:09","id":"450","order":"8","nameChs":"其他","nameCht":"其他","nameEng":"其他","image":null,"parent":null},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-26 23:51:46","id":"115","order":"20","nameChs":"AV(有码)","nameCht":"AV(有碼)","nameEng":"AV(有碼)","image":"","parent":null},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-26 23:51:50","id":"120","order":"21","nameChs":"AV(无码)","nameCht":"AV(無碼)","nameEng":"AV(無碼)","image":"","parent":null},{"createdDate":"2024-04-13 16:52:43","lastModifiedDate":"2024-04-13 16:52:51","id":"445","order":"22","nameChs":"IV","nameCht":"IV","nameEng":"IV","image":null,"parent":null},{"createdDate":"2024-04-13 16:53:44","lastModifiedDate":"2024-04-13 16:53:44","id":"446","order":"23","nameChs":"H-ACG","nameCht":"H-ACG","nameEng":"H-ACG","image":null,"parent":null},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"410","order":"31","nameChs":"AV(有码)/HD Censored","nameCht":"AV(有碼)/HD Censored","nameEng":"AV(有碼)/HD Censored","image":"cenhd.png","parent":"115"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"429","order":"32","nameChs":"AV(无码)/HD Uncensored","nameCht":"AV(無碼)/HD Uncensored","nameEng":"AV(無碼)/HD Uncensored","image":"uenhd.png","parent":"120"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"424","order":"33","nameChs":"AV(有码)/SD Censored","nameCht":"AV(有碼)/SD Censored","nameEng":"AV(有碼)/SD Censored","image":"censd.png","parent":"115"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"430","order":"34","nameChs":"AV(无码)/SD Uncensored","nameCht":"AV(無碼)/SD Uncensored","nameEng":"AV(無碼)/SD Uncensored","image":"uensd.png","parent":"120"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"426","order":"35","nameChs":"AV(无码)/DVDiSo Uncensored","nameCht":"AV(無碼)/DVDiSo Uncensored","nameEng":"AV(無碼)/DVDiSo Uncensored","image":"uendvd.png","parent":"120"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"437","order":"36","nameChs":"AV(有码)/DVDiSo Censored","nameCht":"AV(有碼)/DVDiSo Censored","nameEng":"AV(有碼)/DVDiSo Censored","image":"cendvd.png","parent":"115"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"431","order":"37","nameChs":"AV(有码)/Blu-Ray Censored","nameCht":"AV(有碼)/Blu-Ray Censored","nameEng":"AV(有碼)/Blu-Ray Censored","image":"cenbd.png","parent":"115"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"432","order":"38","nameChs":"AV(无码)/Blu-Ray Uncensored","nameCht":"AV(無碼)/Blu-Ray Uncensored","nameEng":"AV(無碼)/Blu-Ray Uncensored","image":"uenbd.png","parent":"120"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"436","order":"39","nameChs":"AV(网站)/0Day","nameCht":"AV(網站)/0Day","nameEng":"AV(網站)/0Day","image":"adult0day.png","parent":"120"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"425","order":"40","nameChs":"IV(写真影集)","nameCht":"IV(寫真影集)","nameEng":"IV/Video Collection","image":"ivvideo.png","parent":"445"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"433","order":"41","nameChs":"IV(写真图集)","nameCht":"IV(寫真圖集)","nameEng":"IV/Picture Collection","image":"ivpic.png","parent":"445"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"411","order":"51","nameChs":"H-游戏","nameCht":"H-遊戲","nameEng":"H-Game","image":"hgame.png","parent":"446"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"412","order":"52","nameChs":"H-动漫","nameCht":"H-動畫","nameEng":"H-Anime","image":"hanime.png","parent":"446"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"413","order":"53","nameChs":"H-漫画","nameCht":"H-漫畫","nameEng":"H-Comic","image":"hcomic.png","parent":"446"},{"createdDate":"2024-03-22 14:00:15","lastModifiedDate":"2024-03-22 14:00:15","id":"440","order":"440","nameChs":"AV(Gay)/HD","nameCht":"AV(Gay)/HD","nameEng":"AV(Gay)/HD","image":"gayhd.gif","parent":"120"}],"tvshow":["403","402","435","438"],"adult":["410","429","424","430","426","437","431","432","436","425","433","411","412","413","440"],"waterfall":["410","401","419","420","421","439","402","403","435","438","408","434","424","431","437","426","429","430","432","436","440","404","405","406","407","409","411","412","413","422","423","425","427","433","441","442","448"]}
"""


class CategoryManager:
    def __init__(self, category_json_string: str):
        self.categories_by_id: Dict[str, Dict[str, Any]] = {}
        self.categories_by_name_eng: Dict[str, Dict[str, Any]] = {}
        self.categories_by_name_chs: Dict[str, Dict[str, Any]] = {}
        self.categories_by_name_cht: Dict[str, Dict[str, Any]] = {}

        try:
            data = json.loads(category_json_string)
            category_list = data.get("list", [])
            for cat_info in category_list:
                cat_id = cat_info.get("id")
                if not cat_id:
                    continue
                self.categories_by_id[cat_id] = cat_info

                name_eng = cat_info.get("nameEng", "").strip()
                if name_eng: self.categories_by_name_eng[name_eng.lower()] = cat_info

                name_chs = cat_info.get("nameChs", "").strip()
                if name_chs: self.categories_by_name_chs[name_chs.lower()] = cat_info

                name_cht = cat_info.get("nameCht", "").strip()
                if name_cht: self.categories_by_name_cht[name_cht.lower()] = cat_info

            logger.info(f"🗂️ 分类管理器初始化成功，加载了 {len(self.categories_by_id)} 个分类条目。")
        except json.JSONDecodeError:
            logger.error("🚫 解析分类JSON数据失败。分类名称转换将不可用。")
        except Exception as e:
            logger.error(f"🚫 初始化分类管理器时发生错误: {e}")

    def get_name_cht(self, identifier: str, is_id_lookup: bool = False) -> Optional[str]:
        """
        根据提供的标识符（ID或名称）获取繁体中文名称 (nameCht)。
        :param identifier: 分类ID或分类名称 (nameEng, nameChs, nameCht)。
        :param is_id_lookup: 如果为True，则将identifier严格视为ID进行查找。
        :return: 对应的nameCht，如果找不到则返回None。
        """
        if not identifier:
            return None

        cat_info: Optional[Dict[str, Any]] = None
        identifier_lower = identifier.lower()

        if is_id_lookup:
            cat_info = self.categories_by_id.get(identifier)
        else:
            cat_info = self.categories_by_name_eng.get(identifier_lower)
            if not cat_info:
                cat_info = self.categories_by_name_chs.get(identifier_lower)
            if not cat_info:
                cat_info = self.categories_by_name_cht.get(identifier_lower)
            if not cat_info and identifier in self.categories_by_id:
                cat_info = self.categories_by_id.get(identifier)

        if cat_info:
            return cat_info.get("nameCht")

        logger.debug(f"未能为标识符 '{identifier}' (is_id_lookup={is_id_lookup}) 找到对应的分类信息。")
        return None


class Config:
    def __init__(self):
        logger.info("⚙️ 初始化配置...")

        self.RSS_URL: Optional[str] = os.environ.get("MT_RSS_URL")
        self.TG_BOT_TOKEN: Optional[str] = os.environ.get("TG_BOT_TOKEN")
        self.TG_CHAT_ID: Optional[str] = os.environ.get("TG_CHAT_ID")
        self.DATA_FILE_PATH: str = os.environ.get("DATA_FILE_PATH", "mteam/rss_monitor_data.json")
        self.LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

        self.MAX_PROCESSED_IDS_HISTORY: int = 500
        self.PROCESSED_IDS_RETAIN_COUNT: int = 200
        try:
            self.MAX_PROCESSED_IDS_HISTORY = int(os.environ.get("MAX_PROCESSED_IDS_HISTORY", "500"))
            self.PROCESSED_IDS_RETAIN_COUNT = int(os.environ.get("PROCESSED_IDS_RETAIN_COUNT", "200"))
        except ValueError:
            logger.warning("MAX_PROCESSED_IDS_HISTORY 或 PROCESSED_IDS_RETAIN_COUNT 环境变量值无效，将使用默认值。")

        self.TZ_INFOS: Dict[str, pytz.BaseTzInfo] = {"CST": pytz.timezone("Asia/Shanghai")}
        self.LOCAL_TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Asia/Shanghai")

        self._setup_logging()
        self._validate_critical_configs()
        self._validate_history_configs()
        logger.info("👍 配置加载成功。")

    def _setup_logging(self):
        try:
            logging.getLogger().setLevel(self.LOG_LEVEL)
            logger.info(f"日志级别设置为: {self.LOG_LEVEL}")
        except ValueError:
            logger.warning(f"无效的LOG_LEVEL: {self.LOG_LEVEL}. 使用默认 INFO级别。")
            logging.getLogger().setLevel(logging.INFO)

    def _validate_critical_configs(self):
        critical_missing = []
        if not self.RSS_URL:
            critical_missing.append("M-Team RSS订阅URL (MT_RSS_URL)")
        if not self.TG_BOT_TOKEN:
            critical_missing.append("Telegram机器人Token (TG_BOT_TOKEN)")
        if not self.TG_CHAT_ID:
            critical_missing.append("Telegram频道ID (TG_CHAT_ID)")

        if critical_missing:
            error_msg = "、".join(critical_missing) + " 未设置。脚本无法运行。"
            logger.critical(f"🚫 {error_msg}")
            sys.exit(f"CRITICAL: {error_msg}")

    def _validate_history_configs(self):
        if self.PROCESSED_IDS_RETAIN_COUNT <= 0:
            logger.warning("PROCESSED_IDS_RETAIN_COUNT 必须大于0，已重置为默认值200。")
            self.PROCESSED_IDS_RETAIN_COUNT = 200
        if self.MAX_PROCESSED_IDS_HISTORY < self.PROCESSED_IDS_RETAIN_COUNT:
            logger.warning(
                f"MAX_PROCESSED_IDS_HISTORY ({self.MAX_PROCESSED_IDS_HISTORY}) 不能小于 PROCESSED_IDS_RETAIN_COUNT ({self.PROCESSED_IDS_RETAIN_COUNT})。已将 MAX_PROCESSED_IDS_HISTORY 调整为 {self.PROCESSED_IDS_RETAIN_COUNT * 2}.")
            self.MAX_PROCESSED_IDS_HISTORY = self.PROCESSED_IDS_RETAIN_COUNT * 2
        if self.MAX_PROCESSED_IDS_HISTORY <= 0:  # Should be caught by above, but defensive
            logger.warning("MAX_PROCESSED_IDS_HISTORY 必须大于0，已重置为默认值500。")
            self.MAX_PROCESSED_IDS_HISTORY = 500
            if self.MAX_PROCESSED_IDS_HISTORY < self.PROCESSED_IDS_RETAIN_COUNT:
                self.PROCESSED_IDS_RETAIN_COUNT = min(200,
                                                      self.MAX_PROCESSED_IDS_HISTORY // 2 if self.MAX_PROCESSED_IDS_HISTORY > 1 else 1)
                if self.PROCESSED_IDS_RETAIN_COUNT <= 0: self.PROCESSED_IDS_RETAIN_COUNT = 1


class Utils:
    @staticmethod
    def clean_subtitle(text: str) -> str:
        if not text:
            return ""
        cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af.\-_]', '', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    @staticmethod
    def get_current_time_localized(local_timezone: pytz.BaseTzInfo) -> datetime:
        return datetime.now(local_timezone)


class EmergencyNotifierConfig:
    def __init__(self, token: Optional[str], chat_id: Optional[str]):
        self.TG_BOT_TOKEN: Optional[str] = token
        self.TG_CHAT_ID: Optional[str] = chat_id
        self.LOCAL_TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Asia/Shanghai")


class TelegramNotifier:
    def __init__(self, config: Union[Config, EmergencyNotifierConfig]):
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
            logger.warning("⚠️ Telegram BOT_TOKEN 或 CHAT_ID 未配置。通知功能将不可用。")

    @staticmethod
    def _escape_html(text: Optional[str]) -> str:
        if not isinstance(text, str): return ""
        return html.escape(text, quote=True)

    async def send_message(self, message: str, use_html: bool = True) -> bool:
        if not self.bot or not self.config.TG_CHAT_ID:
            logger.debug(f"💬 Telegram通知跳过 (未配置)。消息: {message[:100]}...")
            return False
        try:
            chat_id_int = int(self.config.TG_CHAT_ID)
            max_len = 4096

            messages_to_send = []
            if use_html and len(message) > max_len:
                logger.warning(f"Telegram 消息过长 ({len(message)} > {max_len})，将被拆分为多条发送。")
                current_message_part = ""
                parts = message.split("\n🌸➖➖➖➖➖➖➖➖🌸\n")

                if len(parts) <= 1 and "\n\n" in message and "🌸➖➖➖➖➖➖➖➖🌸" not in message:
                    parts = message.split("\n\n")
                if len(parts) <= 1 and "\n" in message and "🌸➖➖➖➖➖➖➖➖🌸" not in message and "\n\n" not in message:
                    parts = message.split("\n")

                for i, part_content in enumerate(parts):
                    part_to_add = part_content
                    is_last_part = (i == len(parts) - 1)

                    # Add appropriate separator if not the last part and separator exists in original message
                    if not is_last_part:
                        if message.count(
                                "🌸➖➖➖➖➖➖➖➖🌸") > 0 and "🌸➖➖➖➖➖➖➖➖🌸" not in part_content:
                            part_to_add += "\n🌸➖➖➖➖➖➖➖➖🌸\n"
                        elif message.count("\n\n") > 0 and message.count(
                                "🌸➖➖➖➖➖➖➖➖🌸") == 0 and "\n\n" not in part_content:
                            part_to_add += "\n\n"
                        elif message.count("\n") > 0 and message.count(
                                "🌸➖➖➖➖➖➖➖➖🌸") == 0 and message.count(
                            "\n\n") == 0 and "\n" not in part_content:
                            part_to_add += "\n"

                    if len(current_message_part) + len(part_to_add) <= max_len:
                        current_message_part += part_to_add
                    else:
                        if current_message_part:
                            messages_to_send.append(current_message_part.strip())
                        current_message_part = part_to_add
                        if len(current_message_part) > max_len:
                            logger.warning(
                                f"消息拆分后单个部分仍然超长 ({len(current_message_part)} > {max_len})，将进行硬分割。")
                            for chunk_idx in range(0, len(current_message_part), max_len):
                                messages_to_send.append(current_message_part[chunk_idx: chunk_idx + max_len])
                            current_message_part = ""

                if current_message_part.strip():
                    messages_to_send.append(current_message_part.strip())
                if not messages_to_send and message:
                    logger.warning("消息智能拆分未能有效分割，将尝试按字符数硬分割。")
                    for i_chunk in range(0, len(message), max_len):
                        messages_to_send.append(message[i_chunk: i_chunk + max_len])
            else:
                messages_to_send = [message]

            all_sent_successfully = True
            for i, msg_chunk in enumerate(messages_to_send):
                if not msg_chunk.strip(): continue
                await self.bot.send_message(
                    chat_id=chat_id_int, text=msg_chunk,
                    parse_mode=ParseMode.HTML if use_html else None,
                    disable_web_page_preview=True
                )
                log_msg_preview = msg_chunk.replace('\n', ' ')[:100]
                logger.info(f"✅ Telegram消息块 {i + 1}/{len(messages_to_send)} 发送成功 (预览): {log_msg_preview}...")
                if i < len(messages_to_send) - 1:
                    await asyncio.sleep(1)
            return all_sent_successfully

        except ValueError:
            logger.error(f"🚫 无效的Telegram频道ID: '{self.config.TG_CHAT_ID}'。请确保它是一个有效的数字。")
        except TelegramError as e:
            logger.error(f"🚫 Telegram消息发送失败: {e}")
        except Exception as e:
            logger.error(f"🚫 发送Telegram消息时意外错误 ({type(e).__name__}): {e}")
        return False

    def format_torrent_message(self, torrent_info: Dict[str, Any]) -> str:
        id_emoji = "🆔"
        category_emoji = "🏷️"
        subtitle_emoji = "📜"
        name_emoji = "🔗"
        size_emoji = "💾"
        time_emoji = "⏰"

        header_parts = []
        torrent_id_val = self._escape_html(torrent_info.get('id', 'N/A'))
        header_parts.append(f"{id_emoji}[<code>{torrent_id_val}</code>]")

        category_val = self._escape_html(torrent_info.get('category', 'N/A'))
        if category_val != 'N/A':
            header_parts.append(f"{category_emoji}[{category_val}]")

        subtitle_val = self._escape_html(torrent_info.get('subtitle_cleaned', 'N/A'))
        if subtitle_val != 'N/A':
            header_parts.append(f"{subtitle_emoji}[{subtitle_val}]")

        header = "".join(header_parts)

        name = self._escape_html(torrent_info.get('torrent_name_component', 'N/A'))
        torrent_size = self._escape_html(torrent_info.get('size', 'N/A'))

        publish_time_default = Utils.get_current_time_localized(self.config.LOCAL_TIMEZONE)
        pub_time_obj = torrent_info.get('publish_time', publish_time_default)
        pub_time_str = pub_time_obj.strftime('%Y-%m-%d %H:%M:%S') if isinstance(pub_time_obj, datetime) else str(
            pub_time_obj)

        detail_link = self._escape_html(torrent_info.get('link', '#'))

        message = (
            f"{header}\n"
            f"{name_emoji} <b>资源名称:</b> <a href='{detail_link}'>{name}</a>\n"
            f"{size_emoji} <b>资源大小:</b> {torrent_size}\n"
            f"{time_emoji} <b>发布时间:</b> {pub_time_str}"
        )
        return message

    def format_bulk_message(self, torrents: List[Dict[str, Any]], script_start_time: float) -> str:
        if not torrents:
            logger.info(f"ℹ️ 本轮无新种子。")
            return ""

        count = len(torrents)
        message_header = f"📢📢📢 馒头有新种啦！快来看看有没有你喜欢的 ({count}个新种):\n"

        messages = [message_header]
        for torrent in torrents:
            messages.append(self.format_torrent_message(torrent))

        return "\n🌸➖➖➖➖➖➖➖➖🌸\n".join(messages)


class DataManager:
    def __init__(self, config: Config):
        self.config = config
        self.file_path = self.config.DATA_FILE_PATH
        self.data: Dict[str, Any] = {
            "all_pushed_ids": [],
            "last_pushed_batch_ids": []
        }

    def load_data(self) -> None:
        logger.info(f"📂 尝试从 {self.file_path} 加载数据...")
        if not os.path.exists(self.file_path):
            logger.info(f"ℹ️ 数据文件 {self.file_path} 不存在，使用空数据。")
            self.data["all_pushed_ids"] = []
            self.data["last_pushed_batch_ids"] = []
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                loaded_json_data = json.load(f)

            if not isinstance(loaded_json_data, dict):
                logger.warning(f"⚠️ {self.file_path} 数据非字典格式。备份并视为空。")
                self._backup_corrupted_file()
                self.data["all_pushed_ids"] = []
                self.data["last_pushed_batch_ids"] = []
                return

            self.data["all_pushed_ids"] = loaded_json_data.get("all_pushed_ids", [])
            self.data["last_pushed_batch_ids"] = loaded_json_data.get("last_pushed_batch_ids", [])

            if not isinstance(self.data["all_pushed_ids"], list):
                logger.warning("all_pushed_ids 格式错误，重置为空列表。")
                self.data["all_pushed_ids"] = []
            if not isinstance(self.data["last_pushed_batch_ids"], list):
                logger.warning("last_pushed_batch_ids 格式错误，重置为空列表。")
                self.data["last_pushed_batch_ids"] = []

            logger.info(f"✅ 从 {self.file_path} 加载数据成功。")
            logger.debug(f"加载 all_pushed_ids 数量: {len(self.data['all_pushed_ids'])}")
            logger.debug(f"加载 last_pushed_batch_ids: {self.data['last_pushed_batch_ids']}")

        except json.JSONDecodeError as e:
            logger.error(f"🚫 从 {self.file_path} 解码JSON出错: {e}。备份并视为空。")
            self._backup_corrupted_file()
            self.data["all_pushed_ids"] = []
            self.data["last_pushed_batch_ids"] = []
        except IOError as e:
            logger.error(f"🚫 无法读取文件 {self.file_path}: {e}。")
            self.data["all_pushed_ids"] = []
            self.data["last_pushed_batch_ids"] = []
        except Exception as e:
            logger.error(f"🚫 加载数据时意外错误 ({type(e).__name__}): {e}。")
            self.data["all_pushed_ids"] = []
            self.data["last_pushed_batch_ids"] = []

    def get_all_pushed_ids_set(self) -> Set[str]:
        return set(str(id_val) for id_val in self.data.get("all_pushed_ids", []))

    def get_last_pushed_batch_ids(self) -> List[str]:
        return [str(id_val) for id_val in self.data.get("last_pushed_batch_ids", [])]

    def _backup_corrupted_file(self):
        if not os.path.exists(self.file_path): return
        try:
            backup_path = self.file_path + f".corrupted_{int(time.time())}"
            os.rename(self.file_path, backup_path)
            logger.info(f"ℹ️ 已备份可能损坏的数据文件到 {backup_path}")
        except OSError as bak_err:
            logger.error(f"⚠️ 无法备份数据文件 {self.file_path}: {bak_err}")

    def save_data(self, all_ids_to_save: Set[str], last_batch_ids_to_save: List[str]) -> None:
        all_ids_list = sorted([str(id_val) for id_val in all_ids_to_save],
                              key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))

        if len(all_ids_list) > self.config.MAX_PROCESSED_IDS_HISTORY:
            original_count = len(all_ids_list)
            all_ids_list = all_ids_list[-self.config.PROCESSED_IDS_RETAIN_COUNT:]
            ids_removed_count = original_count - len(all_ids_list)
            logger.info(
                f"🧹 清理已处理ID历史: 从 {original_count} 条缩减到 {len(all_ids_list)} 条 (保留最新的 {self.config.PROCESSED_IDS_RETAIN_COUNT} 条)。移除了 {ids_removed_count} 条旧记录。")

        self.data["all_pushed_ids"] = all_ids_list
        self.data["last_pushed_batch_ids"] = [str(id_val) for id_val in last_batch_ids_to_save]

        logger.info(
            f"💾 保存 {len(self.data['all_pushed_ids'])} 条总记录和 {len(self.data['last_pushed_batch_ids'])} 条上批次记录到 {self.file_path}...")
        try:
            dir_name = os.path.dirname(self.file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                logger.info(f"创建目录: {dir_name}")

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            logger.info(f"✅ 数据成功保存到 {self.file_path}。")
        except IOError as e:
            logger.error(f"🚫 保存数据到 {self.file_path} 时IO错误: {e}")
        except Exception as e:
            logger.error(f"🚫 保存数据时意外错误 ({type(e).__name__}): {e}")


class RSSParser:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.category_manager = CategoryManager(CATEGORY_JSON_DATA)

    @staticmethod
    def _parse_mteam_title(title_full: str) -> Tuple[str, str, str, str]:
        """
        解析M-Team的RSS标题。
        返回: (raw_category_name, subtitle_raw, name_component, size)
        """
        if not title_full:
            return "N/A", "N/A", "N/A", "N/A"

        original_brackets_with_content = re.findall(r'(\[[^]]+])', title_full)
        bracket_inner_contents = [b[1:-1] for b in original_brackets_with_content]

        raw_category_name = "N/A"
        category_original_bracket = None
        if bracket_inner_contents:
            raw_category_name = bracket_inner_contents[0].strip()
            category_original_bracket = original_brackets_with_content[0]

        size = "N/A"
        size_original_bracket = None
        size_pattern_text = r'\d+(?:\.\d+)?\s*(?:GB|MB|TB|GiB|MiB|TiB)'
        for i, content in reversed(list(enumerate(bracket_inner_contents))):
            if re.fullmatch(size_pattern_text, content.strip(), re.IGNORECASE):
                size = content.strip()
                size_original_bracket = original_brackets_with_content[i]
                break

        subtitle_raw = "N/A"
        subtitle_original_bracket = None
        tech_spec_indicators = r'\b(?:\d{3,4}p|x26[45]|HEVC|AVC|DTS|HDR|REMUX|BluRay|WEB-DL|MKV|AAC|FLAC|WEB|HDTV|SDTV|Rip|Encode|VXT|CtrlHD|WiKi|CHDBits|Series|Movie)\b'

        candidate_indices = []
        if len(bracket_inner_contents) > 1: candidate_indices.append(1)
        if len(bracket_inner_contents) > 2: candidate_indices.append(2)

        for idx in candidate_indices:
            current_content = bracket_inner_contents[idx].strip()
            current_original_bracket = original_brackets_with_content[idx]

            if current_original_bracket == category_original_bracket or \
                    current_original_bracket == size_original_bracket:
                continue

            is_tech_spec = re.search(tech_spec_indicators, current_content, re.IGNORECASE)
            is_simple_na = current_content.lower() == 'n/a'
            is_already_size = re.fullmatch(size_pattern_text, current_content, re.IGNORECASE)

            if not is_tech_spec and not is_simple_na and not is_already_size and len(current_content) > 3:
                subtitle_raw = current_content
                subtitle_original_bracket = current_original_bracket
                break

        name_component = title_full
        if category_original_bracket:
            name_component = name_component.replace(category_original_bracket, "", 1)
        if subtitle_original_bracket:
            name_component = name_component.replace(subtitle_original_bracket, "", 1)
        if size_original_bracket:
            name_component = name_component.replace(size_original_bracket, "", 1)

        name_component = re.sub(r'\s*\[N/A\]\s*$', '', name_component).strip()
        name_component = re.sub(r'\s{2,}', ' ', name_component).strip()

        if not name_component:
            name_component = title_full
            if category_original_bracket: name_component = name_component.replace(category_original_bracket, "", 1)
            if size_original_bracket: name_component = name_component.replace(size_original_bracket, "", 1)
            name_component = re.sub(r'\s*\[N/A\]\s*$', '', name_component).strip()
            name_component = re.sub(r'\s{2,}', ' ', name_component).strip()
            if not name_component: name_component = title_full

        return raw_category_name, subtitle_raw, name_component, size

    def get_feed_items(self) -> List[Dict[str, Any]]:
        if not self.config.RSS_URL:
            logger.error("🚫 M-Team RSS URL 未配置。")
            return []

        logger.info(f"📰 从RSS源获取项目: {self.config.RSS_URL[:100]}...")
        xml_content: str = ""
        try:
            response = self.session.get(self.config.RSS_URL, timeout=30)
            response.raise_for_status()

            xml_content = response.text
            xml_content = "".join(
                ch for ch in xml_content if unicodedata.category(ch)[0] != "C" or ch in ('\t', '\n', '\r'))

            root = ET.fromstring(xml_content)
            rss_items = []

            for item_element in root.findall(".//item"):
                try:
                    title_full = item_element.findtext("title", "N/A").strip()
                    link = item_element.findtext("link")
                    pub_date_str = item_element.findtext("pubDate")
                    guid_element = item_element.find("guid")
                    guid = guid_element.text if guid_element is not None else link

                    if not link or not pub_date_str:
                        logger.warning(f"条目缺少链接或发布日期，跳过: '{title_full[:50]}...'")
                        continue

                    id_regex = r"(?:id=|details?/|detail/)(\d+)"
                    torrent_id_match = re.search(id_regex, link)
                    if not torrent_id_match and guid:
                        torrent_id_match = re.search(id_regex, guid)

                    if not torrent_id_match:
                        logger.warning(f"无法从链接/GUID提取ID: {link} / {guid}. 跳过: '{title_full[:50]}...'")
                        continue
                    torrent_id = torrent_id_match.group(1)

                    # Step 1: Parse parts from the full title using the existing method.
                    raw_cat_from_title, subtitle_raw, torrent_name_component, torrent_size = self._parse_mteam_title(
                        title_full)
                    subtitle_cleaned = Utils.clean_subtitle(subtitle_raw)

                    # Step 2: Attempt to get a category identifier from a dedicated RSS tag.
                    category_id_or_name_from_tag: Optional[str] = item_element.findtext("category")

                    final_display_category_name = "N/A"

                    # Priority 1: Use ID from tag if available and numeric
                    if category_id_or_name_from_tag and category_id_or_name_from_tag.isdigit():
                        name_cht_from_id = self.category_manager.get_name_cht(category_id_or_name_from_tag,
                                                                              is_id_lookup=True)
                        if name_cht_from_id:
                            final_display_category_name = name_cht_from_id
                            logger.debug(
                                f"项目 {torrent_id}: 使用来自标签的分类ID '{category_id_or_name_from_tag}' 映射到 '{final_display_category_name}'.")

                    # Priority 2: Use name from tag if not yet resolved and tag provided a name
                    if final_display_category_name == "N/A" and category_id_or_name_from_tag and not category_id_or_name_from_tag.isdigit():
                        name_cht_from_tag_name = self.category_manager.get_name_cht(category_id_or_name_from_tag,
                                                                                    is_id_lookup=False)
                        if name_cht_from_tag_name:
                            final_display_category_name = name_cht_from_tag_name
                            logger.debug(
                                f"项目 {torrent_id}: 使用来自标签的分类名 '{category_id_or_name_from_tag}' 映射到 '{final_display_category_name}'.")

                    # Priority 3: Use raw category name parsed from title if not yet resolved
                    if final_display_category_name == "N/A" and raw_cat_from_title and raw_cat_from_title != "N/A":
                        name_cht_from_title_parse = self.category_manager.get_name_cht(raw_cat_from_title,
                                                                                       is_id_lookup=False)
                        if name_cht_from_title_parse:
                            final_display_category_name = name_cht_from_title_parse
                            logger.debug(
                                f"项目 {torrent_id}: 使用来自标题解析的分类名 '{raw_cat_from_title}' 映射到 '{final_display_category_name}'.")

                    # Fallbacks if still "N/A"
                    if final_display_category_name == "N/A":
                        if raw_cat_from_title and raw_cat_from_title != "N/A":
                            final_display_category_name = raw_cat_from_title
                            logger.warning(
                                f"项目 {torrent_id}: 无法将分类 '{raw_cat_from_title}' (来自标题) 映射到 nameCht。使用原始名称。")
                        elif category_id_or_name_from_tag:
                            final_display_category_name = category_id_or_name_from_tag
                            logger.warning(
                                f"项目 {torrent_id}: 无法将分类 '{category_id_or_name_from_tag}' (来自标签) 映射到 nameCht。使用原始标签内容。")

                    try:
                        publish_time_naive = date_parser.parse(pub_date_str, tzinfos=self.config.TZ_INFOS)
                        if publish_time_naive.tzinfo is None or publish_time_naive.tzinfo.utcoffset(
                                publish_time_naive) is None:
                            publish_time_aware = self.config.LOCAL_TIMEZONE.localize(publish_time_naive)
                        else:
                            publish_time_aware = publish_time_naive.astimezone(self.config.LOCAL_TIMEZONE)
                    except Exception as e_date:
                        logger.warning(f"解析种子 {torrent_id} 发布时间 '{pub_date_str}' 失败: {e_date}. 使用当前时间。")
                        publish_time_aware = Utils.get_current_time_localized(self.config.LOCAL_TIMEZONE)

                    rss_items.append({
                        "id": torrent_id,
                        "title_full": title_full,
                        "category": final_display_category_name,
                        "subtitle_raw": subtitle_raw,
                        "subtitle_cleaned": subtitle_cleaned,
                        "torrent_name_component": torrent_name_component,
                        "size": torrent_size,
                        "publish_time": publish_time_aware,
                        "link": link
                    })
                except Exception as e_item:
                    item_title_preview = item_element.findtext('title', 'N/A')[:50]
                    logger.warning(f"⚠️ 解析RSS项目时出错: {e_item}. 项目: '{item_title_preview}...'. 跳过该项目。")

            logger.info(f"📊 从RSS源解析到 {len(rss_items)} 个项目。")
            rss_items.sort(key=lambda x: x["publish_time"], reverse=True)
            return rss_items

        except requests.exceptions.RequestException as e:
            logger.error(f"🚫 获取M-Team RSS源失败: {e}.")
        except ET.ParseError as e:
            content_preview = xml_content[:500] if xml_content else "无法获取内容"
            logger.error(f"🚫 解析M-Team RSS XML失败: {e}. 内容预览: '{content_preview}...'")
        except Exception as e:
            logger.error(f"🚫 处理RSS源时未知错误 ({type(e).__name__}): {e}")
        return []


class FeedMonitor:
    def __init__(self, config: Config, notifier: TelegramNotifier, data_manager: DataManager, rss_parser: RSSParser):
        self.config = config
        self.notifier = notifier
        self.data_manager = data_manager
        self.rss_parser = rss_parser
        self.max_items_to_push = 10

    async def run(self) -> int:
        logger.info("🚀 执行RSS订阅监控...")
        self.data_manager.load_data()

        initial_all_pushed_ids_set = self.data_manager.get_all_pushed_ids_set().copy()
        initial_last_pushed_batch_ids = list(self.data_manager.get_last_pushed_batch_ids())

        feed_items = self.rss_parser.get_feed_items()
        if not feed_items:
            logger.info("ℹ️ RSS源无项目或加载失败。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0

        genuinely_new_torrents = []
        for item in feed_items:
            item_id_str = str(item.get("id", ""))
            if not item_id_str:
                logger.warning(f"发现一个没有ID的项目: {item.get('title_full', 'N/A')[:30]}... 跳过。")
                continue
            if item_id_str not in initial_all_pushed_ids_set:
                genuinely_new_torrents.append(item)
            else:
                logger.debug(
                    f"ID {item_id_str} ({item.get('title_full', 'N/A')[:30]}...) 已存在于 all_pushed_ids_set，跳过。")

        if not genuinely_new_torrents:
            logger.info("✅ RSS源中所有项目均已处理过。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0

        current_batch_to_push = genuinely_new_torrents[:self.max_items_to_push]
        current_batch_ids = [str(item["id"]) for item in current_batch_to_push]

        if not current_batch_to_push:
            logger.info("ℹ️ 筛选后无新种子可推送。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0

        if current_batch_ids == initial_last_pushed_batch_ids and initial_last_pushed_batch_ids:
            logger.info(f"⏭️ 本次选出的新种子批次 (IDs: {current_batch_ids}) 与上次成功推送的批次完全相同，跳过发送。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0

        logger.info(f"📨 准备推送 {len(current_batch_to_push)} 个新种子...")
        full_message_content = self.notifier.format_bulk_message(current_batch_to_push, time.monotonic())

        if not full_message_content:
            logger.info("ℹ️ 格式化消息为空，本轮不发送Telegram通知。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0

        sent_successfully = await self.notifier.send_message(full_message_content)

        if sent_successfully:
            logger.info(f"✅ {len(current_batch_to_push)} 个种子信息已发送。")
            updated_all_pushed_ids_set = initial_all_pushed_ids_set.copy()
            updated_all_pushed_ids_set.update(current_batch_ids)
            self.data_manager.save_data(updated_all_pushed_ids_set, current_batch_ids)
            return len(current_batch_to_push)
        else:
            logger.error("🚫 发送Telegram消息失败。本轮项目不标记为已处理。")
            self.data_manager.save_data(initial_all_pushed_ids_set, initial_last_pushed_batch_ids)
            return 0


async def main():
    script_start_time = time.monotonic()
    error_occurred_in_run = False
    items_pushed_this_run = 0

    config_instance: Optional[Config] = None
    notifier_instance: Optional[TelegramNotifier] = None

    try:
        config_instance = Config()
        notifier_instance = TelegramNotifier(config_instance)

        data_manager = DataManager(config_instance)
        rss_parser = RSSParser(config_instance)

        monitor = FeedMonitor(config_instance, notifier_instance, data_manager, rss_parser)
        items_pushed_this_run = await monitor.run()

        if items_pushed_this_run > 0:
            logger.info(f"✅ 本轮成功推送 {items_pushed_this_run} 个新种子。")

    except SystemExit as e:
        logger.critical(f"🚫 配置错误导致中止: {e}")
        error_occurred_in_run = True
        temp_tg_token_exit = os.environ.get("TG_BOT_TOKEN")
        temp_tg_chat_id_exit = os.environ.get("TG_CHAT_ID")
        if temp_tg_token_exit and temp_tg_chat_id_exit:
            emergency_config_exit = EmergencyNotifierConfig(temp_tg_token_exit, temp_tg_chat_id_exit)
            emergency_notifier_exit = TelegramNotifier(emergency_config_exit)
            if emergency_notifier_exit.bot:
                await emergency_notifier_exit.send_message(
                    f"☠️ <b>M-Team RSS监控</b>: 严重配置错误中止 - <code>{html.escape(str(e))}</code>. 请检查环境变量。")
        return
    except Exception as e:
        logger.critical(f"🚫 执行时发生未捕获严重错误 ({type(e).__name__}): {e}", exc_info=True)
        error_occurred_in_run = True
        if notifier_instance and notifier_instance.bot:
            await notifier_instance.send_message(
                f"☠️ <b>M-Team RSS监控</b>: 运行时严重错误 - <code>{html.escape(type(e).__name__)}: {html.escape(str(e)[:200])}...</code>"
            )
    finally:
        elapsed_time = time.monotonic() - script_start_time
        if error_occurred_in_run:
            logger.error(f"🚫 ===== 脚本因错误中止或未完成，耗时 {elapsed_time:.2f} 秒. =====")
        else:
            logger.info(f"🎉 ===== 脚本执行完毕，耗时 {elapsed_time:.2f} 秒. (推送 {items_pushed_this_run} 条) =====")

        if notifier_instance and notifier_instance.bot:
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    # os.environ[
    #     "MT_RSS_URL"] = "https://rss.m-team.cc/api/rss/fetch?dl=1&pageSize=20&sign=xxxxxxxxxxxxxxxxx&t=xxxxxxxxxxxx&teams=9%2C44%2C43%2C23&tkeys=ttitle%2Ctcat%2Ctsmalldescr%2Ctsize&uid=xxxxxxx"
    # os.environ["TG_BOT_TOKEN"] = "7888888022:Tțgxxxxxxxxxxxxxxxxxxxxxx"
    # os.environ["TG_CHAT_ID"] = "-10023243240"
    # os.environ["LOG_LEVEL"] = "INFO"

    required_env_vars_check = ["MT_RSS_URL", "TG_BOT_TOKEN", "TG_CHAT_ID"]
    if any(not os.environ.get(var) for var in required_env_vars_check):
        missing_vars_str = ", ".join([var for var in required_env_vars_check if not os.environ.get(var)])
        logger.critical(f"启动前检查: 关键环境变量 {missing_vars_str} 未设置。脚本无法启动。")

        temp_tg_token_main = os.environ.get("TG_BOT_TOKEN")
        temp_tg_chat_id_main = os.environ.get("TG_CHAT_ID")
        if temp_tg_token_main and temp_tg_chat_id_main:
            emergency_config_main = EmergencyNotifierConfig(temp_tg_token_main, temp_tg_chat_id_main)
            emergency_notifier_main = TelegramNotifier(emergency_config_main)
            if emergency_notifier_main.bot:
                async def notify_env_error():
                    await emergency_notifier_main.send_message(
                        f"☠️ <b>M-Team RSS监控</b>: 启动失败! 关键环境变量缺失: <code>{html.escape(missing_vars_str)}</code>")
                    await asyncio.sleep(1)


                try:
                    asyncio.run(notify_env_error())
                except Exception as e_notify:
                    logger.error(f"发送紧急启动错误通知失败: {e_notify}")
        sys.exit(1)
    asyncio.run(main())
