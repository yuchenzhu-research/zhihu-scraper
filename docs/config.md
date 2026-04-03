# config.md

本文档说明本项目的配置入口、schema、运行时行为和兼容原则。

## 1. 配置文件入口

默认配置文件为仓库根目录的：

```text
config.yaml
```

运行时入口：

- facade：`core/config.py`
- runtime loader：`core/config_runtime.py`
- schema：`core/config_schema.py`
- logging：`core/logging_setup.py`
- path helper：`core/project_paths.py`

## 2. 配置加载模型

当前加载顺序：

```text
config.yaml
-> yaml.safe_load
-> core/config_schema.build_config_from_dict(...)
-> Config dataclass
-> logging setup
-> runtime singleton cache
```

如果配置文件不存在：

- 记录警告
- 回退默认配置
- 仍会完成 logging setup，并继续走统一 facade

如果配置文件存在但字段不兼容：

- 尽量兼容旧字段
- 兼容失败时回退默认配置，并输出提示
- `override_level` 这类运行时覆盖仍会应用到回退后的默认配置

## 3. 配置结构

### 3.1 `zhihu`

负责知乎访问相关配置。

子项包括：

- `cookies`
  - `file`
  - `pool_dir`
  - `required`
- `browser`
  - `headless`
  - `timeout`
  - `viewport`
  - `channel`
  - `args`
- `anti_detection`
  - `stealth`
  - `webgl`
  - `navigator`
- `signature`
  - `enabled`

### 3.2 `crawler`

负责抓取通用运行参数。

子项包括：

- `retry`
  - 最大重试次数、退避参数、jitter
- `scroll`
  - 页面滚动相关
- `humanize`
  - 随机延迟和人类行为模拟
- `images`
  - 图片下载并发、超时、referer

### 3.3 `output`

负责本地输出结构。

子项包括：

- `directory`
- `format`
- `images_subdir`
- `folder_format`

当前代码中还兼容旧字段：

- `download_images`

该字段不再是推荐写法，但为了兼容历史配置仍被 schema 接受。

### 3.4 `logging`

负责日志行为。

子项包括：

- `level`
- `format`
- `file`
- `log_exceptions`

## 4. 运行时路径约定

当前默认运行时目录是：

```text
.local/
```

重要路径包括：

- `.local/cookies.json`
- `.local/cookie_pool/`
- `.local/logs/`

兼容历史路径：

- `cookies.json`
- `cookie_pool/`

说明：

- 仓库根目录不再推荐直接承载长期凭据
- `.local/` 用于存放凭据、日志等运行态文件
- `zhihu config --show` 会同时显示 configured path 和 active path
- 如果由于兼容策略实际命中了仓库根目录旧路径，`zhihu config --show` 和 `zhihu check` 都会明确显示 legacy fallback 状态

## 5. 单例与 facade

当前 `core/config.py` 已不直接承载完整 schema，而是作为 facade：

- `get_config()`
- `get_logger()`
- `get_humanizer()`
- `setup_logging()`
- `resolve_project_path()`

这层的作用是：

- 给 CLI 和 core 模块提供稳定入口
- 避免调用方直接依赖 loader / schema 的内部细节

## 6. 与文档和测试的联动

配置系统变更时，默认需要同步检查：

- `README.md`
- `README_EN.md`
- `MANUAL.md`
- `cli/manual_content.py`
- `tests/test_config_schema.py`
- `tests/test_config_runtime.py`
- `tests/test_install_contract.py`

## 7. 已知限制

- 当前仍然以单配置文件模型为主，不支持 profile/overlay 体系
- 浏览器配置与协议配置还未完全拆成独立 provider 层
- 某些历史字段虽然保留兼容，但已经不建议继续在新配置里使用

## 8. 后续建议

- 继续将兼容层与 schema 说明拆得更明确
- 考虑为配置错误建立更结构化的诊断输出
- 如果未来引入更多运行模式，优先扩展 schema 和 loader，不要回到命令层散落读取配置的做法
