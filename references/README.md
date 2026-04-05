# References

这个目录仅作为 **项目内参考资料区**，不存放任何项目主代码和运行时文件。
任何存储在此处的代码、文档和技巧仅供开发者或 Agent 查阅，不要被 `core/` 或 `cli/` 代码直接 `import` 引用。

当前分为两层核心结构：

## `skills/` (Agent 认知与辅助技能)

包含从 SkillsMP 及其他来源引入的 Agent Skills，主要协助进行架构决策、图形绘制与代码文档化：

- `mermaid-diagram.md`: 关注 Mermaid.js 在项目架构和业务流图生成中的语法最佳实践。
- `mermaid-tools.md`: 收集了提取 Markdown 中的 Mermaid 源码并验证、渲染的脚本指导。
- `readme-generator.md`: 指导 AI Agent 如何遵循 Top GitHub 开源项目的标准（如 React/Vue）来精简改写 README。

**用途**：
- 为代码助手提供操作规范约束（The system prompt augmentation）。
- 缩短代理试错边界，直接应用被认可的代码结构与技巧。

## `external/` (外部工程挂载点)

外部参考仓库的本地挂载点（例如 `MediaCrawler`, `openclaw` 等）：

- 阅读外部项目的实现思路（如跨平台爬虫的鉴权方式或多语言翻译流）。
- 参考目录结构、模块分层、交互设计。
- 只有 `references/external/README.md` 受本仓库 Git 管理，其子目录被 `.gitignore` 忽略，不作为主项目运行时依赖。

---

> [!TIP]
> 如果某个参考最终要变成项目正式流程的一部分，请在 `docs/` 里重新沉淀最终正式版本，并在 `AGENTS.md` 或 `MANUAL.md` 里形成正式约束，而不是长期直接依赖 `references/` 里的草案。
