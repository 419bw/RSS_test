# 创建 RSS 订阅源 — 通用流程 SKILL

> 目标：把任意一个**没有官方 RSS**的网页（或网页列表），改造成一个标准的 RSS 2.0 订阅源，并部署到 GitHub Pages，让 Inoreader / Feedly 等阅读器能订阅。
>
> 全流程可在 1-2 小时内完成。

---

## 适用场景

- 新闻/博客列表页（公司新闻、官方公告、媒体专栏等）
- 论坛板块列表
- 商品列表（但要注意版权与抓取频率）
- API 文档 changelog
- 任何"内容定期更新、但没提供 RSS"的页面

## 不适用

- 需要登录的页面（除非你有稳定的 cookie）
- JS 渲染占比极高的 SPA（需要 playwright）
- 抓取频率需要 < 1 小时的场景（考虑用 RSSHub、Huginn 等更专业的方案）

---

## 前置准备

| 工具 | 用途 | 备注 |
|---|---|---|
| Python 3.10+ | 写抓取脚本 | 必装 |
| pip + venv | 依赖管理 | 必装 |
| git + GitHub 账号 | 部署 RSS + Pages | 必装 |
| 一个空仓库 | 托管 RSS | 推荐 public（Pages 要求） |
| curl 或浏览器 F12 | 调研网页结构 | 必装 |

Python 依赖：

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
feedgen>=0.9.0
```

---

## 流程概览

```
1. 调研目标网站 ──→  2. 搭建项目 ──→  3. 写抓取脚本
        ↑                                    │
        └────── 解析失败时回到这步 ───────────┘
                                            ↓
                          4. 验证 feed.xml ──→ 5. 部署到 GitHub Pages
                                                        ↓
                                          6. 在 Inoreader 订阅（可选 7. 加定时任务）
```

---

## 步骤 1：调研目标网站（关键步骤）

**目的**：搞清楚页面结构、提取规则、反爬机制。**这一步的细致程度直接决定后面写脚本的难度。**

### 1.1 基本信息

```bash
# 抓下来看
curl -L -A "Mozilla/5.0 ..." -o raw.html "https://目标网址"
```

观察：
- 总大小（几百 KB → 静态；几 MB → SPA）
- 是否含 `<h1>`、`<h2>`、`<a>` 等结构化标签
- 是否含日期（`2024-01-15`、`2024/01/15`）
- 摘要/正文如何呈现

### 1.2 关键问题清单

- [ ] **列表元素**：每条内容用什么标签包裹？`<article>`？`<li>`？`<a>`？
- [ ] **标题**：在哪个标签里？`<h1>`、`<h2>`、`<h3>`？
- [ ] **链接**：是绝对 URL 还是相对 URL？
- [ ] **日期**：在哪个标签里？文本格式是什么？
- [ ] **数量**：每页多少条？要不要分页？
- [ ] **反爬**：直接 curl 能拿到吗？需不需要 headers / cookie / 代理？
- [ ] **渲染**：是服务端渲染还是 SPA？JS 不跑能拿到内容吗？

### 1.3 反爬快速排查

依次尝试以下 curl 命令，看哪个能拿到完整内容：

```bash
# 1. 最简
curl -s URL | head -100

# 2. 加 User-Agent
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" URL | head -100

# 3. 加 Referer
curl -s -A "..." -H "Referer: https://目标域名" URL | head -100

# 4. 加 Cookie（先浏览器抓一个）
curl -s -A "..." -H "Cookie: xxx=yyy" URL | head -100
```

如果 1-3 都拿不到完整内容：
- 内容是 JS 动态渲染 → 用 playwright（更重）
- 有 Cloudflare 等高级防护 → 考虑用 RSSHub 适配器

---

## 步骤 2：搭建项目

```bash
mkdir my-rss && cd my-rss
git init -b main
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt   # 用上面的依赖清单
```

**最小文件结构**：

```
my-rss/
├── fetcher.py        # 抓取 + 解析 + 生成 RSS
├── feed.xml          # 生成的 RSS（提交）
├── requirements.txt
├── .gitignore        # 忽略 venv/、__pycache__/
└── README.md         # 简短说明（可选）
```

---

## 步骤 3：写抓取脚本

### 3.1 脚本骨架（可复用模板）

```python
"""fetcher.py — 抓取 <目标名> 内容并生成 RSS"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from lxml import etree
from feedgen.feed import FeedGenerator

# ===== 配置 =====
TARGET_URL = "https://..."
RSS_OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CHANNEL = {
    "title": "<目标名>RSS",
    "link": TARGET_URL,
    "description": "...",
    "language": "zh-cn",
}


def fetch() -> str:
    """获取网页源码"""
    r = requests.get(TARGET_URL, headers=HEADERS, timeout=30)
    r.encoding = "utf-8"
    r.raise_for_status()
    return r.text


def parse(html: str) -> list:
    """解析出 [{title, link, pubdate_dt}, ...]"""
    soup = BeautifulSoup(html, "lxml")
    items = []
    # TODO: 根据实际 DOM 结构写
    # ...
    return items


def make_rss(items: list) -> None:
    """生成 RSS 2.0 XML（含按时间倒序重排）"""
    fg = FeedGenerator()
    fg.id(CHANNEL["link"])
    fg.title(CHANNEL["title"])
    fg.link(href=CHANNEL["link"], rel="alternate")
    fg.description(CHANNEL["description"])
    fg.language(CHANNEL["language"])

    for it in items:
        fe = fg.add_entry()
        fe.id(it["link"])
        fe.title(it["title"])
        fe.link(href=it["link"], rel="alternate")
        fe.pubDate(it["pubdate_str"])

    # feedgen 会按 id 重排，用 lxml 按 pubDate 倒序覆盖
    root = etree.fromstring(fg.rss_str(pretty=True))
    channel = root.find("channel")
    xml_items = channel.findall("item")
    def _dt(it):
        pd = it.find("pubDate")
        if pd is not None and pd.text:
            try: return parsedate_to_datetime(pd.text)
            except: return None
        return None
    xml_items.sort(key=lambda it: _dt(it) or datetime.min, reverse=True)
    for it in xml_items: channel.remove(it)
    for it in xml_items: channel.append(it)

    with open(RSS_OUTPUT_FILE, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True,
                               xml_declaration=True, encoding="UTF-8"))


if __name__ == "__main__":
    html = fetch()
    items = parse(html)
    items.sort(key=lambda x: x["pubdate_dt"], reverse=True)
    for it in items:
        it["pubdate_str"] = it["pubdate_dt"].strftime("%a, %d %b %Y %H:%M:%S +0800")
        del it["pubdate_dt"]
    make_rss(items[:MAX_ITEMS])
    print(f"生成 {len(items[:MAX_ITEMS])} 条 RSS")
```

### 3.2 编写 `parse()` 的常用模式

**模式 A：列表型（每条是 `<article>` 或 `<li>`）**

```python
for article in soup.find_all("article"):
    title = article.find(["h1","h2","h3"]).get_text(strip=True)
    link = article.find("a", href=True)["href"]
    date_str = article.find("time").get("datetime") or article.find("time").get_text()
    # ...
```

**模式 B：链接型（每条是一个 `<a>`，标题/日期都在 a 内部）**

```python
for a in soup.find_all("a", href=True):
    if not re.search(r"/article/\d+", a["href"]): continue
    h3 = a.find("h3"); p = a.find("p")
    if not (h3 and p): continue
    title, date_str = h3.get_text(strip=True), p.get_text(strip=True)
    # ...
```

**模式 C：表格型（`<tr>` / `<td>`）**

```python
for tr in soup.find_all("tr")[1:]:  # 跳过表头
    tds = tr.find_all("td")
    if len(tds) < 2: continue
    title = tds[0].get_text(strip=True)
    date_str = tds[1].get_text(strip=True)
    # ...
```

**日期解析（多格式兼容）**：

```python
def parse_date(s):
    for fmt in ["%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"]:
        try: return datetime.strptime(s.strip(), fmt)
        except: continue
    return None
```

### 3.3 解析失败 → 回到步骤 1

**诊断技巧**：

```python
# 临时打印前 5 个匹配，看提取规则对不对
soup = BeautifulSoup(html, "lxml")
for i, a in enumerate(soup.find_all("a", href=True)[:20]):
    print(i, a.get("href"), "|", a.get_text(strip=True)[:50])
```

最常见的失败原因：
- a 标签 `href` 是相对路径 → 没拼成绝对 URL
- 日期在 a 标签**内部**（子标签），不是兄弟节点
- SPA 网站，HTML 里只有 JSON data，没渲染好的 DOM
- 反爬返回的不是真实页面（"请开启 JS" 的占位页）

---

## 步骤 4：验证 feed.xml

```bash
python fetcher.py
# 应输出：生成 15 条 RSS
```

然后手动检查：

```bash
# 1. 文件存在且是合法 XML
python -c "import xml.etree.ElementTree as ET; ET.parse('feed.xml'); print('XML 合法')"

# 2. 顺序对（最新在最前）
head -20 feed.xml

# 3. 字段都有
python -c "
import xml.etree.ElementTree as ET
root = ET.parse('feed.xml').getroot()
for item in root.findall('.//item')[:3]:
    print(item.find('title').text, '|', item.find('link').text, '|', item.find('pubDate').text)
"
```

**在线校验工具**（推荐）：
- https://validator.w3.org/feed/ — W3C 官方 RSS 校验
- https://www.rssboard.org/rss-validator/ — RSS Advisory Board 校验

---

## 步骤 5：部署到 GitHub Pages

### 5.1 创建 GitHub 仓库

- 仓库名随意（例：`my-rss`、`<目标>-rss`）
- **Public**（GitHub Pages 免费版要求 public）
- 不要勾选 "Add README"（我们本地已经有）

### 5.2 推送到 GitHub

```bash
git remote add origin git@github.com:<user>/<repo>.git
git add .gitignore fetcher.py requirements.txt feed.xml README.md
git commit -m "Initial RSS feed"
git push -u origin main
```

### 5.3 启用 GitHub Pages

1. 仓库 → **Settings** → **Pages**
2. Source: `Deploy from a branch`
3. Branch: `main` / `(root)`
4. 保存

### 5.4 验证

等 1-2 分钟后访问：

```
https://<user>.github.io/<repo>/feed.xml
```

应该能看到 RSS XML 原文。

---

## 步骤 6：在 Inoreader 订阅

1. Inoreader → **+ Subscribe** → **Feed URL**
2. 填写：`https://<user>.github.io/<repo>/feed.xml`
3. 完成

> 其他阅读器（Feedly、Reedly、NetNewsWire）操作类似。

---

## 步骤 7（可选）：自动定时抓取

三种方案对比：

| 场景 | 方案 | 优点 | 缺点 |
|---|---|---|---|
| 个人电脑、Windows | 任务计划程序 | 本地无外部依赖 | 关机就不跑 |
| 服务器、Linux 24h | Crontab | 灵活、可控 | 自己维护服务器 |
| 完全不想自己跑 | **GitHub Actions（推荐）** | 推送一次就完事，GitHub 免费跑 | cron 最小粒度 5 分钟，时间不保证精确 |

---

### 7.1 GitHub Actions 方案（最省心，推送一次就完事）

**核心认知：只需要 push 一次工作流文件，之后 GitHub 自己定时跑，你什么都不用做。**

#### 步骤 A：准备 `requirements.txt` + `fetcher.py` + `feed.xml`

确保这三个文件在仓库根目录能跑（步骤 3、4 已就绪）。

#### 步骤 B：写工作流文件

`.github/workflows/feed.yml`：

```yaml
name: Update RSS

on:
  schedule:
    # 北京时间 0/4/8/12/16/20 点各跑一次（GitHub 用 UTC）
    - cron: "0 16,20,0,4,8,12 * * *"
  workflow_dispatch:  # 支持网页点一下手动跑（调试用）

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python fetcher.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Update RSS feed"
```

#### 步骤 C：一次性推送到 GitHub

```bash
git init -b main
git add .
git commit -m "Initial RSS feed"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

**这一步是唯一需要推送的代码。** 之后工作流会自动跑、自动 commit 新的 `feed.xml`，**你不需要再 push 任何东西**。

#### 步骤 D：验证

| 时间点 | 预期行为 |
|---|---|
| 推送后 1-2 分钟 | 仓库 → **Actions** 标签下能看到 `Update RSS` workflow |
| 推送后 30-60 分钟 | GitHub 调度器触发第一次自动跑（首次可能有延迟） |
| 第一次跑成功后 | 仓库多一条 `Update RSS feed` 的 commit，feed.xml 内容更新 |
| 之后每 4 小时 | 持续自动跑、自动 commit |

> ⚠️ **首次自动跑可能要等 30-60 分钟**。想立刻验证：在 Actions 页面 → 选 `Update RSS` → **Run workflow**（这就是 `workflow_dispatch` 的作用）。

#### 步骤 E：cron 时间换算（重要）

GitHub Actions 的 cron 是 **UTC 时区**。常用对照：

| 北京时间 | UTC cron | 表达式 |
|---|---|---|
| 每 1 小时 | `0 * * * *` | `0 * * * *` |
| 每 4 小时 | 0/4/8/12/16/20 点 | `0 16,20,0,4,8 * * *`（注意是 16,20,0,4,8） |
| 每 6 小时 | 0/6/12/18 点 | `0 16,4,10,18 * * *` |
| 每天 8 点 | 8:00 | `0 0 * * *` |
| 每天 20 点 | 20:00 | `0 12 * * *` |
| 每天 9 点和 21 点 | 9:00 / 21:00 | `0 1,13 * * *` |

> 📌 **关于 cron 精度**：GitHub 不保证按点执行，高峰期可能延迟 5-30 分钟。新闻类 RSS 4 小时一次完全够用。

#### 步骤 F：调试 / 查看日志

- **手动跑一次**：仓库 → Actions → `Update RSS` → **Run workflow** → 点绿色按钮
- **看历史**：Actions → 左侧列表点某次运行 → 展开步骤看 `python fetcher.py` 的输出
- **看 RSS 是否更新**：访问 `https://<user>.github.io/<repo>/feed.xml`，看 `lastBuildDate` 是不是最近

#### 步骤 G：常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 推送后 1 小时还没自动跑 | 正常，等 30-60 分钟；或手动 Run workflow 验证 |
| 工作流跑失败 | 看 Actions 日志，最常见是 `fetcher.py` 报错或依赖没装 |
| feed.xml 没更新但 workflow 跑成功了 | 网站内容真没变，git-auto-commit 不会创建空 commit |
| 定时不准确 | GitHub 调度限制，无法保证精确到分钟；用更频繁的 cron 弥补 |
| 想暂停自动跑 | 删掉 `.github/workflows/feed.yml` 即可（保留文件就只手动跑） |
| 想换频率 | 改 cron 表达式，commit 一次后 GitHub 自动应用新调度 |
| 私有仓库 | 每月 2000 分钟免费额度，本项目一次跑约 1 分钟，够用 |

---

### 7.2 Windows 任务计划程序方案（仅本机跑）

适合：只想本机抓，不部署到 GitHub。

1. 打开「任务计划程序」→ 创建基本任务
2. 触发器：每天 / 每周 / 登录时
3. 操作：启动程序
   - 程序：`C:\...\venv\Scripts\python.exe`
   - 参数：`fetcher.py`
   - 起始位置：项目目录
4. 勾选「使用最高权限」

> 注意：电脑关机就不跑。

### 7.3 Linux Crontab 方案

```bash
crontab -e
# 添加一行（每 4 小时）
0 */4 * * * cd /path/to/my-rss && /path/to/venv/bin/python fetcher.py
```

---

## 关键决策点

### RSS 字段填什么？

| 字段 | 必填 | 来源 | 说明 |
|---|---|---|---|
| `title` | 是 | 列表中的标题 | 必填，否则阅读器无法显示 |
| `link` | 是 | 详情页 URL | 必填，否则无法跳转 |
| `pubDate` | 是 | 网页日期/当前时间 | RFC 822 格式，Inoreader 按此排序 |
| `description` | 否 | 摘要/正文 | 不填也能用，填了显示更丰富 |
| `guid` | 否 | 通常 = link | feedgen 自动生成 |

### 抓多少条？

- 15-30 条比较合适（Inoreader 默认就显示这些）
- 太多会增加请求量和推送体积
- 太少会丢失旧内容

### 抓取频率？

- 普通新闻：每 4 小时足够
- 实时性要求高：每 1 小时
- **不要 < 1 小时**，对目标网站不友好

---

## 常见陷阱

| 陷阱 | 解决方案 |
|---|---|
| 中英文乱码 | 强制 `response.encoding = "utf-8"` |
| 反爬返回 403 | 加完整 headers（User-Agent + Referer） |
| 相对路径链接 | 手动拼成绝对 URL |
| 同一个 URL 出现多次 | 用 `set()` 去重 |
| feedgen 按 id 重排 | 生成后用 lxml 按 pubDate 重排 |
| 日期字符串不能直接比较 | 统一转 datetime 对象再排序 |
| 页面结构改了 | 重新做步骤 1 |
| 抓不到任何内容 | curl 一下看是不是反爬；用浏览器 F12 看实际 DOM |

---

## 复用模板速查

**最小可运行项目**（任何网站适配，改 4 处即可）：

```python
# fetcher.py
TARGET_URL = "<URL>"              # ← 改 1
CHANNEL = {"title": "...", ...}   # ← 改 2
HEADERS = {"User-Agent": "..."}   # ← 改 3

def parse(html):                  # ← 改 4（关键）
    # 根据目标 DOM 结构写
    ...
```

其余 `fetch()` / `make_rss()` / `__main__` 全部通用，不需要改。

---

## 复用到其他网站的步骤（30 分钟版）

1. 复制本项目目录，改名（如 `huawei-rss/`）
2. 改 `fetcher.py` 的 4 处（URL、CHANNEL、HEADERS、parse）
3. 跑 `python fetcher.py`，看 feed.xml 是否生成
4. 解析不对 → 浏览器 F12 看 DOM → 改 `parse()` → 重跑
5. 改 `git remote add origin <新仓库>`
6. push + GitHub Pages + Inoreader 订阅

---

## 相关工具

| 需求 | 工具 |
|---|---|
| 想跳过写代码 | [RSSHub](https://docs.rsshub.app/) — 已有上千个网站的适配器 |
| JS 渲染页面 | [feedgenerator](https://github.com/h5p/feedgenerator) + playwright |
| 多个 RSS 合并 | [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) |
| 想要现成 GitHub 模板 | [hugo-PaperMod](https://github.com/adityatelange/hugo-PaperMod) 风格的 Jekyll/Hexo 静态博客自带 RSS |
