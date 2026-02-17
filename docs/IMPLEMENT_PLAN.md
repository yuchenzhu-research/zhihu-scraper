# 📋 实现计划 (Implementation Plan)

> 知乎爬虫 v1.x 版本路线图

---

## 状态追踪

| 状态 | 说明 |
|------|------|
| ✅ 已完成 | 功能已实现，可使用 |
| 🔄 进行中 | 正在开发中 |
| ⏳ 待开始 | 计划中，尚未开始 |

---

## 🎯 优先级速查

```
P0 (必须做): 修复现有 bug，完善基础功能
P1 (应该做): 提升代码质量和可维护性
P2 (可以做): 锦上添花的功能增强
```

---

## v1.1.0 - 稳定性与可靠性

### ✅ 配置管理系统
| 检查项 | 状态 | 说明 |
|--------|------|------|
| config.yaml | ✅ | 统一配置管理 |
| pyproject.toml | ✅ | 现代化依赖管理 |

### 🔄 错误处理与重试机制
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 异常分类体系 | ✅ | core/errors.py |
| 智能重试 | ⏳ | 需集成到抓取流程 |
| 断点续传 | ⏳ | 中断后恢复 |

**下一步任务**:
```python
# 1. 在 scraper.py 中集成重试机制
async def fetch_with_retry(url, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await _fetch_one(url)
        except ZhihuScraperError as e:
            if e.severity == ErrorSeverity.FATAL:
                raise
            await asyncio.sleep(backoff(attempt))
```

### ✅ 并发性能优化
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 图片并发下载 | ✅ | Semaphore 控制 |
| 配置化并发数 | ✅ | config.yaml |

### ⏳ 完善日志系统
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 基础日志 | ✅ | structlog |
| 请求追踪 | ⏳ | request_id 关联 |
| 慢请求告警 | ⏳ | 超时阈值监控 |

---

## v1.2.0 - 代码质量

### 📝 类型注解
| 检查项 | 优先级 | 状态 |
|--------|--------|------|
| scraper.py | P0 | ⏳ |
| converter.py | P0 | ⏳ |
| cli/app.py | P1 | ⏳ |
| config.py | P1 | ⏳ |
| errors.py | P2 | ⏳ |

**任务**: 运行 `mypy --strict` 并修复所有类型错误

### 🧪 测试覆盖
| 检查项 | 优先级 | 状态 |
|--------|--------|------|
| 配置加载测试 | P1 | ⏳ |
| 公式转换测试 | P1 | ⏳ |
| URL 解析测试 | P1 | ⏳ |
| E2E 测试 | P2 | ⏳ |

### 📦 代码重构
| 检查项 | 优先级 | 状态 |
|--------|--------|------|
| src/ 目录结构 | P1 | ⏳ |
| 导出 (\_\_all\_\_) | P2 | ⏳ |
| 常量分离 | P2 | ⏳ |

---

## v1.3.0 - 用户体验增强

### 🔧 CLI 增强
| 功能 | 优先级 | 状态 |
|------|--------|------|
| fetch 命令 | P0 | ✅ |
| batch 命令 | P0 | ✅ |
| config 命令 | P1 | ✅ |
| check 命令 | P1 | ✅ |
| 进度显示 | P1 | ⏳ |
| 自动补全 | P2 | ⏳ |

### 📊 输出格式支持
| 格式 | 优先级 | 状态 |
|------|--------|------|
| Markdown | P0 | ✅ |
| PDF | P2 | ⏳ |
| HTML | P2 | ⏳ |
| JSON | P2 | ⏳ |

### 🎨 模板系统
| 模板 | 优先级 | 状态 |
|------|--------|------|
| 默认 | P0 | ✅ |
| Obsidian | P1 | ⏳ |
| Notion | P2 | ⏳ |
| 学术论文 | P2 | ⏳ |

---

## v2.0.0 - 架构升级

### 🏗️ 通用爬虫框架
```
┌─────────────────────────────────────────────────────────────┐
│                    FrogScraper Framework                     │
├─────────────────────────────────────────────────────────────┤
│  Platform Adapter (平台适配器)                                │
│  ├── ZhihuAdapter                                           │
│  ├── BilibiliAdapter  (未来)                                 │
│  ├── XiaohongshuAdapter (未来)                               │
│  └── BaseAdapter                                            │
├─────────────────────────────────────────────────────────────┤
│  Extractor Pipeline (提取管道)                               │
│  ├── ContentExtractor                                       │
│  ├── ImageExtractor                                         │
│  └── MetadataExtractor                                      │
├─────────────────────────────────────────────────────────────┤
│  Exporter (导出器)                                           │
│  ├── MarkdownExporter                                       │
│  ├── PDFExporter                                            │
│  └── DataExporter                                           │
└─────────────────────────────────────────────────────────────┘
```

### 🌐 HTTP API 服务
| 功能 | 优先级 | 状态 |
|------|--------|------|
| FastAPI 服务 | P2 | ⏳ |
| Web UI | P2 | ⏳ |
| WebSocket 实时推送 | P3 | ⏳ |

### 📱 任务队列
| 功能 | 优先级 | 状态 |
|------|--------|------|
| 任务持久化 | P2 | ⏳ |
| 定时任务 | P3 | ⏳ |
| 分布式支持 | P3 | ⏳ |

---

## 📌 下一步行动 (Next Steps)

### 立即可做 (5-10 分钟)

1. **运行类型检查**
   ```bash
   pip install mypy
   mypy core/ --strict
   ```

2. **添加一个测试**
   ```python
   # tests/test_config.py
   def test_config_load():
       from core.config import get_config
       cfg = get_config()
       assert cfg.output.directory == "data"
   ```

3. **完善 main.py 日志**
   在现有代码中添加更多日志调用

### 本周可做 (1-2 小时)

1. **集成重试机制**
   - 在 `download_images` 基础上
   - 扩展到 `fetch_page` 方法

2. **完善 batch 命令**
   - 真正的并发抓取 (当前是顺序)
   - 进度条实时显示

3. **添加 GitHub Actions**
   - 自动类型检查
   - 自动运行测试

---

## 📚 参考资源

- [PEP 621 - pyproject.toml](https://peps.python.org/pep-0621/)
- [Structlog 文档](https://www.structlog.org/)
- [Typer 文档](https://typer.tiangolo.com/)
- [Playwright Python](https://playwright.dev/python/)
- [Mypy 速查](https://mypy.readthedocs.io/en/stable/cheat_sheet.html)

---

> 本文档会随项目进展持续更新