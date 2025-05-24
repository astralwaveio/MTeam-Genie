#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件: manage_upload_speed.py
# 描述: 定时随机设置 qBittorrent 上传速度。
#       速度范围: 768 KB/s 到 2048 KB/s
import datetime
import logging
import os
import random

from qbittorrentapi import Client, APIConnectionError, LoginFailed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(funcName)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# qBittorrent 连接信息 (从环境变量读取)
QBIT_HOST = os.environ.get('QBIT_HOST', 'http://localhost')
QBIT_PORT = os.environ.get('QBIT_PORT', '8080')
QBIT_USERNAME = os.environ.get('QBIT_USERNAME')
QBIT_PASSWORD = os.environ.get('QBIT_PASSWORD')

# 上传速度限制范围 (KB/s)
MIN_UPLOAD_SPEED_KBPS = 768
MAX_UPLOAD_SPEED_KBPS = 2048
BYTES_IN_KILOBYTE = 1024  # 1 KB = 1024 Bytes

# 转换为字节/秒
MIN_UPLOAD_SPEED_BPS = MIN_UPLOAD_SPEED_KBPS * BYTES_IN_KILOBYTE
MAX_UPLOAD_SPEED_BPS = MAX_UPLOAD_SPEED_KBPS * BYTES_IN_KILOBYTE


def set_random_upload_speed():
    """
    设置 qBittorrent 的上传速度限制为一个随机值。
    """
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{current_time_str}] 🚀 开始执行上传速度调整脚本...")

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
        random_speed_bps = random.randint(MIN_UPLOAD_SPEED_BPS, MAX_UPLOAD_SPEED_BPS)
        random_speed_kbps = random_speed_bps / BYTES_IN_KILOBYTE
        qbit.app_set_preferences(prefs={'up_limit': random_speed_bps})
        logger.info(
            f"[{current_time_str}] ✅ 已将上传速度限制随机设置为: {random_speed_kbps:.2f} KB/s ({random_speed_bps} B/s)")
    except LoginFailed:
        logger.error(f"[{current_time_str}] 🚫 错误: qBittorrent 登录失败! 请检查 QBIT_USERNAME 和 QBIT_PASSWORD。")
    except APIConnectionError as e:
        logger.error(f"[{current_time_str}] 🚫 错误: 无法连接到 qBittorrent WebUI at {QBIT_HOST}。详情: {e}")
    except Exception as e:
        logger.error(f"[{current_time_str}] 🚫 发生未知错误: {e}")
    finally:
        logger.info(f"[{current_time_str}] 🏁 上传速度调整脚本执行完毕。")


if __name__ == "__main__":
    set_random_upload_speed()
