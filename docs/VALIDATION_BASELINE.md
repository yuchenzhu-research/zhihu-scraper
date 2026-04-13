# Validation Baseline / 验证基线

本文件记录当前仓库的默认验证基线，用来替代已废弃的阶段性验证矩阵引用。

## 1. 当前最小回归集合

默认最小回归集合：

```bash
./.venv/bin/python -m unittest -q tests.test_docs_sync tests.test_command_surface tests.test_install_contract
```

这组测试的目标是先守住：

- 文档同步与入口表述
- 命令面与主入口语义
- 安装契约与平台边界

## 2. 当前 CI 验证现实

GitHub Actions 当前验证：

- `ubuntu-latest`
- `macos-latest`

CI 当前执行：

```bash
pip install -e .
python -m compileall cli core
python -m unittest -q tests.test_cli_compat tests.test_docs_sync tests.test_command_surface tests.test_tui_rebuild tests.test_save_pipeline tests.test_save_contracts tests.test_config_view tests.test_scraper_payloads tests.test_scraper_contracts tests.test_config_schema tests.test_config_runtime tests.test_install_contract tests.test_workflow_service tests.test_db_contract
python cli/app.py --help
python cli/app.py manual --help
python cli/app.py onboard --help
python cli/app.py fetch --help
python cli/app.py batch --help
python cli/app.py creator --help
python cli/app.py monitor --help
python cli/app.py query --help
python cli/app.py interactive --help
python cli/app.py config --help
python cli/app.py check --help
```

## 3. 当前验证边界

需要明确：

- CI 的 `pip install -e .` 只覆盖基础包，不等于 Playwright / browser fallback 已被完整验证
- 本地完整功能路径仍然是 `./install.sh` 或 `pip install -e ".[full]"`
- Windows 仍然只有 runbook，不是当前的一等安装路径

## 4. 按改动类型补充的验证

如果改动涉及以下范围，应补对应验证：

- 文档 / 命令面：`tests.test_docs_sync`、`tests.test_command_surface`
- 配置层：`tests.test_config_schema`、`tests.test_config_runtime`
- 保存链路：`tests.test_save_pipeline`、`tests.test_save_contracts`
- scraper contract：`tests.test_scraper_payloads`、`tests.test_scraper_contracts`
- workflow / 执行桥：`tests.test_workflow_service`、相关 CLI/TUI 回归
- 安装 / 平台边界：`tests.test_install_contract`

## 5. 权威关系

验证基线相关文档职责如下：

- `CONSTITUTION.md`：定义质量门禁存在与边界
- `AGENTS.md`：定义默认执行顺序、同步纪律和结果汇报要求
- `MANUAL.md`：给维护者解释何时运行哪些检查
- `docs/PLATFORM_SUPPORT.md`：说明平台支持边界
- `docs/WINDOWS_RUNBOOK.md`：说明 Windows 手动路径
- `.github/workflows/ci.yml`：记录当前自动化执行事实
