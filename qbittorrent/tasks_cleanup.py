#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html  # 用于HTML转义
import logging
import os
import sys
import time

import requests  # 用于Telegram通知
from qbittorrentapi import Client, APIConnectionError, LoginFailed, TorrentStates, NotFound404Error

# --- qBittorrent 配置 ---
QBIT_HOST = os.environ.get('QBIT_HOST', 'http://localhost:8080')
QBIT_PORT = int(os.environ.get('QBIT_PORT', '8080')),
QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')
QBIT_VERIFY_CERT = os.environ.get('QBIT_VERIFY_CERT', 'True').lower() != 'false'

# --- Telegram 配置 ---
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

# --- 删除逻辑常量 ---
# 情景1: 状态为 error 或 unknown 的任务，无论分类，直接完全删除
SCENARIO1_STATES = [
    TorrentStates.ERROR,
    TorrentStates.UNKNOWN
]

# 情景2: 特定分类（如'刷流'）且处于特定状态的任务，删除任务及文件
SCENARIO2_CATEGORIES = ['刷流']
SCENARIO2_STATES = [
    TorrentStates.PAUSED_UPLOAD,
    TorrentStates.STALLED_UPLOAD,
    TorrentStates.MISSING_FILES,
    TorrentStates.UNKNOWN,
    TorrentStates.ERROR
]

# 情景3: 特定分类，处于对刷流无益的状态，仅删除任务，保留文件
SCENARIO3_CATEGORIES = ['儿童', '其他', '刷流', '动漫', '成人', '电影', '电视节目', '纪录片', '音乐', '音乐视频']
SCENARIO3_STATES = [
    TorrentStates.PAUSED_UPLOAD,
    TorrentStates.STALLED_UPLOAD,
    TorrentStates.MISSING_FILES
]

# --- 日志记录器设置 ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - [%(funcName)s] - %(message)s',
    handlers=[logging.StreamHandler()]
)


class QBittorrentManager:
    """管理与qBittorrent的连接、种子信息获取和删除操作。"""

    def __init__(self):
        logger.info("⚙️ 初始化 QBittorrentManager...")
        self.qbit_host = QBIT_HOST
        self.qbit_port: int = int(os.environ.get("QBIT_PORT", "8080"))
        self.qbit_username = QBIT_USERNAME
        self.qbit_password = QBIT_PASSWORD
        self.verify_cert = QBIT_VERIFY_CERT
        self.qbit = None
        self.current_run_matched_details = []
        logger.info("👍 QBittorrentManager 配置加载成功。")

    def connect_qbit(self) -> bool:
        """连接到qBittorrent并登录。"""
        logger.info(f"🔗 尝试连接到 qBittorrent: {self.qbit_host}")
        try:
            self.qbit = Client(
                host=self.qbit_host,
                port=self.qbit_port,
                username=self.qbit_username,
                password=self.qbit_password,
                REQUESTS_ARGS={'timeout': (10, 30)}
            )
            self.qbit.auth_log_in()
            qbit_version = self.qbit.app.version
            api_version = self.qbit.app.web_api_version
            logger.info(f"✅ 成功连接并登录到 qBittorrent (版本: v{qbit_version}, API 版本: {api_version})")
            return True
        except LoginFailed as e:
            logger.error(f"💥 qBittorrent 登录失败: {e}")
            return False
        except APIConnectionError as e:
            logger.error(f"💥 连接 qBittorrent 失败: {e}")
            return False
        except Exception as e:
            logger.error(f"💥 连接或登录时发生未知错误: {e}", exc_info=True)
            return False

    def disconnect_qbit(self):
        """从qBittorrent注销并断开连接。"""
        if self.qbit and self.qbit.is_logged_in:
            try:
                self.qbit.auth_log_out()
                logger.info("🔌 已成功从 qBittorrent 注销。")
            except Exception as e:
                logger.warning(f"⚠️ 注销 qBittorrent 时发生错误: {e}", exc_info=True)
        self.qbit = None

    def delete_torrents_by_criteria(self) -> int:
        """
        根据预设情景规则检查并删除种子。
        返回实际发起删除操作的种子数量。
        """
        logger.info("🔍 开始检查种子...")
        if not self.qbit or not self.qbit.is_logged_in:
            logger.warning("🚫 未连接到 qBittorrent，跳过删除操作。")
            return 0

        try:
            torrents = self.qbit.torrents_info()
        except Exception as e:
            logger.error(f"💥 获取种子列表失败: {e}", exc_info=True)
            return 0

        if not torrents:
            logger.info("ℹ️ 当前 qBittorrent 中没有种子，无需操作。")
            return 0

        torrents_to_delete_with_files_hashes = set()
        torrents_to_delete_task_only_hashes = set()
        self.current_run_matched_details = []  # 重置本轮详情

        for torrent in torrents:
            torrent_hash = torrent.hash
            torrent_name = torrent.name
            torrent_category = torrent.category if torrent.category else ""
            torrent_state = torrent.state

            action_description = ""
            scenario_name = ""
            reason_details_for_log = ""

            # 情景1
            if torrent_state in SCENARIO1_STATES:
                if torrent_hash not in torrents_to_delete_with_files_hashes:
                    torrents_to_delete_with_files_hashes.add(torrent_hash)
                    action_description = "将删除任务和文件"
                    scenario_name = "情景1"
                    reason_details_for_log = f"状态为 {torrent_state}"
            # 情景2
            elif torrent_category in SCENARIO2_CATEGORIES and torrent_state in SCENARIO2_STATES:
                if torrent_hash not in torrents_to_delete_with_files_hashes:
                    torrents_to_delete_with_files_hashes.add(torrent_hash)
                    action_description = "将删除任务和文件"
                    scenario_name = "情景2"
                    reason_details_for_log = f"分类 '{torrent_category}' 且状态为 {torrent_state}"
            # 情景3
            elif torrent_category in SCENARIO3_CATEGORIES and torrent_state in SCENARIO3_STATES:
                if torrent_hash not in torrents_to_delete_with_files_hashes and \
                        torrent_hash not in torrents_to_delete_task_only_hashes:
                    torrents_to_delete_task_only_hashes.add(torrent_hash)
                    action_description = "将仅删除任务"
                    scenario_name = "情景3"
                    reason_details_for_log = f"分类 {torrent_category} 且状态为 {torrent_state}"

            if scenario_name:
                self.current_run_matched_details.append({
                    'name': torrent_name,
                    'category': torrent_category,
                    'state_value': torrent_state,
                    'scenario': scenario_name,
                    'reason_details': reason_details_for_log,
                    'action_description': action_description
                })

        actually_deleted_count = 0

        if torrents_to_delete_with_files_hashes:
            hashes_list = list(torrents_to_delete_with_files_hashes)
            logger.info(f"⏳ 准备删除 {len(hashes_list)} 个种子 (任务和文件)...")
            try:
                self.qbit.torrents_delete(delete_files=True, torrent_hashes=hashes_list)
                logger.info(f"✅ 成功发起删除 {len(hashes_list)} 个种子 (任务和文件) 的请求。")
                actually_deleted_count += len(hashes_list)
            except NotFound404Error:
                logger.warning(f"⚠️ 删除部分种子(带文件)时，有种子未找到 (可能已被其他方式删除)。")
                actually_deleted_count += len(hashes_list)
            except Exception as e:
                logger.error(f"💥 删除种子(带文件)时出错: {e}", exc_info=True)

        final_torrents_to_delete_task_only = torrents_to_delete_task_only_hashes - torrents_to_delete_with_files_hashes

        if final_torrents_to_delete_task_only:
            hashes_list = list(final_torrents_to_delete_task_only)
            logger.info(f"⏳ 准备删除 {len(hashes_list)} 个种子 (仅任务)...")
            try:
                self.qbit.torrents_delete(delete_files=False, torrent_hashes=hashes_list)
                logger.info(f"✅ 成功发起删除 {len(hashes_list)} 个种子 (仅任务) 的请求。")
                actually_deleted_count += len(hashes_list)
            except NotFound404Error:
                logger.warning(f"⚠️ 删除部分种子(仅任务)时，有种子未找到 (可能已被其他方式删除)。")
                actually_deleted_count += len(hashes_list)
            except Exception as e:
                logger.error(f"💥 删除种子(仅任务)时出错: {e}", exc_info=True)

        if not self.current_run_matched_details:
            logger.info("ℹ️ 没有找到符合删除条件的种子。")

        return actually_deleted_count


def format_telegram_message(content: str) -> str:
    """
    优化后的消息格式化函数，只转义纯文本内容，保留 Telegram 支持的 HTML 标签
    """
    # 先处理换行
    content = content.replace("<br>", "\n")

    # 使用正则表达式来保护 Telegram 支持的 HTML 标签不被转义
    import re
    from html import escape

    # Telegram 支持的标签列表
    supported_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'a']

    # 构建正则表达式模式来匹配这些标签及其内容
    tag_pattern = '|'.join(supported_tags)
    pattern = re.compile(
        r'<(/?)({})(?:\s+[^>]*?)?>'.format(tag_pattern),
        re.IGNORECASE
    )

    # 临时替换标签为占位符
    placeholders = {}

    def replace_tag(match):
        placeholder = f"__TAG_{len(placeholders)}__"
        placeholders[placeholder] = match.group(0)
        return placeholder

    content_with_placeholders = pattern.sub(replace_tag, content)

    # 转义剩余内容
    escaped_content = escape(content_with_placeholders)

    # 恢复标签
    for placeholder, tag in placeholders.items():
        escaped_content = escaped_content.replace(placeholder, tag)

    return escaped_content


def send_telegram_notification(bot_token: str, chat_id: str, message_parts: list):
    """
    优化后的Telegram通知发送函数
    完全兼容Telegram HTML格式要求
    """
    if not bot_token or not chat_id:
        logger.warning("⚠️ Telegram token 或 chat ID 未配置。跳过通知。")
        return

    # 构建基础消息
    base_message = "<b>🗑️ qBittorrent 任务清理脚本报告</b>\n"

    # 处理消息内容
    processed_parts = []
    for part in message_parts:
        # 格式化每个部分
        formatted_part = format_telegram_message(part)
        processed_parts.append(formatted_part)

    message_body = "".join(processed_parts)
    full_message = base_message + message_body

    # 处理消息长度限制
    max_length = 4096  # Telegram消息长度限制
    if len(full_message) > max_length:
        truncate_indicator = "\n... [消息过长，已截断] ..."
        available_length = max_length - len(truncate_indicator)
        # 尝试在最后一个换行符处截断
        last_newline = full_message.rfind("\n", 0, available_length)
        if last_newline != -1:
            full_message = full_message[:last_newline] + truncate_indicator
        else:
            full_message = full_message[:available_length] + truncate_indicator
        logger.warning("Telegram 消息体过长，已执行截断。")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': full_message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }

    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        logger.info("✅ Telegram 通知已成功发送。")
    except requests.exceptions.Timeout:
        logger.error("💥 发送 Telegram 通知超时。")
    except requests.exceptions.HTTPError as e:
        logger.error(f"💥 发送 Telegram 通知失败 (HTTP Error): {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"💥 发送 Telegram 通知失败 (RequestException): {e}")
    except Exception as e:
        logger.error(f"💥 发送 Telegram 通知时发生未知错误: {e}")


def main():
    """优化后的主函数，调整了消息生成逻辑"""
    start_time = time.perf_counter()
    logger.info(f"🏁 ===== qBittorrent 清理开始执行 =====")

    manager = QBittorrentManager()
    telegram_report_parts = []  # 改名为更通用的名称

    # 添加脚本执行时间戳
    exec_time_str = time.strftime('%Y-%m-%d %H:%M:%S %Z')
    telegram_report_parts.append(f"<b>执行时间</b>: <code>{exec_time_str}</code>\n")

    if not manager.connect_qbit():
        logger.critical("🚫 连接 qBittorrent 失败，脚本终止。")
        telegram_report_parts.append(
            "🚫 <b>脚本执行失败:</b>\n"
            f"无法连接到 qBittorrent (<code>{manager.qbit_host}</code>)。\n"
            f"请检查 qBittorrent 是否正在运行以及网络连接和认证信息是否正确。"
        )
        send_telegram_notification(TG_BOT_TOKEN, TG_CHAT_ID, telegram_report_parts)
        end_time = time.perf_counter()
        logger.info(f"💥 ===== qBittorrent 清理脚本执行中止，耗时 {end_time - start_time:.2f} 秒. =====")
        return

    total_deleted_this_run = manager.delete_torrents_by_criteria()

    # 控制台日志输出保持不变
    if manager.current_run_matched_details:
        logger.info("\n📜 本轮计划操作详情:")
        for item in manager.current_run_matched_details:
            logger.info(
                f"  - '{item['name']}' (分类: '{item['category']}', 状态: '{item['state_value']}') - "
                f"原因: {item['scenario']} ({item['reason_details']}) - {item['action_description']}."
            )

    if manager.current_run_matched_details and len(manager.current_run_matched_details) > 0:
        telegram_report_parts.append("📜 <b>本轮计划操作详情:</b>\n")
        for item in manager.current_run_matched_details:
            name = html.escape(item['name'])
            category = html.escape(item['category'])
            state = html.escape(item['state_value'])
            scenario = html.escape(item['scenario'])
            reason = html.escape(item['reason_details'])
            action = html.escape(item['action_description'])

            telegram_report_parts.append(
                f"- <b>{name}</b> (分类: '{category}', 状态: <code>{state}</code>)\n"
                f" 原因: {scenario} ({reason}) - <i>{action}</i>\n"
            )
    else:
        telegram_report_parts.append("📜 <b>本轮计划操作详情:</b> 无匹配项。\n")

    # 总结信息
    summary_msg = "\n📊 <b>总结:</b>\n"
    if total_deleted_this_run > 0:
        summary_msg += f"✅ 本轮共成功发起 <code>{total_deleted_this_run}</code> 个种子的删除请求。"
    elif manager.current_run_matched_details and len(manager.current_run_matched_details) > 0:
        summary_msg += (
            f"⚠️ 本轮匹配到 <code>{len(manager.current_run_matched_details)}</code> 个种子计划操作，"
            f"但实际删除的种子数量为0。\n"
            f"   <i>请检查 qBittorrent 日志或种子状态。</i>"
        )
    else:
        logger.info("ℹ️ 本轮未发现符合删除条件的种子，未执行任何操作。")
        sys.exit(0)

    telegram_report_parts.append(summary_msg)

    send_telegram_notification(TG_BOT_TOKEN, TG_CHAT_ID, telegram_report_parts)

    manager.disconnect_qbit()
    end_time = time.perf_counter()
    logger.info(f"🎉 ===== qBittorrent 清理脚本执行完毕，耗时 {end_time - start_time:.2f} 秒. =====")


if __name__ == "__main__":
    logging.getLogger('qbittorrentapi').setLevel(logging.INFO)
    main()
