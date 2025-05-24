# M-Team 精灵：qBittorrent 与 Telegram 自动化套件 🚀

[![Stars](https://img.shields.io/github/stars/astralwaveio/MTeam-Genie?style=social)](https://github.com/astralwaveio/MTeam-Genie/stargazers) [![Forks](https://img.shields.io/github/forks/astralwaveio/MTeam-Genie?style=social)](https://github.com/astralwaveio/MTeam-Genie/network/members) [![Issues](https://img.shields.io/github/issues/astralwaveio/MTeam-Genie)](https://github.com/astralwaveio/MTeam-Genie/issues) [![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) 

👋 欢迎来到 **M-Team 精灵**项目！如果您是一位 Private Tracker (PT) 爱好者，尤其是 **M-Team** 用户，并且希望通过自动化脚本提升您的站点使用体验、高效管理 qBittorrent 下载任务，并通过 Telegram 机器人实时掌控一切，那么这套精心打造的 Python 脚本集合正是为您准备的！

本项目旨在解决 PT 日常使用中的一些痛点，例如：

* 手动搜索和添加种子的繁琐。
* 难以有效管理大量刷流任务。
* 错过重要站点的新种和优惠信息。
* qBittorrent 客户端缺乏灵活的自动化管理能力。

通过 M-Team 精灵，您可以轻松实现诸多自动化功能，让您的 PT 之旅更加轻松愉快。

## ✨ 项目亮点与核心功能

M-Team 精灵包含多个模块，各司其职，共同为您打造高效的 PT & 下载体验：

### 🤖 M-Team Telegram 助手 (`telegram/mt_helper.py`) - 您的智能 PT 伙伴！

这是项目的核心交互工具，一个功能丰富的 Telegram 机器人，让您随时随地掌控 M-Team 和 qBittorrent：

* 🔍 **关键词智能搜种**: 在 M-Team 快速、准确地搜索您想要的资源。结果清晰展示，包含种子名称、大小、M-Team ID、站点内部分类、详细副标题以及**实时优惠状态**（免费、促销等）。
* ➕ **一键轻松下载**: 从搜索结果中直接选择，或通过输入 M-Team 种子 ID，即可将种子任务一键添加到您的 qBittorrent 客户端，并支持在添加时**选择指定分类**。
* 🔄 **灵活任务管理**: 远程修改 qBittorrent 中已有任务的分类，方便整理。
* 🗑️ **便捷删除任务**: 从 qBittorrent 中删除指定任务，并可选择是否**同时从硬盘删除相关文件**。
* 📊 **实时状态查询**: 随时查看 qBittorrent 中的任务列表（支持分页）和所有已配置的分类。
* 🔐 **安全多用户授权**: 通过环境变量配置，允许多个授权的 Telegram 用户安全地操作机器人。

### Ⓜ️ M-Team 站点自动化 (`mteam/`) - 刷流养号，快人一步！

* 🌊 **全自动智能刷流 (`brush.py`)**:
    * 自动检测 M-Team 上的免费、2X 免费或其他优惠种子。
    * 智能筛选符合条件的种子（可配置大小、类型等）。
    * 自动将选中的种子添加到 qBittorrent 开始下载。
    * 建议配合 `qbittorrent/tasks_cleanup.py` 脚本使用，实现下载完成后的自动清理，形成高效刷流闭环。
* 🔔 **RSS 新种实时监控 (`rss_monitor.py`)**:
    * 持续监控您在 M-Team 配置的 RSS Feed 地址。
    * 一旦发现新发布的种子，立即提取关键信息。
    * 通过 Telegram 机器人将新种详情（如标题、链接、大小、优惠状态等）推送到指定用户或群组，让您不再错过任何热门或稀有资源！

### ⚙️ qBittorrent 客户端增强管理 (`qbittorrent/`) - 下载管理更智能！

* 🧹 **下载任务自动清理 (`tasks_cleanup.py`)**:
    * 自动检测并清理 qBittorrent 中已完成的刷流任务（例如，达到特定分享率或做种时间）。
    * 清理长时间无速度、连接数过低或其他符合自定义规则的无用任务。
    * 保持您的 qBittorrent 客户端整洁高效，释放系统资源。
* 🚀 **动态智能调速**:
    * `speeds_set_download.py`: 根据当前整体网络带宽使用情况或特定规则，自动调整 qBittorrent 的全局或特定任务的下载速度限制，避免占满带宽影响其他应用。
    * `speeds_set_upload.py`: 根据预设的时间段（例如，夜间空闲时段）或网络条件，自动调整上传速度限制策略，最大化分享率或在需要时降低带宽占用。
    * `speeds_set_manual.py`: 提供一个手动方式，快速清除所有由脚本设定的临时限速规则，将 qBittorrent 恢复到默认或用户手动设置的限速状态。

### 📢 Telegram 便捷推送工具 (`telegram/`)

* 📰 **每日新闻自动推送 (`daily_news_dayu.py`)**:
    * 自动从指定新闻源（如“大鱼号”或其他可配置的RSS/API）抓取每日重点新闻或您感兴趣的资讯。
    * 格式化新闻内容，并通过 Telegram 机器人定时推送到指定的用户或群组，让您轻松获取每日简报。

## 📂 项目结构概览



.
├── LICENSE
├── mteam/                     # M-Team 相关脚本
│   ├── brush.py             # 全自动刷流脚本
│   └── rss_monitor.py       # RSS 自动解析与推送
├── qbittorrent/               # qBittorrent 相关脚本
│   ├── speeds_set_download.py # 自动调整下载速度
│   ├── speeds_set_manual.py   # 手动清除限速
│   ├── speeds_set_upload.py   # 自动调整上传速度
│   └── tasks_cleanup.py       # 任务自动清理
├── README.md                  # 就是您现在看到的这个文件
├── requirements.txt           # 项目依赖
├── telegram/                  # Telegram Bot 及推送脚本
│   ├── daily_news_dayu.py   # 每日新闻推送
│   └── mt_helper.py         # M-Team Telegram 助手核心脚本
└── tmp/                       # 临时文件目录 (可选, 用于存放运行时产生的临时文件)


## 🛠️ 环境准备

在开始之前，请确保您的系统环境满足以下基本要求：

* **Python**: 版本 3.8 或更高。
* **pip**: Python 包管理工具 (通常随 Python 一同安装)。
* **网络连接**: 脚本需要访问 Internet 来与 M-Team API, qBittorrent WebUI, Telegram API 等进行通信。
* **qBittorrent**: 需要已安装并运行 qBittorrent 客户端，并已开启 WebUI 功能。

## ⚙️ 安装与配置

请按照以下步骤设置您的 M-Team 精灵：

1.  **克隆项目仓库**:
    如果您是通过 `git` 管理项目，请克隆本仓库到您的本地计算机或服务器：
    ```bash
    git clone [https://github.com/astralwaveio/MTeam-Genie.git](https://github.com/astralwaveio/MTeam-Genie.git)
    cd MTeam-Genie
    ```
    请务必将 `astralwaveio/MTeam-Genie` 替换为实际的 GitHub 用户名和仓库名称。如果您是直接下载的 ZIP 包，请解压。

2.  **安装依赖库**:
    项目依赖一些第三方 Python 库，这些库在 `requirements.txt` 文件中列出。请在项目根目录下打开终端或命令行，运行以下命令安装：
    ```bash
    pip install -r requirements.txt
    ```
    建议在 Python 虚拟环境 (venv 或 conda) 中安装，以避免与系统全局 Python 环境冲突。

3.  **核心配置：环境变量**:
    为了保障您的账户安全和配置的灵活性，本项目**强烈推荐**使用**环境变量**来设置所有敏感信息和关键参数，而不是直接修改代码。

    **为什么使用环境变量？**
    * **安全**: 避免将 API 密钥、密码等直接写入代码，防止意外泄露。
    * **便捷**: 在不同环境（开发、生产）或不同用户间切换配置时，无需修改代码。
    * **标准化**: 许多部署平台（如 Docker, 青龙面板）都原生支持环境变量配置。

    **通用关键环境变量 (多个脚本可能共用):**

    | 环境变量名                     | 描述                                                                  | 示例值                                         |
    | ------------------------------ | --------------------------------------------------------------------- | ---------------------------------------------- |
    | `TG_BOT_TOKEN`                 | 您的 Telegram Bot 的 Token (从 BotFather 获取)                        | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`    |
    | `TG_ALLOWED_CHAT_IDS`          | 允许使用此 Bot 的 Telegram 用户或群组的 Chat ID (多个用逗号 `,` 分隔) | `123456789,987654321`                          |
    | `MT_APIKEY`                    | 您在 M-Team 站点的 API 密钥 (通常在个人控制面板获取)                  | `your_mteam_api_key_here`                      |
    | `MT_HOST`                      | M-Team API 服务器地址 (通常默认为 `https://api.m-team.cc` 即可)       | `https://api.m-team.cc`                        |
    | `QBIT_HOST`                    | 您的 qBittorrent WebUI 地址                                           | `http://localhost` 或 `https://qb.example.com` |
    | `QBIT_PORT`                    | qBittorrent WebUI 端口                                                | `8080`                                         |
    | `QBIT_USERNAME`                | qBittorrent WebUI 登录用户名                                          | `admin`                                        |
    | `QBIT_PASSWORD`                | qBittorrent WebUI 登录密码                                            | `your_qb_password`                             |
    | `QBIT_DEFAULT_CATEGORY_FOR_MT` | (可选) M-Team 助手添加种子到 qB 时的默认分类名                        | `MTeam-Auto`                                   |
    | `QBIT_DEFAULT_TAGS_FOR_MT`     | (可选) M-Team 助手添加种子到 qB 时的默认标签 (多个用逗号分隔)         | `PT,Telegram下载`                              |
    | `USE_IPV6_DOWNLOAD`            | (可选) M-Team 助手是否优先使用 IPv6 下载种子文件 (`True` 或 `False`)  | `False`                                        |

    **如何设置环境变量?**

    * **Linux / macOS**:
        * 临时设置 (当前终端会话有效): `export VAR_NAME="value"`
        * 永久设置 (推荐): 编辑 `~/.bashrc` (Bash) 或 `~/.zshrc` (Zsh) 文件，在末尾添加 `export VAR_NAME="value"`，然后执行 `source ~/.bashrc` 或 `source ~/.zshrc` 使其生效。
    * **Windows**:
        * PowerShell (当前会话): `$env:VAR_NAME="value"`
        * 永久设置: 通过 “系统属性” -> “高级” -> “环境变量” 进行图形化设置。
    * **Docker**: 在 `docker run` 命令中使用 `-e VAR_NAME="value"` 参数，或在 `docker-compose.yml` 文件中定义 `environment`。
    * **青龙面板**: 在面板的 “配置文件” 或 “环境变量” 设置页面添加。

    **请务必根据您实际使用的脚本，查阅其开头的说明或代码内部逻辑，确认所需的全部环境变量并正确配置。**

## 🚀 使用指南

配置完成后，您可以根据需要运行相应的脚本。

### 1. M-Team Telegram 助手 (`telegram/mt_helper.py`)

这是您与 PT 世界交互的智能门户。

* **启动脚本**:
    在项目根目录下，执行：
    ```bash
    python telegram/mt_helper.py
    ```
    脚本会持续运行，连接到 Telegram API。

* **与机器人互动**:
    1.  在 Telegram 中找到您创建的 Bot。
    2.  发送 `/start` 命令给机器人，它会回复欢迎消息并显示主操作菜单键盘。
    3.  **通过键盘按钮操作**:
        * **➕ 添加任务**: 机器人会提示您输入 M-Team 种子的 ID。输入后，您可以选择 qBittorrent 中的分类（或使用默认/无分类）来添加下载。
        * **🔄 修改分类**: 机器人会提示您输入 qBittorrent 中任务的 M-Team ID (通常是任务名中 `[12345]` 这样的数字部分)。找到任务后，您可以选择一个新的分类。
        * **🔍 搜索种子**: 机器人会提示您输入搜索关键词。搜索结果将以分页形式展示，包含详细信息。您可以点击按钮翻页，或直接选择某个种子进行下载（后续流程同添加任务）。
        * **🗑️ 删除任务**: 类似修改分类，输入 M-Team ID 定位任务，然后选择是仅删除任务记录还是同时删除关联的文件。
        * **↩️ 返回菜单**: 在任何多步骤操作中，点击此按钮可以取消当前操作并返回到主菜单。
    4.  **直接使用命令**:
        * `/start`: 显示欢迎语和主菜单。
        * `/cancel`: 强制取消当前正在进行的多步骤操作，并返回主菜单。
        * `/help`: 显示详细的帮助信息和可用命令列表。
        * `/listcats`: 列出您 qBittorrent 中所有已配置的分类名称。
        * `/qbtasks [页码]`: 查看 qBittorrent 中的任务列表。例如，`/qbtasks` 查看第一页，`/qbtasks 2` 查看第二页。

### 2. 其他自动化脚本

对于 `mteam/`, `qbittorrent/` 目录下的其他自动化脚本 (如 `brush.py`, `rss_monitor.py`, `tasks_cleanup.py` 等)：

* **启动**: 通常直接使用 `python <脚本路径>` 命令运行，例如 `python mteam/brush.py`。
* **配置**: 确保已设置它们所需的全部环境变量。
* **运行方式**:
    * 部分脚本 (如 `rss_monitor.py`) 设计为持续运行的监控服务。
    * 其他脚本 (如 `brush.py`, `tasks_cleanup.py`) 可能适合通过定时任务（如 Linux 的 `cron`，Windows 的“任务计划程序”，或青龙面板的定时任务功能）周期性执行。例如，每隔几小时运行一次刷流脚本，或每天凌晨运行一次任务清理脚本。

**请仔细阅读每个脚本开头的说明（如果有的话）以了解其具体功能、配置需求和推荐的运行方式。**

## 部分截图

![](images/01.png)

![](images/02.png)

![](images/03.png)

## 🤝 贡献代码与反馈

我们热烈欢迎任何形式的贡献，无论是：

* **发现并报告 Bug**: 请通过 [GitHub Issues](https://github.com/astralwaveio/MTeam-Genie/issues) 提交详细的 Bug 描述。
* **提出功能建议**: 有好的想法能让项目更棒？请同样通过 Issues 告诉我们！
* **贡献代码**:
    1.  Fork 本项目到您的 GitHub 账户。
    2.  基于 `main` (或当前开发主分支) 创建一个新的特性分支 (`git checkout -b feature/your-new-feature`)。
    3.  进行您的代码修改和完善。
    4.  提交您的更改 (`git commit -am 'feat: Add some amazing feature'`)。
    5.  将您的分支推送到您的 Fork 仓库 (`git push origin feature/your-new-feature`)。
    6.  在本项目的 GitHub 页面创建一个 Pull Request，详细说明您的更改内容和原因。

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。您可以自由使用、修改和分发，但请遵守许可证条款。

---

🎉 感谢您对 **M-Team 精灵** 的关注与支持！希望这些工具能为您的 PT 生活带来便利与乐趣。
如果您觉得这个项目对您有帮助，请不吝给我们点亮一颗 ⭐ **Star** ⭐，这是对我们最大的鼓励！
遇到任何问题或有任何建议，都欢迎通过项目的 [GitHub Issues](https://github.com/astralwaveio/MTeam-Genie/issues) 与我们交流。

Happy torrenting! 🥳
