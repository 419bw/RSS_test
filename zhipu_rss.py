# -*- coding: utf-8 -*-
"""
智谱AI新闻RSS抓取脚本
功能：抓取智谱AI官网新闻列表，生成RSS 2.0 XML文件，并自动推送到GitHub Pages

依赖库：requests, beautifulsoup4, feedgen
安装：pip install -r requirements.txt

使用方法：
    python zhipu_rss.py
"""

import os
# 禁用系统代理，避免代理连接失败导致请求失败
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import subprocess
import sys

# ========== 配置区域 ==========
TARGET_URL = "https://www.zhipuai.cn/zh/news"
RSS_OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 15  # 最多保留的新闻条目数

# Git配置
# GIT_REMOTE 可以是 remote 名称（如 "origin"）或完整 URL
# 推荐先用 `git remote add origin git@github.com:419bw/RSS_test.git`，这里保持 "origin"
GIT_REMOTE = "origin"
GIT_BRANCH = "main"  # GitHub Pages 需 main 分支
GIT_REPO_URL = "git@github.com:419bw/RSS_test.git"  # 首次配置时使用

# 请求头伪装
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# RSS频道元数据
CHANNEL_META = {
    "title": "智谱AI新闻",
    "link": "https://www.zhipuai.cn/zh/news",
    "description": "智谱AI官方新闻与资讯",
    "language": "zh-cn",
}


def fetch_webpage(url: str) -> str:
    """
    获取网页源码

    Args:
        url: 目标网址

    Returns:
        网页HTML内容（UTF-8编码）

    Raises:
        requests.RequestException: 请求失败时抛出异常
    """
    print(f"[INFO] 正在请求: {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.encoding = "utf-8"  # 确保中文不乱码
    response.raise_for_status()
    print(f"[INFO] 请求成功，状态码: {response.status_code}")
    return response.text


def parse_news(html: str) -> list:
    """
    解析HTML，提取新闻列表

    Args:
        html: 网页HTML内容

    Returns:
        新闻列表，每项包含 title, link, pubdate
    """
    soup = BeautifulSoup(html, "lxml")
    import re

    # 智谱页面是 Next.js SPA，新闻卡片的真实 DOM 结构：
    #   <a href="/zh/news/{id}" class="group flex h-full cursor-pointer flex-col gap-y-6">
    #     <div><img alt="标题"/></div>
    #     <div>
    #       <h3>标题</h3>
    #       <p>2026/03/31</p>
    #     </div>
    #     <span>摘要...</span>
    #   </a>
    # 识别要点：a 标签同时含有 h3 和 p，且 href 是 /zh/news/数字

    news_items = []
    seen_links = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        m = re.search(r"^/zh/news/(\d+)$", href)  # 精确匹配列表卡片
        if not m:
            continue

        # 必须同时含 h3（标题）和 p（日期/描述）
        h3 = a_tag.find("h3")
        p = a_tag.find("p")
        if h3 is None or p is None:
            continue

        title = h3.get_text(strip=True)
        date_text = p.get_text(strip=True)

        if not title or len(title) < 5:
            continue

        # 构造绝对 URL
        full_link = f"https://www.zhipuai.cn{href}"

        # 解析日期
        pubdate_dt = parse_date_to_datetime(date_text) or datetime.now()
        pubdate = pubdate_dt.strftime("%a, %d %b %Y %H:%M:%S +0800")

        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        news_items.append({
            "title": title,
            "link": full_link,
            "pubdate": pubdate,
            "_dt": pubdate_dt,
        })

    # 按时间倒序排序（最新优先）
    news_items.sort(key=lambda x: x["_dt"], reverse=True)
    # 移除内部字段
    for item in news_items:
        item.pop("_dt", None)

    print(f"[INFO] 解析到 {len(news_items)} 条新闻")
    return news_items[:MAX_ITEMS]


def parse_date_to_datetime(date_str: str):
    """
    将日期字符串转换为 datetime 对象

    Args:
        date_str: 日期字符串（如 2026/03/31 或 2026-03-31）

    Returns:
        datetime 对象，解析失败返回 None
    """
    formats = [
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y年%m月%d日",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_date_to_rfc(date_str: str) -> str:
    """
    将日期字符串转换为RFC 822格式
    """
    dt = parse_date_to_datetime(date_str)
    if dt is None:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0800")


def generate_rss(news_items: list, output_file: str):
    """
    生成RSS 2.0 XML文件

    Args:
        news_items: 新闻列表
        output_file: 输出文件名
    """
    try:
        from feedgen.feed import FeedGenerator
    except ImportError:
        print("[ERROR] 请先安装 feedgen: pip install feedgen")
        sys.exit(1)

    fg = FeedGenerator()
    fg.id(CHANNEL_META["link"])
    fg.title(CHANNEL_META["title"])
    fg.link(href=CHANNEL_META["link"], rel="alternate")
    fg.description(CHANNEL_META["description"])
    fg.language(CHANNEL_META["language"])

    for item in news_items:
        fe = fg.add_entry()
        fe.id(item["link"])
        fe.title(item["title"])
        fe.link(href=item["link"], rel="alternate")
        fe.pubDate(item["pubdate"])

    # feedgen 内部会按 id 重排 item，需要用 lxml 重新按 pubDate 倒序排
    from lxml import etree
    from email.utils import parsedate_to_datetime
    xml = fg.rss_str(pretty=True)
    root = etree.fromstring(xml)
    channel = root.find("channel")
    items_xml = channel.findall("item")

    def _to_dt(it):
        pd = it.find("pubDate")
        if pd is not None and pd.text:
            try:
                return parsedate_to_datetime(pd.text)
            except Exception:
                return None
        return None

    items_xml.sort(key=lambda it: _to_dt(it) or datetime.min, reverse=True)
    for it in items_xml:
        channel.remove(it)
    for it in items_xml:
        channel.append(it)

    with open(output_file, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

    print(f"[INFO] RSS文件已生成: {output_file}")


def ensure_git_remote():
    """
    确保 remote 已配置。如果 GIT_REMOTE 是 "origin" 但未设置，则用 GIT_REPO_URL 添加。
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", GIT_REMOTE],
            capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            # remote 不存在，添加
            print(f"[INFO] 添加远程仓库: {GIT_REMOTE} -> {GIT_REPO_URL}")
            subprocess.run(
                ["git", "remote", "add", GIT_REMOTE, GIT_REPO_URL],
                check=True
            )
    except subprocess.CalledProcessError as e:
        print(f"[WARN] 配置 remote 失败: {e}")


def git_push():
    """
    将feed.xml提交到GitHub
    """
    try:
        # 确保 remote 已配置
        ensure_git_remote()

        # 先拉取，避免远端有更新时冲突
        pull = subprocess.run(
            ["git", "pull", "--rebase", GIT_REMOTE, GIT_BRANCH],
            capture_output=True, text=True, encoding="utf-8"
        )
        if pull.returncode != 0:
            # 首次推送（远端空仓库）时可能失败，不影响继续
            print(f"[INFO] 拉取跳过（远端可能为空）: {pull.stderr.strip()[:200]}")

        # 检查git状态
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8"
        )

        if not status.stdout.strip():
            print("[INFO] 没有需要提交的更改")
            return

        # 添加 feed.xml
        subprocess.run(["git", "add", "feed.xml"], check=True)

        # 提交
        commit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Update RSS feed: {commit_time}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)

        # 推送
        result = subprocess.run(
            ["git", "push", GIT_REMOTE, GIT_BRANCH],
            capture_output=True, text=True, encoding="utf-8"
        )

        if result.returncode == 0:
            print(f"[INFO] 成功推送至 {GIT_REMOTE}/{GIT_BRANCH}")
            if result.stdout.strip():
                print(result.stdout.strip())
        else:
            print(f"[WARN] 推送失败 (exit={result.returncode}):")
            print(f"  stdout: {result.stdout.strip()[:300]}")
            print(f"  stderr: {result.stderr.strip()[:300]}")

    except subprocess.CalledProcessError as e:
        print(f"[WARN] Git操作失败: {e}")
    except FileNotFoundError:
        print("[WARN] 未检测到Git仓库，跳过推送步骤")


def main():
    """
    主流程
    """
    print("=" * 50)
    print("智谱AI新闻 RSS 抓取脚本")
    print("=" * 50)

    # 1. 获取网页
    try:
        html = fetch_webpage(TARGET_URL)
    except requests.RequestException as e:
        print(f"[ERROR] 获取网页失败: {e}")
        sys.exit(1)

    # 2. 解析新闻
    news_items = parse_news(html)

    if not news_items:
        print("[WARN] 未解析到新闻，可能页面结构已变更")
        sys.exit(1)

    # 3. 生成RSS
    generate_rss(news_items, RSS_OUTPUT_FILE)

    # 4. Git推送（可选）
    if os.path.exists(".git"):
        print("[INFO] 检测到Git仓库，开始自动部署...")
        git_push()
    else:
        print("[INFO] 非Git仓库目录，跳过自动部署")

    print("[INFO] 任务完成！")


if __name__ == "__main__":
    main()
