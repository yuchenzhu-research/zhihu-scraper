# Stage 1 Skill Foundation / 阶段一：Skill 基础设施收尾

这份文档记录阶段一的收尾状态，目的是把“引入 skill 参考资料”这件事从临时操作，变成可持续维护的仓库结构。

## 本阶段做了什么

1. 从 SkillsMP 追溯来源仓库，筛选出适合本项目的工程治理 skill
2. 把 skill 分成两大类：
   - 检测型：横向审计和质量检查
   - 推进型：纵向治理和结构优化
3. 把原本分散的 `references/skillsmp` 与 `references/skillsmp-curated` 合并成统一结构

## 当前目录结构

```text
references/
  README.md
  skills/
    docs-writing/
    engineering/
      quality-detection/
      engineering-progression/
```

### `references/skills/docs-writing/`

用途：
- README 结构审计
- 文档可读性优化
- 文案压缩与清晰化

### `references/skills/engineering/quality-detection/`

用途：
- 代码库整体审计
- 结构一致性审计
- 测试与质量门禁审计

### `references/skills/engineering/engineering-progression/`

用途：
- 架构演进
- 重构整理
- 防御式编程
- 文档治理

## 为什么要改目录

旧结构的问题是：

- `skillsmp` 与 `skillsmp-curated` 命名体系并列，不知道哪个是旧的，哪个是新的
- 文档类 skill 和工程类 skill 没有明确隔离
- 后续阶段二审计时，没有统一入口

新结构的目标是：

- 一眼看清 skill 资源在哪
- 一眼看清哪些是写作文档类，哪些是工程治理类
- 给阶段二和后续工程整治提供稳定入口

## 阶段二入口

阶段二不再先改代码，而是先用这批 skill 做一次正式审计：

1. `quality-detection/audit`
2. `quality-detection/coherence-audit`
3. `quality-detection/testing-qa`
4. `docs-writing/*`

预期输出：

- 跨平台可用性清单
- 命令面执行清单
- 文档漂移清单
- 工程结构与技术债清单
- P0 / P1 / P2 优先级矩阵
