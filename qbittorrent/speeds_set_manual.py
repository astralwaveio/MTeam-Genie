#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: set_manual_speeds.py
# 描述: 手动设置 qBittorrent 的上传和下载速度。
#       上传速度: 512 KB/s
#       下载速度: 5 MB/s

import datetime
import logging
import os

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

# 速度单位转换
BYTES_IN_KILOBYTE = 1024
BYTES_IN_MEGABYTE = 1024 * 1024

# 手动设置的速度限制
MANUAL_UPLOAD_SPEED_KBPS = 512
MANUAL_DOWNLOAD_SPEED_MBPS = 5

MANUAL_UPLOAD_SPEED_BPS = MANUAL_UPLOAD_SPEED_KBPS * BYTES_IN_KILOBYTE
MANUAL_DOWNLOAD_SPEED_BPS = MANUAL_DOWNLOAD_SPEED_MBPS * BYTES_IN_MEGABYTE


def main():
    """
    手动设置 qBittorrent 的上传和下载速度限制。
    """
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{current_time_str}] 🛠️  开始执行手动速度设置脚本...")

    if not QBIT_USERNAME or not QBIT_PASSWORD:
        print(f"[{current_time_str}] ❌ 错误: 请设置 QBIT_USERNAME 和 QBIT_PASSWORD 环境变量。")
        return

    try:
        # 连接到 qBittorrent WebUI
        logger.info(f"[{current_time_str}] 🔗 正在尝试连接到 qBittorrent at {QBIT_HOST}...")
        qbit = Client(
            host=QBIT_HOST,
            port=int(os.environ.get("QBIT_PORT", "8080")),
            username=QBIT_USERNAME,
            password=QBIT_PASSWORD,
            REQUESTS_ARGS={'timeout': (10, 30)}
        )
        logger.info(f"[{current_time_str}] ✅ 成功连接到 qBittorrent!")

        # 设置上传速度限制
        qbit.app_set_preferences(prefs={'up_limit': MANUAL_UPLOAD_SPEED_BPS})
        logger.info(
            f"[{current_time_str}] ✅ 已将上传速度限制设置为: {MANUAL_UPLOAD_SPEED_KBPS} KB/s ({MANUAL_UPLOAD_SPEED_BPS} B/s)")

        # 设置下载速度限制
        qbit.app_set_preferences(prefs={'dl_limit': MANUAL_DOWNLOAD_SPEED_BPS})
        logger.info(
            f"[{current_time_str}] ✅ 已将下载速度限制设置为: {MANUAL_DOWNLOAD_SPEED_MBPS} MB/s ({MANUAL_DOWNLOAD_SPEED_BPS} B/s)")

    except LoginFailed:
        logger.error(f"[{current_time_str}] ❌ 错误: qBittorrent 登录失败! 请检查 QBIT_USERNAME 和 QBIT_PASSWORD。")
    except APIConnectionError as e:
        logger.error(f"[{current_time_str}] ❌ 错误: 无法连接到 qBittorrent WebUI at {QBIT_HOST}。详情: {e}")
    except Exception as e:
        logger.error(f"[{current_time_str}] ❌ 发生未知错误: {e}")
    finally:
        logger.error(f"[{current_time_str}] 🏁 手动速度设置脚本执行完毕。")


if __name__ == "__main__":
    main()
