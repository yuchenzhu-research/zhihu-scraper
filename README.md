<div align="center">

# Zhihu-Scraper
### 知乎本地归档抓取工具

<p><strong>一个本地优先的知乎抓取与归档项目：协议优先，必要时回退浏览器，输出直接落到 Markdown、图片目录和 SQLite。</strong></p>

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

</div>

> [!WARNING]
> 本项目仅用于学习、研究、个人归档与技术交流。请遵守知乎服务条款、robots 约束和当地法律法规。

## 1. 项目定位

本项目是一个**本地优先**的知乎归档工具，不是在线爬虫平台，也不是 SaaS 产品。

它的主要目标是：

- 输入知乎链接
- 抓取正文和必要元数据
- 转换为 Markdown
- 下载图片并保存在本地目录
- 将索引写入 SQLite

适合场景：

- 个人知识归档
- 研究材料整理
- 命令行工作流
- 本地文件 + 本地数据库双存储

非目标：

- 在线托管采集平台
- 全站级数据采集
- GUI 成品应用
- JSON / CSV / MySQL 作为默认交付

## 2. 当前支持范围

当前支持：

- 单条回答
- 专栏文章
- 问题页最近 N 条回答
- 作者主页下最近回答与专栏
- 收藏夹增量监控
- Markdown + 图片 + SQLite 本地输出
- 默认交互工作台：**Textual TUI**
- 兼容回退：`interactive --legacy`

当前不作为正式交付的能力：

- 话题页抓取
- GUI
- 云端托管
- MySQL / 远程存储默认支持

## 3. 快速开始

### 3.1 安装

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./install.sh
```

如需重建环境：

```bash
./install.sh --recreate
```

当前维护基线：

- Python 3.14+

### 3.2 准备 Cookie

默认运行目录已统一到 `.local/`：

```bash
mkdir -p .local
cp cookies.example.json .local/cookies.json
```

填写你自己的：

- `z_c0`
- `d_c0`

兼容历史路径：

- `cookies.json`
- `cookie_pool/`

### 3.3 最小运行

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

打开首页或工作台：

```bash
zhihu
zhihu interactive
zhihu interactive --legacy
```

入口关系：

- `zhihu`
  打开首页 launcher，适合首次使用、命令导航和环境检查。
- `zhihu interactive`
  直接进入默认的 Textual TUI 归档工作台。
- `zhihu interactive --legacy`
  进入旧 Rich / questionary 回退路径，仅用于兼容与排障。

## 4. 命令总览

当前核心命令如下：

- `zhihu onboard`
- `zhihu fetch`
- `zhihu creator`
- `zhihu batch`
- `zhihu monitor`
- `zhihu query`
- `zhihu interactive`
- `zhihu config --show`
- `zhihu check`
- `zhihu manual`

主入口关系：

- `zhihu`
  无参数时进入首页 launcher，不直接进入 Textual 工作台。
- `zhihu interactive`
  直达当前推荐的 Textual TUI。
- `zhihu interactive --legacy`
  直达兼容回退路径。

常用例子：

```bash
zhihu onboard
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
zhihu creator "https://www.zhihu.com/people/iterator"
zhihu batch urls.txt
zhihu monitor 78170682
zhihu query "Transformer"
zhihu interactive
zhihu interactive --legacy
zhihu config --show
zhihu check
zhihu manual
```

## 5. 输出结构

默认输出根目录：

```text
data/
```

典型结构：

```text
data/
├─ entries/
│  └─ 2026-04-03_title--answer-123456/
│     ├─ index.md
│     └─ images/
├─ creators/
│  └─ <url_token>/
│     ├─ creator.json
│     └─ README.md
└─ zhihu.db
```

## 6. 基本目录说明

```text
cli/    命令入口、交互、保存编排
core/   抓取、配置、转换、数据库、运行时能力
docs/   平台、配置、工作流等专题文档
tests/  unittest 回归测试
data/   默认输出目录
.local/ Cookie、日志等运行时文件
```

## 7. 平台与安装边界

当前平台说明以 [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md) 为准。

简要结论：

- macOS：主维护平台
- Linux：持续加固中
- Windows：有 runbook，但还不是一等安装体验

Windows 运行细节见：

- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)

## 8. 更多文档

如果你只是想快速用起来，看本 README 即可。  
如果你要维护、协作或继续重构，请继续看：

- [MANUAL.md](MANUAL.md)
- [AGENTS.md](AGENTS.md)
- [docs/dependency-map.md](docs/dependency-map.md)
- [docs/config.md](docs/config.md)
- [docs/workflows.md](docs/workflows.md)

## 9. 当前交互入口说明

`zhihu` 无参数时会打开首页 launcher。  
`zhihu interactive` 才是直达 **Textual TUI** 的命令。

旧的 Rich / questionary 路径仍然保留为：

```bash
zhihu interactive --legacy
```

它的定位是兼容与排障，不再是推荐主路径。  
抓取链路仍然以“协议优先，必要时浏览器回退”为基本策略。
