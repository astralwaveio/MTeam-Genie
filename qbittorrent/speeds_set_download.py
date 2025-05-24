#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: manage_download_speed.py
# 描述: 定时调整 qBittorrent 下载速度。
#       北京/上海时间 00:00-09:00 限制为 40 MB/s
#       北京/上海时间 09:00-24:00 限制为 18 MB/s
import datetime
import logging
import os

import pytz
from qbittorrentapi import Client, APIConnectionError, LoginFailed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# qBittorrent 连接信息 (从环境变量读取)
QBIT_HOST = os.environ.get('QBIT_HOST', 'http://localhost:8080')
QBIT_PORT = os.environ.get("QBIT_PORT", "8080"),
QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')
QBIT_VERIFY_CERT = os.environ.get('QBIT_VERIFY_CERT', 'True').lower() != 'false'

# 速度限制 (字节/秒)
SPEED_LIMIT_HIGH_MBPS = 40
SPEED_LIMIT_LOW_MBPS = 18
BYTES_IN_MEGABYTE = 1024 * 1024

SPEED_LIMIT_HIGH_BPS = SPEED_LIMIT_HIGH_MBPS * BYTES_IN_MEGABYTE
SPEED_LIMIT_LOW_BPS = SPEED_LIMIT_LOW_MBPS * BYTES_IN_MEGABYTE

# 时区设置
TIMEZONE_SHANGHAI = pytz.timezone('Asia/Shanghai')


def main():
    """
    根据当前北京/上海时间设置 qBittorrent 的下载速度限制。
    """
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{current_time_str}] 🚀 开始执行下载速度调整脚本...")

    if not QBIT_USERNAME or not QBIT_PASSWORD:
        logger.info(f"[{current_time_str}] 🚫 错误: 请设置 QBIT_USERNAME 和 QBIT_PASSWORD 环境变量。")
        return

    try:
        logger.info(f"[{current_time_str}] 🔗 正在尝试连接到 qBittorrent at {QBIT_HOST}...")
        qbit = Client(
            host=QBIT_HOST,
            port=int(os.environ.get("QBIT_PORT", "8080")),
            username=QBIT_USERNAME,
            password=QBIT_PASSWORD,
            REQUESTS_ARGS={'timeout': (10, 30)}
        )
        logger.info(f"[{current_time_str}] ✅ 成功连接到 qBittorrent!")
        now_shanghai = datetime.datetime.now(TIMEZONE_SHANGHAI)
        current_hour = now_shanghai.hour
        shanghai_time_str = now_shanghai.strftime('%H:%M:%S')
        if 0 <= current_hour < 9:
            target_speed_bps = SPEED_LIMIT_HIGH_BPS
            speed_description = f"{SPEED_LIMIT_HIGH_MBPS} MB/s (高速)"
            logger.info(f"[{current_time_str}] ⏰ 当前北京/上海时间 {shanghai_time_str} (属于 00:00-09:00 高速时段)")
        else:
            target_speed_bps = SPEED_LIMIT_LOW_BPS
            speed_description = f"{SPEED_LIMIT_LOW_MBPS} MB/s (低速)"
            logger.info(f"[{current_time_str}] ⏰ 当前北京/上海时间 {shanghai_time_str} (属于 09:00-24:00 低速时段)")
        current_preferences = qbit.app_preferences()
        current_dl_limit = current_preferences.get('dl_limit', -1)  # 获取当前下载限制，如果未设置则默认为-1
        if current_dl_limit == target_speed_bps:
            logger.info(
                f"[{current_time_str}] ℹ️  下载速度限制已经是 {speed_description} ({target_speed_bps} B/s)，无需更改。")
        else:
            qbit.app_set_preferences(prefs={'dl_limit': target_speed_bps})
            logger.info(f"[{current_time_str}] ✅ 已将下载速度限制设置为: {speed_description} ({target_speed_bps} B/s)")
    except LoginFailed:
        logger.error(f"[{current_time_str}] 🚫 错误: qBittorrent 登录失败! 请检查 QBIT_USERNAME 和 QBIT_PASSWORD。")
    except APIConnectionError as e:
        logger.error(f"[{current_time_str}] 🚫 错误: 无法连接到 qBittorrent WebUI at {QBIT_HOST}。详情: {e}")
    except Exception as e:
        logger.error(f"[{current_time_str}] 🚫 发生未知错误: {e}")
    finally:
        logger.info(f"[{current_time_str}]🏁 下载速度调整脚本执行完毕。")


if __name__ == "__main__":
    main()
