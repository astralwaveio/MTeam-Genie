#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qBittorrent 智能管理脚本

功能简介:
1.  连接到 qBittorrent 服务。
2.  根据预设规则和实时状态，智能判断哪些种子任务可以被清理。
3.  区分“刷流任务”和“非刷流任务”，应用不同的清理策略：
    - 刷流任务：重点监控其活跃度、上传效率和站点规则（如分享率、做种时间），对不再产生效益或长期无效的任务进行清理（删除任务及文件）。
    - 非刷流任务：主要目标是保护文件，仅在任务出错或文件丢失等严重问题时考虑删除任务（保留文件）。
4.  引入状态持续时间监控：避免因短暂的状态变化导致任务被误删。只有当任务持续处于某种“无效”状态达到设定时长后，才触发清理。
5.  支持 Freeleech 种子的特殊处理，通常给予更长的保留时间。
6.  包含“荣退”机制：对于已达到高分享率、低需求或做种时间过长的非 Freeleech 刷流任务，可自动清理以释放资源。
7.  所有操作均有详细日志记录，支持 DRY_RUN (演习模式) 进行测试。
8.  可选的 Telegram 通知功能，将清理结果报告发送给用户。

使用此脚本前，请务必理解其逻辑，并根据自己的实际情况调整 `CONFIG` 中的参数。
错误的配置可能导致不期望的数据丢失。建议先在 DRY_RUN 模式下充分测试。
"""

import html
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from qbittorrentapi import Client, APIConnectionError, LoginFailed, TorrentStates, NotFound404Error

CONFIG = {
    "QBIT_HOST": os.environ.get('QBIT_HOST', 'http://localhost:8080'),
    "QBIT_PORT": int(os.environ.get('QBIT_PORT', '8080')),
    "QBIT_USERNAME": os.environ.get('QBIT_USERNAME', None),
    "QBIT_PASSWORD": os.environ.get('QBIT_PASSWORD', None),
    "QBIT_VERIFY_CERT": os.environ.get('QBIT_VERIFY_CERT', 'True').lower() != 'false',
    "QBIT_REQUESTS_ARGS": {'timeout': (10, 30)},

    "BRUSHING_CATEGORIES": [cat.strip() for cat in os.environ.get('BRUSHING_CATEGORIES', "刷流").split(',')
                            if cat.strip()],
    "BRUSHING_TAGS": [tag.strip() for tag in os.environ.get('BRUSHING_TAGS', "刷流").split(',') if tag.strip()],
    "NON_BRUSHING_CATEGORIES": [cat.strip() for cat in os.environ.get('NON_BRUSHING_CATEGORIES',
                                                                      "keep,collection,archive,电影,电视剧,音乐,纪录片,动漫,儿童,其他,成人,音乐视频").split(
        ',') if cat.strip()],
    "NON_BRUSHING_TAGS": [tag.strip() for tag in
                          os.environ.get('NON_BRUSHING_TAGS', "personal,archive_manual").split(',') if tag.strip()],
    "FREELEECH_TAGS": [tag.strip() for tag in os.environ.get('FREELEECH_TAGS', "freeleech,FL,FreeLeech").split(',') if
                       tag.strip()],

    "MONITOR_FILE_PATH": Path(os.environ.get('MONITOR_FILE_PATH', "mteam/delete_record_data.json")),
    "USELESS_STATE_MONITOR_DURATION_MINUTES": int(os.environ.get('USELESS_STATE_MONITOR_DURATION_MINUTES', '15')),
    "STALLED_WITH_LEECHERS_MONITOR_DURATION_MINUTES": int(
        os.environ.get('STALLED_WITH_LEECHERS_MONITOR_DURATION_MINUTES', '45')),
    "FREELEECH_STALLED_NO_LEECHERS_MONITOR_DURATION_MINUTES": int(
        os.environ.get('FREELEECH_STALLED_NO_LEECHERS_MONITOR_DURATION_MINUTES', '240')),

    "RETIREMENT_MIN_RATIO": float(os.environ.get('RETIREMENT_MIN_RATIO', '5.0')),
    "RETIREMENT_LOW_DEMAND_LEECHERS": int(os.environ.get('RETIREMENT_LOW_DEMAND_LEECHERS', '1')),
    "RETIREMENT_MIN_SEEDING_DAYS": int(os.environ.get('RETIREMENT_MIN_SEEDING_DAYS', '14')),
    "RETIREMENT_MAX_SEEDING_DAYS_NO_ACTIVITY_NON_FL": int(
        os.environ.get('RETIREMENT_MAX_SEEDING_DAYS_NO_ACTIVITY_NON_FL', '90')),
    "RETIREMENT_NO_ACTIVITY_LEECHER_THRESHOLD_NON_FL": int(
        os.environ.get('RETIREMENT_NO_ACTIVITY_LEECHER_THRESHOLD_NON_FL', '0')),
    "RETIREMENT_NO_ACTIVITY_LAST_ACTIVE_DAYS_NON_FL": int(
        os.environ.get('RETIREMENT_NO_ACTIVITY_LAST_ACTIVE_DAYS_NON_FL', '7')),

    "TG_BOT_TOKEN_MONITOR": os.environ.get('TG_BOT_TOKEN_MONITOR', None),
    "TG_CHAT_ID": os.environ.get('TG_CHAT_ID', None),
    "TG_MAX_DELETED_ITEMS_IN_REPORT": int(os.environ.get('TG_MAX_DELETED_ITEMS_IN_REPORT', '20')),

    "DRY_RUN": os.environ.get('DRY_RUN', 'False').lower() == 'true',
    "LOG_LEVEL": os.environ.get('LOG_LEVEL', 'INFO').upper(),
}

STATE_UPLOADING_ZERO_SPEED = "uploading_zero_speed"
STATE_DOWNLOADING_ZERO_SPEED = "downloading_zero_speed"

logger = logging.getLogger("qb_smart_cleanup")


def setup_logging():
    log_level_val = getattr(logging, CONFIG["LOG_LEVEL"], logging.INFO)
    logging.basicConfig(
        level=log_level_val,
        format='%(asctime)s - %(levelname)s - %(name)s - [%(funcName)s] - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger('qbittorrentapi').setLevel(logging.INFO if log_level_val <= logging.INFO else log_level_val)


def load_monitoring_data(filepath: Path) -> dict:
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"⚠️ 无法加载或解析监控数据文件 {filepath}: {e}。将以空数据开始。")
    return {}


def save_monitoring_data(filepath: Path, data: dict):
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"💾 监控数据已保存至 {filepath}")
    except IOError as e:
        logger.error(f"💥 保存监控数据至 {filepath} 失败: {e}")


def connect_qbittorrent(config_dict: dict) -> Client | None:
    logger.info(f"🔗 尝试连接到 qBittorrent 服务: {config_dict['QBIT_HOST']}:{config_dict['QBIT_PORT']}")
    try:
        qb = Client(
            host=config_dict['QBIT_HOST'],
            port=config_dict['QBIT_PORT'],
            username=config_dict['QBIT_USERNAME'],
            password=config_dict['QBIT_PASSWORD'],
            VERIFY_WEBUI_CERTIFICATE=config_dict['QBIT_VERIFY_CERT'],
            REQUESTS_ARGS=config_dict['QBIT_REQUESTS_ARGS']
        )
        qb.auth_log_in()
        qbit_version = qb.app.version
        api_version = qb.app.web_api_version
        logger.info(f"✅ 成功连接到 qBittorrent (版本: v{qbit_version}, API 版本: {api_version})")
        return qb
    except LoginFailed as e:
        logger.error(f"💥 qBittorrent 登录失败: {e}")
    except APIConnectionError as e:
        logger.error(f"💥 无法连接到 qBittorrent: {e}")
    except Exception as e:
        logger.error(f"💥 连接 qBittorrent 时发生未知错误: {e}", exc_info=True)
    return None


def get_torrent_type_and_freeleech(torrent, config_dict: dict) -> tuple[str, bool]:
    category_type = "unclassified"
    is_freeleech = False
    torrent_tags_list = [tag.strip() for tag in torrent.tags.split(',') if tag.strip()] if torrent.tags else []

    if any(tag in config_dict["FREELEECH_TAGS"] for tag in torrent_tags_list):
        is_freeleech = True

    if torrent.category and torrent.category in config_dict["NON_BRUSHING_CATEGORIES"]:
        category_type = "non_brushing"
    elif any(tag in config_dict["NON_BRUSHING_TAGS"] for tag in torrent_tags_list):
        category_type = "non_brushing"
    elif torrent.category and torrent.category in config_dict["BRUSHING_CATEGORIES"]:
        category_type = "brushing"
    elif any(tag in config_dict["BRUSHING_TAGS"] for tag in torrent_tags_list):
        category_type = "brushing"

    if is_freeleech and category_type == "unclassified":
        category_type = "brushing"
        logger.debug(f"任务 '{torrent.name}' 被标记为 Freeleech 且未分类，将按“刷流”类型处理。")

    return category_type, is_freeleech


def delete_torrent_action(qb_client: Client, torrent_hash: str, torrent_name: str, delete_files: bool, dry_run: bool,
                          reason: str, tg_report_list: list) -> bool:
    action_prefix = "[演习模式] " if dry_run else ""
    file_action_msg = "任务和文件" if delete_files else "仅任务 (保留文件)"
    log_message = f"{action_prefix}请求删除 '{torrent_name}' ({torrent_hash}) - {file_action_msg}。原因: {reason}"
    logger.info(log_message)

    tg_report_list.append({
        "name": torrent_name,
        "hash": torrent_hash,
        "action_type": "删除" if not reason.startswith("荣退") else "荣退",
        "detail": file_action_msg,
        "reason": reason,
        "dry_run": dry_run
    })

    if not dry_run:
        try:
            qb_client.torrents_delete(torrent_hashes=torrent_hash, delete_files=delete_files)
            logger.info(f"✅ 已成功发起对 '{torrent_name}' 的删除请求。")
            return True
        except NotFound404Error:
            logger.warning(f"⚠️ 删除任务 '{torrent_name}' ({torrent_hash}) 时未找到 (可能已被其他方式删除)。")
            return True
        except Exception as e:
            logger.error(f"💥 删除任务 '{torrent_name}' ({torrent_hash}) 失败: {e}", exc_info=True)
            return False
    return True


def format_telegram_html(text: str) -> str:
    return html.escape(str(text))


def send_telegram_notification(config: dict, report_items: list, summary_stats: dict):
    bot_token = config["TG_BOT_TOKEN_MONITOR"]
    chat_id = config["TG_CHAT_ID"]

    if not bot_token or not chat_id:
        logger.info("ℹ️ Telegram Token 或 Chat ID 未配置，跳过发送通知。")
        return
    if summary_stats['deleted'] == 0 and summary_stats['monitored_new'] == 0 and summary_stats[
        'monitored_removed'] == 0:
        logger.info("ℹ️ 没有需要清理或监控状态变更的任务，跳过发送通知。")
        return

    message_parts = [f"<b>🗑️ qBittorrent 智能清理报告</b>{' (演习模式)' if config['DRY_RUN'] else ''}",
                     f"- 成功删除任务: {summary_stats['deleted']} 个 (其中自动荣退: {summary_stats['retired']} 个)",
                     f"- 新增监控任务: {summary_stats['monitored_new']} 个",
                     f"- 持续监控检查: {summary_stats['monitored_updated']} 次",
                     f"- 移除监控任务: {summary_stats['monitored_removed']} 个"]

    deleted_items_for_report = [item for item in report_items if item["action_type"] in ["删除", "荣退"]]
    if config["DRY_RUN"]:
        deleted_items_for_report = report_items

    if deleted_items_for_report:
        message_parts.append(
            "\n<b>🔍 清理详情</b> (最多显示前 " + str(config['TG_MAX_DELETED_ITEMS_IN_REPORT']) + " 条):")
        for i, item in enumerate(deleted_items_for_report):
            if i >= config['TG_MAX_DELETED_ITEMS_IN_REPORT']:
                message_parts.append(
                    f"\n<i>...还有 {len(deleted_items_for_report) - i} 个已操作任务未在此列出。</i>")
                break

            name_escaped = format_telegram_html(item['name'][:80])
            reason_escaped = format_telegram_html(item['reason'])
            action_type_emoji = "🏆" if item["action_type"] == "荣退" else "🗑️"
            dry_run_tag = " [演习]" if item["dry_run"] and not config["DRY_RUN"] else ""

            message_parts.append(
                f"\n{action_type_emoji} <b>{item['action_type']}{dry_run_tag}:</b> {name_escaped}\n"
                f"   <i>原因:</i> {reason_escaped}\n"
                f"   <i>操作:</i> 删除{format_telegram_html(item['detail'])}"
            )
    elif not (summary_stats['deleted'] or summary_stats['monitored_new'] or summary_stats['monitored_removed']):
        message_parts.append("\n<i>本轮未执行任何显著操作。</i>")

    full_message = "\n".join(message_parts)
    max_length = 4096
    if len(full_message.encode('utf-8')) > max_length:
        truncate_indicator = "\n\n... [消息过长，已截断] ..."
        temp_message = full_message
        while len(temp_message.encode('utf-8')) + len(truncate_indicator.encode('utf-8')) > max_length:
            temp_message = temp_message[:int(len(temp_message) * 0.9)]
            if not temp_message: break
        full_message = temp_message + truncate_indicator
        logger.warning("Telegram 消息体过长，已执行截断。")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': full_message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }

    try:
        response = requests.post(url, data=payload, timeout=20)
        response.raise_for_status()
        logger.info("✅ Telegram 通知已成功发送。")
    except requests.exceptions.Timeout:
        logger.error("💥 发送 Telegram 通知超时。")
    except requests.exceptions.HTTPError as e:
        logger.error(f"💥 发送 Telegram 通知失败 (HTTP 错误): {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"💥 发送 Telegram 通知失败 (RequestException): {e}")
    except Exception as e:
        logger.error(f"💥 发送 Telegram 通知时发生未知错误: {e}", exc_info=True)


def main():
    script_start_time = time.perf_counter()
    setup_logging()
    logger.info(f"🏁 ===== qBittorrent 智能清理脚本 (v{datetime.now().strftime('%Y%m%d.%H%M')}) 开始运行 =====")
    if CONFIG["DRY_RUN"]:
        logger.warning("🏜️ 演习模式 (DRY_RUN) 已激活。脚本将不会对 qBittorrent 进行任何实际更改。")

    monitoring_data = load_monitoring_data(CONFIG["MONITOR_FILE_PATH"])
    qb = connect_qbittorrent(CONFIG)
    telegram_report_items = []

    actions_this_run = {"deleted": 0, "retired": 0, "monitored_new": 0, "monitored_updated": 0, "monitored_removed": 0}

    if not qb:
        logger.critical("🚫 无法连接到 qBittorrent。脚本终止。")
        telegram_report_items.append({"action_type": "系统错误", "name": "连接失败", "detail": "无法连接qBittorrent",
                                      "reason": "请检查配置或服务状态", "dry_run": CONFIG["DRY_RUN"]})
        send_telegram_notification(CONFIG, telegram_report_items, actions_this_run)
        logger.info(f"⏱️ ===== 脚本因连接失败中止，耗时 {time.perf_counter() - script_start_time:.2f} 秒。 =====")
        return

    try:
        torrents = qb.torrents_info()
    except Exception as e:
        logger.error(f"💥 获取种子列表失败: {e}", exc_info=True)
        telegram_report_items.append(
            {"action_type": "系统错误", "name": "获取列表失败", "detail": "无法从qBittorrent获取种子列表",
             "reason": str(e), "dry_run": CONFIG["DRY_RUN"]})
        send_telegram_notification(CONFIG, telegram_report_items, actions_this_run)
        logger.info(f"⏱️ ===== 脚本因获取列表失败而中止，耗时 {time.perf_counter() - script_start_time:.2f} 秒。 =====")
        return

    if not torrents:
        logger.info("ℹ️ qBittorrent 中当前没有种子任务。无需操作。")
        current_qbit_hashes = set()
    else:
        current_qbit_hashes = {t.hash for t in torrents}

    current_time_seconds = time.time()

    for torrent in torrents:
        # --- BEGIN MODIFICATION ---
        # 新增的最高优先级跳过条件

        # 条件1: 任务添加时间少于24小时
        # torrent.added_on 是任务添加时的 Unix 时间戳 (单位: 秒)
        time_since_added_seconds = current_time_seconds - torrent.added_on
        is_recently_added = time_since_added_seconds < (24 * 60 * 60)  # 24小时的秒数

        # 条件2: 任务状态为“做种中”
        # "做种中" (Seeding) 通常包括以下状态:
        # - TorrentStates.UPLOADING: 正在上传
        # - TorrentStates.FORCED_UPLOAD: 强制上传
        # - TorrentStates.STALLED_UPLOAD: 停止上传/做种 (已完成)
        seeding_states = [
            TorrentStates.UPLOADING,
            TorrentStates.FORCED_UPLOAD,
            TorrentStates.STALLED_UPLOAD  # 通常表示已完成下载，等待上传机会
        ]
        is_in_seeding_state = torrent.state_enum in seeding_states

        if is_recently_added or is_in_seeding_state:
            reasons_to_skip = []
            if is_recently_added:
                hours_since_added = time_since_added_seconds / 3600
                reasons_to_skip.append(f"添加时间少于24小时 (已添加 {hours_since_added:.1f} 小时)")
            if is_in_seeding_state:
                reasons_to_skip.append(f"状态为〔做种中〕: {torrent.state}")
            
            logger.info(f"⏭️ 跳过任务 '{torrent.name}' ({torrent.hash}): {'; '.join(reasons_to_skip)}.")
            
            # 如果此任务之前在监控数据中，将其移除，因为它现在被优先跳过处理
            if torrent.hash in monitoring_data:
                logger.debug(f"➖ 由于优先跳过，从监控列表移除任务 '{torrent.name}' ({torrent.hash}).")
                del monitoring_data[torrent.hash]
                actions_this_run["monitored_removed"] += 1 # 确保 actions_this_run 已定义
            
            continue  # 跳到 torrents 循环中的下一个任务
        # --- END MODIFICATION ---

        category_type, is_freeleech = get_torrent_type_and_freeleech(torrent, CONFIG)
        torrent_handled_this_cycle = False

        if category_type == "non_brushing":
            if torrent.state_enum in (TorrentStates.ERROR, TorrentStates.MISSING_FILES, TorrentStates.UNKNOWN):
                reason = f"非刷流任务处于错误状态 '{torrent.state}'"
                if delete_torrent_action(qb, torrent.hash, torrent.name, delete_files=False, dry_run=CONFIG["DRY_RUN"],
                                         reason=reason, tg_report_list=telegram_report_items):
                    actions_this_run["deleted"] += 1
                    torrent_handled_this_cycle = True
            if torrent.hash in monitoring_data: # 即使没有错误，非刷流任务也不应该在监控中
                logger.info(f"ℹ️ 非刷流任务 '{torrent.name}' ({torrent.hash}) 存在于监控数据中，将被移除。")
                del monitoring_data[torrent.hash]
                actions_this_run["monitored_removed"] += 1

        elif category_type == "brushing":
            if torrent.state_enum in (TorrentStates.ERROR, TorrentStates.MISSING_FILES, TorrentStates.UNKNOWN):
                reason = f"刷流任务处于严重错误状态 '{torrent.state}'"
                if delete_torrent_action(qb, torrent.hash, torrent.name, delete_files=True, dry_run=CONFIG["DRY_RUN"],
                                         reason=reason, tg_report_list=telegram_report_items):
                    actions_this_run["deleted"] += 1
                    if torrent.hash in monitoring_data:
                        del monitoring_data[torrent.hash]
                        actions_this_run["monitored_removed"] += 1
                continue # 严重错误的任务处理完后直接跳到下一个任务

            effective_state = None
            # 注意: 此处的 STALLED_UPLOAD 是指任务完成下载后的做种停滞，与上面跳过条件中的 is_in_seeding_state 不同
            # is_in_seeding_state 用于初始跳过，这里的 effective_state 用于监控那些 *不活跃* 的做种任务
            if torrent.state_enum == TorrentStates.STALLED_UPLOAD: # 明确指做种停滞
                 effective_state = TorrentStates.STALLED_UPLOAD.value # 使用 .value 获取字符串表示
            elif torrent.state_enum == TorrentStates.PAUSED_UPLOAD: # 明确指做种暂停
                 effective_state = TorrentStates.PAUSED_UPLOAD.value
            elif torrent.state_enum == TorrentStates.UPLOADING and torrent.upspeed == 0:
                effective_state = STATE_UPLOADING_ZERO_SPEED
            elif torrent.state_enum == TorrentStates.STALLED_DOWNLOAD and torrent.progress < 1:
                effective_state = TorrentStates.STALLED_DOWNLOAD.value
            elif torrent.state_enum == TorrentStates.DOWNLOADING and torrent.downspeed == 0 and torrent.progress < 1:
                effective_state = STATE_DOWNLOADING_ZERO_SPEED
            # 注意：TorrentStates.STOPPED_UPLOAD 在原脚本中是 STALLED_UPLOAD, PAUSED_UPLOAD, STOPPED_UPLOAD
            # qbittorrentapi TorrentStates 没有 STOPPED_UPLOAD，可能是笔误或旧版API。
            # 假设原意是包含已暂停上传的状态，PAUSED_UPLOAD 已经覆盖。

            if effective_state:
                if torrent.hash not in monitoring_data or monitoring_data[torrent.hash][
                    'monitored_state'] != effective_state:
                    logger.info(
                        f"🔎 [新增监控] 任务 '{torrent.name}' ({torrent.hash}) 进入受监控状态: {effective_state} (FL: {is_freeleech}, 下载者: {torrent.num_leechs})")
                    monitoring_data[torrent.hash] = {
                        "name": torrent.name,
                        "monitored_state": effective_state,
                        "first_seen_in_state_timestamp": current_time_seconds,
                        "is_freeleech": is_freeleech,
                    }
                    actions_this_run["monitored_new"] += 1
                else:
                    monitored_entry = monitoring_data[torrent.hash]
                    time_in_state_seconds = current_time_seconds - monitored_entry['first_seen_in_state_timestamp']
                    time_in_state_minutes = time_in_state_seconds / 60
                    actions_this_run["monitored_updated"] += 1

                    should_delete_based_on_monitoring = False
                    deletion_reason = ""
                    current_monitor_threshold_minutes = CONFIG["USELESS_STATE_MONITOR_DURATION_MINUTES"]

                    # 检查 effective_state 是否是表示做种停滞的状态
                    if effective_state in (TorrentStates.STALLED_UPLOAD.value, STATE_UPLOADING_ZERO_SPEED, TorrentStates.PAUSED_UPLOAD.value):
                        if monitored_entry['is_freeleech']:
                            if torrent.num_leechs == 0: # 仅当没有下载者时，FL任务的停滞才使用更长的监控时间
                                current_monitor_threshold_minutes = CONFIG[
                                    "FREELEECH_STALLED_NO_LEECHERS_MONITOR_DURATION_MINUTES"]
                        elif torrent.num_leechs > 0: # 非FL任务，如果有下载者但仍然停滞
                            current_monitor_threshold_minutes = CONFIG["STALLED_WITH_LEECHERS_MONITOR_DURATION_MINUTES"]
                        # 如果是非FL任务且无下载者，或者FL任务有下载者，则使用默认的 USELESS_STATE_MONITOR_DURATION_MINUTES

                    if time_in_state_minutes >= current_monitor_threshold_minutes:
                        should_delete_based_on_monitoring = True
                        deletion_reason = f"处于状态 '{effective_state}' 已达 {time_in_state_minutes:.1f} 分钟 (阈值 {current_monitor_threshold_minutes} 分钟). FL: {is_freeleech}, 下载者: {torrent.num_leechs}."

                    if should_delete_based_on_monitoring:
                        if delete_torrent_action(qb, torrent.hash, torrent.name, delete_files=True,
                                                 dry_run=CONFIG["DRY_RUN"], reason=deletion_reason,
                                                 tg_report_list=telegram_report_items):
                            actions_this_run["deleted"] += 1
                            torrent_handled_this_cycle = True
                            del monitoring_data[torrent.hash]
                            actions_this_run["monitored_removed"] += 1
            else: # 任务状态良好 (不是上述定义的 effective_state)
                if torrent.hash in monitoring_data:
                    logger.info(f"🟢 任务 '{torrent.name}' ({torrent.hash}) 当前状态 '{torrent.state}' 良好或不符合监控条件。从监控列表中移除。")
                    del monitoring_data[torrent.hash]
                    actions_this_run["monitored_removed"] += 1

                # 只有在任务未因监控被删除，且状态良好时，才考虑荣退逻辑
                # 并且，荣退逻辑只针对正在上传或强制上传的任务 (即活跃的做种任务)
                if not torrent_handled_this_cycle and torrent.state_enum in (TorrentStates.UPLOADING,
                                                                             TorrentStates.FORCED_UPLOAD):
                    seeding_time_days = torrent.seeding_time / (60 * 60 * 24) if torrent.seeding_time else 0
                    last_activity_days_ago = (current_time_seconds - torrent.last_activity) / (
                            60 * 60 * 24) if torrent.last_activity > 0 else float('inf')

                    attempt_retirement = False
                    retirement_reason = ""

                    if not is_freeleech:
                        if (torrent.ratio >= CONFIG["RETIREMENT_MIN_RATIO"] and
                                torrent.num_leechs <= CONFIG["RETIREMENT_LOW_DEMAND_LEECHERS"] and
                                seeding_time_days >= CONFIG["RETIREMENT_MIN_SEEDING_DAYS"]):
                            attempt_retirement = True
                            retirement_reason = (
                                f"荣退: 分享率 {torrent.ratio:.2f} (>{CONFIG['RETIREMENT_MIN_RATIO']}), "
                                f"下载者 {torrent.num_leechs} (<{CONFIG['RETIREMENT_LOW_DEMAND_LEECHERS']}), "
                                f"做种 {seeding_time_days:.1f} 天 (>{CONFIG['RETIREMENT_MIN_SEEDING_DAYS']})")
                        elif (seeding_time_days >= CONFIG["RETIREMENT_MAX_SEEDING_DAYS_NO_ACTIVITY_NON_FL"] and
                              torrent.num_leechs <= CONFIG["RETIREMENT_NO_ACTIVITY_LEECHER_THRESHOLD_NON_FL"] and
                              last_activity_days_ago >= CONFIG["RETIREMENT_NO_ACTIVITY_LAST_ACTIVE_DAYS_NON_FL"]):
                            attempt_retirement = True
                            retirement_reason = (
                                f"荣退 (非FL): 做种 {seeding_time_days:.1f} 天 (>{CONFIG['RETIREMENT_MAX_SEEDING_DAYS_NO_ACTIVITY_NON_FL']}), "
                                f"下载者 {torrent.num_leechs} (<{CONFIG['RETIREMENT_NO_ACTIVITY_LEECHER_THRESHOLD_NON_FL']}), "
                                f"最后活动于 {last_activity_days_ago:.1f} 天前 (>{CONFIG['RETIREMENT_NO_ACTIVITY_LAST_ACTIVE_DAYS_NON_FL']})")
                    if attempt_retirement:
                        if delete_torrent_action(qb, torrent.hash, torrent.name, delete_files=True,
                                                 dry_run=CONFIG["DRY_RUN"], reason=retirement_reason,
                                                 tg_report_list=telegram_report_items):
                            actions_this_run["deleted"] += 1
                            actions_this_run["retired"] += 1
                            # 如果因荣退被删除，且仍在监控中（理论上不应该，因为状态良好时会先移除），也移除
                            if torrent.hash in monitoring_data:
                                del monitoring_data[torrent.hash]
                                actions_this_run["monitored_removed"] += 1
                            # torrent_handled_this_cycle = True # 标记已处理，避免后续逻辑 (虽然荣退是最后一步)

        elif category_type == "unclassified":
            logger.debug(f"ℹ️ 任务 '{torrent.name}' ({torrent.hash}) 未分类。跳过详细处理逻辑。")
            if torrent.hash in monitoring_data: # 未分类任务也不应该在监控中
                logger.info(f"ℹ️ 未分类任务 '{torrent.name}' ({torrent.hash}) 存在于监控数据中，将被移除。")
                del monitoring_data[torrent.hash]
                actions_this_run["monitored_removed"] += 1

    # 清理监控数据中已不存在于 qBittorrent 的任务条目
    hashes_to_remove_from_monitor = set(monitoring_data.keys()) - current_qbit_hashes
    if hashes_to_remove_from_monitor:
        for h_to_remove in hashes_to_remove_from_monitor:
            entry_name = monitoring_data.pop(h_to_remove, {}).get('name', '未知任务(已消失)')
            logger.info(f"🧹 清理过时监控条目: '{entry_name}' ({h_to_remove}) (任务不再存在于 qBittorrent)。")
            actions_this_run["monitored_removed"] += 1

    save_monitoring_data(CONFIG["MONITOR_FILE_PATH"], monitoring_data)

    logger.info("📊 --- 本轮运行摘要 ---")
    logger.info(f"成功删除任务: {actions_this_run['deleted']} 个 (其中自动荣退: {actions_this_run['retired']} 个)")
    logger.info(
        f"监控状态 - 新增: {actions_this_run['monitored_new']}, 更新检查: {actions_this_run['monitored_updated']}, 移除: {actions_this_run['monitored_removed']}")

    send_telegram_notification(CONFIG, telegram_report_items, actions_this_run)

    if CONFIG["DRY_RUN"]:
        logger.warning("🏜️ 演习模式 (DRY_RUN) 已激活。未对 qBittorrent 进行任何实际更改。")

    logger.info(f"🎉 ===== 脚本执行完毕，耗时 {time.perf_counter() - script_start_time:.2f} 秒。 =====")


if __name__ == "__main__":
    main()

