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
> **免责声明 / Disclaimer**
>
> 本项目仅用于学习、研究、个人归档与技术交流。请遵守知乎服务条款、robots 约束和当地法律法规。不要将其用于未授权抓取、批量滥用、数据倒卖、撞库、账号滥用或任何非法用途。

## 1. 这是什么

`Zhihu-Scraper` 不是一个在线爬虫平台，也不是一个 SaaS 产品。  
它是一个 **本地优先** 的归档工具，目标很明确：

- 输入知乎链接
- 抓取正文和相关元信息
- 转成 Markdown
- 下载图片
- 把归档结果和检索数据保存到本地

它适合：

- 个人知识归档
- 研究材料收集
- 命令行工作流
- 本地文件 + 本地数据库双存储
- 持续迭代的工程项目

它不适合：

- 大规模在线采集平台
- 托管式抓取服务
- 一键 GUI 成品
- 即刻获得 JSON / CSV / MySQL 导出
- 话题页 / 全站搜索 / 更大范围的数据覆盖

## 2. 当前项目状态

当前仓库已经不再是早期脚本堆叠状态，而是经历了完整的一轮治理和重构。

当前状态可以概括成：

- CLI 主路径可用
- Textual TUI 已成为默认交互入口
- README / manual / `--help` / 测试矩阵已经开始同步治理
- `test` 分支上的六阶段治理已合并回 `main`
- 配置层和抓取结果契约已经开始类型化
- 仍然有继续重构空间，尤其是 `core/config.py`、`core/scraper.py`、TUI 状态流和跨平台验证

## 3. 现在支持什么

### 支持的抓取对象

- 单条回答
- 专栏文章
- 问题页下最近 N 条回答
- 作者主页下最近回答
- 作者主页下最近专栏
- 收藏夹增量监控

### 支持的输出

- `index.md`
- `images/`
- `zhihu.db`
- creator 元信息文件

### 支持的入口

- `zhihu`
- `./zhihu`
- `python3 cli/app.py`

### 支持的交互方式

- 传统命令行
- 默认交互工作台：**Textual TUI**
- 兼容回退：`interactive --legacy`

## 4. 现在还不支持什么

- 话题页抓取
- JSON 导出
- CSV 导出
- MySQL 持久化
- GUI 图形界面
- LLM 自动分析
- Windows 一等安装体验

这些仍然属于路线图，不应该被视为当前已交付能力。

## 5. Python 与运行时基线

当前仓库已经统一提升到：

- **Python 3.14+**

原因不是单纯追新，而是要和当前测试、`tomllib`、CI、文档和开发环境对齐。  
现在仓库里的声明、CI 和 README 都统一按 3.14+ 维护。

## 6. 快速开始

### 6.1 克隆仓库

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### 6.2 安装

推荐直接运行：

```bash
./install.sh
```

如果你要彻底重建环境：

```bash
./install.sh --recreate
```

### 6.3 配置 Cookie

默认运行目录已经统一到 `.local/`：

```bash
mkdir -p .local
cp cookies.example.json .local/cookies.json
```

然后填入你自己的：

- `z_c0`
- `d_c0`

也支持：

- `.local/cookie_pool/*.json`

并兼容历史路径：

- `cookies.json`
- `cookie_pool/`

### 6.4 Hello World

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

### 6.5 默认首页入口

```bash
zhihu
```

### 6.6 打开完整手册

```bash
zhihu manual
```

## 7. 命令面总览

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

### 常用例子

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

## 8. 交互工作台（TUI）

`interactive` 现在默认已经是 **Textual TUI**。

当前 TUI 已经有：

- 全屏交互工作台
- 居中布局
- 输入栏
- 问题页数量选择
- 当前草案
- 最近执行结果
- 失败重试

当前 TUI 仍在继续推进：

- 状态面板继续整理
- 结果信息继续收口
- 更多 typed contract 接入
- 继续减少 legacy 路径依赖

旧的 Rich / questionary 流程没有删除，但定位已经变成：

- 回归排查
- 兼容兜底
- 不再是推荐主路径

使用方式：

```bash
zhihu interactive
zhihu interactive --legacy
```

## 9. 输出结构

默认输出根目录：

```text
data/
```

当前主要结构：

```text
data/
├─ entries/
│  └─ 2026-04-03_title--answer-123456/
│     ├─ index.md
│     └─ images/
├─ creators/
│  └─ demo-user/
│     ├─ creator.json
│     ├─ README.md
│     └─ 2026-04-03_title--article-1/
│        └─ index.md
└─ zhihu.db
```

说明：

- 普通抓取输出在 `entries/`
- 作者模式输出在 `creators/<url_token>/`
- SQLite 数据库在根目录 `zhihu.db`
- 输出目录命名已改成更适合 shell 的风格

## 10. 平台支持边界

当前平台边界不是“宣传语”，而是明确治理中的工程状态。

### macOS

- 主维护平台
- 安装、CLI、TUI 优先在这里验证

### Linux

- 核心 CLI 可用
- 仍在继续做路径、浏览器回退、安装体验兼容

### Windows

- 已承认是目标平台
- 但还不是一等安装路径
- 当前以 runbook 和手动路径为主

相关文档：

- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)

## 11. 配置系统

配置文件默认位置：

```text
config.yaml
```

当前配置治理已经做了这些事：

- 配置 schema 独立
- 配置运行时加载拆分
- logging setup 拆分
- relative path 统一走 project path 解析
- 旧配置字段开始做兼容层

你可以用下面命令看当前实际配置：

```bash
zhihu config --show
zhihu config --path
```

## 12. 架构与模块状态

### CLI 层

当前 CLI 入口已经不再全部堆在一个文件里，主要边界有：

- `cli/app.py`
- `cli/launcher_flow.py`
- `cli/manual_content.py`
- `cli/config_view.py`
- `cli/healthcheck.py`
- `cli/save_pipeline.py`
- `cli/save_contracts.py`
- `cli/creator_metadata.py`

### Core 层

当前 core 也已经开始从“大文件混合职责”往模块边界收：

- `core/config.py` 现在是 facade
- `core/config_runtime.py`
- `core/config_schema.py`
- `core/logging_setup.py`
- `core/project_paths.py`
- `core/scraper.py`
- `core/scraper_payloads.py`
- `core/scraper_contracts.py`

### 当前方向

当前真正的重构方向不是“继续加功能”，而是：

- 稳定配置边界
- 稳定 scraper/result contract
- 减少大文件继续膨胀
- 把 TUI / CLI / core 的职责继续拉开

## 13. 今天这轮工程都做了什么

这轮工程不是一两个 patch，而是完整做了多阶段治理。

### 阶段一：治理底座

- 整理 `references/`
- 建立 skill 基础结构
- 明确仓库边界和阶段文档

### 阶段二：系统审计

- 审计命令面
- 审计平台支持
- 审计 README / manual 漂移
- 形成阶段二质量报告

### 阶段三：P0 可用性修复

- 收敛 `check`
- 收敛依赖缺失提示
- 加平台边界文档
- 开始拆 `cli/app.py`

### 阶段四：结构重构

- 抽离保存链路
- 抽离配置展示层
- 抽离 scraper payload 归一化

### 阶段五：验证矩阵

- 加命令面测试
- 加安装契约测试
- 固化验证矩阵
- 补 Windows runbook

### 阶段六：收口与合并准备

- 发布审查文档
- issue 回复模板
- merge playbook

### 阶段六之后的新 tranche

在六阶段完成后，又继续做了：

- 配置 schema / runtime / logging / path 分层
- typed save result contract
- creator metadata 渲染抽离
- 问题页分页统计进入 typed result contract

## 14. 测试与验证

现在仓库不是“看起来能跑”，而是有明确验证矩阵。

当前主要验证包括：

- `py_compile`
- unit tests
- command-surface 守卫
- docs-sync 守卫
- install contract 守卫
- save pipeline 守卫
- scraper payload / contract 守卫
- TUI 基础回归
- CLI `--help` smoke

验证矩阵文档见：

- [docs/STAGE5_VALIDATION_MATRIX.md](docs/STAGE5_VALIDATION_MATRIX.md)

## 15. 仓库里有哪些重要文档

- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)
- [docs/STAGE1_SKILL_FOUNDATION.md](docs/STAGE1_SKILL_FOUNDATION.md)
- [docs/STAGE2_QUALITY_AUDIT.md](docs/STAGE2_QUALITY_AUDIT.md)
- [docs/STAGE5_VALIDATION_MATRIX.md](docs/STAGE5_VALIDATION_MATRIX.md)
- [docs/STAGE6_RELEASE_REVIEW.md](docs/STAGE6_RELEASE_REVIEW.md)
- [docs/STAGE6_ISSUE_REPLY_TEMPLATES.md](docs/STAGE6_ISSUE_REPLY_TEMPLATES.md)
- [docs/STAGE6_MERGE_PLAYBOOK.md](docs/STAGE6_MERGE_PLAYBOOK.md)

## 16. 当前工程重点

当前工程重点不是继续堆功能，而是：

- 继续收 `core/config.py`
- 继续收 `core/scraper.py`
- 继续稳定 typed contract
- 继续减轻 CLI / TUI / core 耦合
- 持续补跨平台验证
- 持续让 README / manual / tests / CI 对齐

## 17. 路线图

已完成：

- [x] 单条回答抓取
- [x] 专栏文章抓取
- [x] 问题页分页抓取
- [x] 作者主页抓取
- [x] 收藏夹增量监控
- [x] Markdown + 图片 + SQLite 输出
- [x] 默认交互工作台（Textual TUI）
- [x] 六阶段治理与主线合并

未完成：

- [ ] 话题页抓取
- [ ] JSON 导出
- [ ] CSV 导出
- [ ] MySQL
- [ ] 更完整的 TUI 状态机
- [ ] 更深入的 Windows 支持
- [ ] 更强的浏览器回退自动验证
- [ ] GUI
- [ ] LLM 分析能力

## 18. FAQ

### 为什么要求 Python 3.14+？

因为当前仓库已经把运行时、测试、CI 和文档统一到了 3.14+，不再继续维护 3.10 这条旧基线。

### 为什么没有 Cookie 也能跑？

游客模式可以跑一部分公开路径，但稳定性和可见范围明显更差。作者页、问题页和监控路径更依赖登录态。

### 为什么 `interactive --legacy` 还保留？

因为它现在的角色是兼容回退和回归排查，而不是默认入口。

### 为什么 README 现在很长？

因为这一版目标不是“写得短”，而是先把项目现状、能力边界、平台状态、工程阶段和入口信息全部摊开，方便后续继续整理或交给其他模型再加工。
