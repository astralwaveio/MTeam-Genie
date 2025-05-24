#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Python 脚本：获取图片，单张发送到 Telegram，带5秒间隔，配置从环境变量读取，自定义标题

# ============== 配置变量 ================
# 图片来源信息列表，每个元素是一个包含 URL 和对应标题的字典
IMAGE_SOURCES = [
    {
        "url": "https://dayu.qqsuu.cn/moyurili/apis.php",
        "caption": "🦑 摸鱼日历"
    },
    {
        "url": "https://dayu.qqsuu.cn/moyuribao/apis.php",
        "caption": "📰 摸鱼日报"  # 使用报纸 emoji
    },
    {
        "url": "https://dayu.qqsuu.cn/weiyujianbao/apis.php",
        "caption": "📄 新闻简报"  # 使用文件 emoji
    },
    {
        "url": "https://dayu.qqsuu.cn/qingganhuayuan/apis.php",
        "caption": "🌸 情感花园"  # 使用花朵 emoji
    },
]

# HTTP 请求头，模拟浏览器访问
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 发送图片间的延迟时间（秒）
SEND_DELAY_SECONDS = 5
# =========================================

import io  # 用于在内存中处理字节流
import os  # 用于读取环境变量
import sys  # 用于 sys.exit 退出脚本
import time  # 用于 time.sleep 实现延迟

import requests
from PIL import Image  # 从Pillow库导入Image模块，用于图片处理 (虽然不拼接，但可能仍用于验证图片)


def print_log(message):
    """打印日志信息到控制台。"""
    print(f"[日志] {message}")


def get_env_variable(var_name):
    """从环境变量中获取值，如果未设置则打印错误并退出。"""
    value = os.getenv(var_name)
    if value is None:
        print_log(f"错误：环境变量 {var_name} 未设置。请设置该变量后重试。")
        sys.exit(1)
    return value


def fetch_image_bytes(url):
    """
    从给定的 URL 获取图片，并以字节形式返回图片内容。
    如果获取失败，则返回 None。
    """
    print_log(f"开始从 URL 下载图片: {url}")
    try:
        # 发送GET请求，设置超时时间为30秒，并添加请求头
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        # 如果请求失败 (状态码 4XX 或 5XX), 则抛出 HTTPError 异常
        response.raise_for_status()
        # 尝试打开图片，验证是否是有效的图片格式
        try:
            Image.open(io.BytesIO(response.content))
            print_log(f"图片下载并验证成功: {url} (状态码: {response.status_code})")
            return response.content  # 返回图片的二进制内容
        except IOError:  # Pillow 无法识别图片格式
            print_log(f"下载的内容不是有效的图片格式: {url}")
            return None
    except requests.exceptions.HTTPError as http_err:
        # 捕获 HTTP 错误
        print_log(
            f"下载图片时发生 HTTP 错误 {url}: {http_err} (状态码: {http_err.response.status_code if http_err.response else 'N/A'})")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        # 捕获连接错误
        print_log(f"下载图片时发生连接错误 {url}: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        # 捕获超时错误
        print_log(f"下载图片超时 {url}: {timeout_err}")
        return None
    except requests.exceptions.RequestException as e:
        # 捕获所有其他 requests 相关的异常
        print_log(f"下载图片失败 {url}: {e}")
        return None


def send_image_to_telegram(bot_token, chat_id, image_bytes, caption="", image_filename="image.png"):
    """
    将单张图片 (字节数据) 发送到指定的 Telegram 聊天。
    """
    if image_bytes is None:
        print_log("没有图片字节数据可以发送到 Telegram。")
        return False

    print_log(f"准备发送图片 '{image_filename}' (标题: '{caption}') 到 Telegram Chat ID: {chat_id}")
    # Telegram Bot API 的 sendPhoto 接口
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    # 将字节数据包装在 BytesIO 中
    image_stream = io.BytesIO(image_bytes)
    image_stream.seek(0)  # 确保指针在开头

    # 'files' 参数用于上传文件
    files = {'photo': (image_filename, image_stream, 'image/png')}  # 假设图片是PNG
    # 'params' 参数用于传递 chat_id 和 caption
    params = {'chat_id': chat_id}
    if caption:  # 只有当标题不为空时才添加
        params['caption'] = caption

    try:
        # 发送 POST 请求，设置超时时间为60秒
        response = requests.post(url, files=files, params=params, timeout=60)
        response.raise_for_status()  # 检查请求是否成功
        response_data = response.json()
        if response_data.get("ok"):  # Telegram API 返回的 JSON 中 'ok' 字段为 true 表示成功
            print_log(f"图片 {image_filename} 成功发送到 Telegram！")
            return True
        else:
            print_log(f"发送图片 {image_filename} 到 Telegram 失败: {response_data.get('description', response.text)}")
            return False
    except requests.exceptions.RequestException as e:
        print_log(f"发送图片 {image_filename} 到 Telegram 时发生网络错误: {e}")
        return False
    except Exception as e:
        print_log(f"发送图片 {image_filename} 到 Telegram 时发生未知错误: {e}")
        return False


def main():
    """
    主函数，用于编排脚本的执行流程。
    """
    print_log("脚本开始运行...")

    # 从环境变量读取 Telegram 配置
    telegram_bot_token = get_env_variable("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = get_env_variable("TELEGRAM_CHAT_ID_1")

    fetched_images_data = []  # 用于存储下载的图片字节数据及其对应的标题
    for source_info in IMAGE_SOURCES:
        url = source_info["url"]
        caption = source_info["caption"]
        img_bytes = fetch_image_bytes(url)
        if img_bytes:  # 只有成功获取到图片字节数据才添加到列表中
            fetched_images_data.append({"bytes": img_bytes, "caption": caption, "original_url": url})
        else:
            print_log(f"警告：未能从 {url} 下载图片或图片无效，将跳过此图片。")

    if not fetched_images_data:  # 如果一张图片都未能下载
        print_log("未能下载任何有效图片。脚本终止。")
        return  # 结束脚本

    num_images_to_send = len(fetched_images_data)
    for index, image_data in enumerate(fetched_images_data):
        img_bytes = image_data["bytes"]
        caption = image_data["caption"]
        original_url = image_data["original_url"]  # 用于生成唯一的文件名

        print_log(f"准备发送第 {index + 1}/{num_images_to_send} 张图片 (来源: {original_url})...")
        # 为每张图片生成一个基于来源URL的文件名（可选，但有助于日志和区分）
        # 简单处理，取URL最后一部分作为基础文件名
        base_filename = original_url.split('/')[-1] if '/' in original_url else f"image_{index + 1}"
        image_filename = f"{base_filename}.png"

        success = send_image_to_telegram(
            telegram_bot_token,
            telegram_chat_id,
            img_bytes,
            caption,  # 为每张图片使用其特定的标题
            image_filename
        )

        if success and index < num_images_to_send - 1:  # 如果发送成功且不是最后一张图片
            print_log(f"等待 {SEND_DELAY_SECONDS} 秒后发送下一张图片...")
            time.sleep(SEND_DELAY_SECONDS)
        elif not success:
            print_log(f"发送第 {index + 1} 张图片 (来源: {original_url}) 失败，继续尝试下一张（如果有）。")

    print_log("脚本运行结束。")


if __name__ == "__main__":
    main()
