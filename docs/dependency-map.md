# dependency-map.md

本文档记录主项目依赖来源、依赖分类和代码落点。  
目标是减少“README、安装脚本、代码 import、历史 requirements 文件”之间的漂移。

## 1. 唯一事实来源

主项目依赖以仓库根目录的 `pyproject.toml` 为唯一事实来源。

执行规则：

- 根目录不新增新的 `requirements*.txt`
- 安装脚本、CI、README、MANUAL 都以 `pyproject.toml` 为准
- 如果出现依赖冲突，优先检查 `pyproject.toml`，不要先修改 README

## 2. 当前主项目依赖映射

### 2.1 协议抓取与访问层

- `curl_cffi`
  - 主要用于协议请求与 TLS impersonation 路径
  - 代码落点：`core/api_client.py`
- `httpx`
  - 主要用于部分网络请求与下载路径
  - 代码落点：`core/scraper.py`
- `PyExecJS`
  - 用于知乎签名或页面脚本能力接入
  - 代码落点：`core/api_client.py`

### 2.2 内容解析与转换层

- `beautifulsoup4`
  - HTML 解析
  - 代码落点：`core/converter.py`
- `markdownify`
  - HTML -> Markdown 转换
  - 代码落点：`core/converter.py`

### 2.3 CLI / TUI / 用户交互层

- `typer`
  - 命令注册与参数解析
  - 代码落点：`cli/app.py`
- `rich`
  - CLI 富文本输出
  - 代码落点：`cli/app.py`、`cli/save_pipeline.py`
- `textual`
  - 默认交互工作台
  - 代码落点：`cli/interactive.py`、`cli/tui/`
- `questionary`
  - legacy / onboarding / launcher 交互
  - 代码落点：`cli/launcher_flow.py`、`cli/interactive_legacy.py`

### 2.4 配置与日志层

- `pyyaml`
  - `config.yaml` 解析
  - 代码落点：`core/config_runtime.py`
- `structlog`
  - 结构化日志与脱敏处理
  - 代码落点：`core/logging_setup.py`

### 2.5 可选浏览器能力

- `playwright`
  - 浏览器回退路径
  - 代码落点：`core/browser_fallback.py`
  - 安装方式：`pip install -e ".[full]"`

## 3. optional-dependencies 约定

当前 `pyproject.toml` 中的可选依赖分组：

- `full`
  - 完整功能路径，包含 Playwright
- `cli`
  - 预留给未来进一步细分的轻量 CLI 环境
- `translate`
  - 可选 LLM 翻译能力，包含 `openai`
- `dev`
  - 开发测试工具
- `lint`
  - 静态检查工具

当前默认安装入口是：

```bash
./install.sh
```

其内部实际执行的是：

```bash
pip install -e ".[full]"
```

CI 当前执行的是：

```bash
pip install -e .
```

说明：

- `pip install -e .` 代表基础协议抓取 + CLI/TUI 命令面验证
- `pip install -e ".[full]"` 才包含浏览器回退依赖
- 因此 CI 通过不等于 Playwright / browser fallback 已被完整验证

## 4. 子目录中的历史依赖文件

当前仓库内还存在：

- `references/external/MediaCrawler/requirements.txt`
- `references/external/MediaCrawler/uv.lock`

说明：

- 这两个文件不属于本项目根目录依赖来源
- 当前视为独立子项目或参考内容
- 在未确认其用途前，不静默删除、不纳入主项目安装路径

## 5. 依赖变更流程

新增或修改依赖时，至少同步检查：

1. `pyproject.toml`
2. `install.sh`
3. `README.md`
4. `README_EN.md`
5. `MANUAL.md`
6. 必要测试或 smoke

## 6. 当前已知风险

- `questionary` 仍在 legacy / onboarding 路径中，因此主项目目前不能简单移除它
- `playwright` 是可选依赖，但 `install.sh` 当前默认仍走完整安装路径
- `openai` 仅用于可选翻译路径，不属于基础归档能力
- `cli` optional group 目前基本为空，后续如要细分安装模型，需要同时更新安装脚本、README 和测试契约
