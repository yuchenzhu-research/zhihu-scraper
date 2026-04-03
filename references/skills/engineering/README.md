# SkillsMP Curated Engineering Skills

这个目录是从 [SkillsMP](https://skillsmp.com/) 追溯到对应 GitHub 仓库后，筛出来并拉进本项目的 **工程治理 skill 集合**。

目标不是“收集更多 skill”，而是给这个仓库建立两类可持续使用的工程底座：

- `quality-detection/`
  用于横向审计和质量检查
- `engineering-progression/`
  用于纵向推进、结构优化和防止继续堆成大单文件

## 目录分类

### 1. `quality-detection/`

- `audit/`
  来源：SkillsMP `audit`
  仓库：`willietran/autoboard`
  用途：做多维度代码库审计，适合整体质量盘点

- `coherence-audit/`
  来源：SkillsMP `coherence-audit`
  仓库：`willietran/autoboard`
  用途：检查多阶段改动、并行改动后的结构一致性和层次漂移

- `testing-qa/`
  来源：SkillsMP `testing-qa`
  选取仓库：`ngxtm/devkit`
  用途：建立测试金字塔、质量门禁、回归检查路线

### 2. `engineering-progression/`

- `improve-codebase-architecture/`
  来源：SkillsMP `improve-codebase-architecture`
  仓库：`Tokugero/opencode-project-template`
  用途：推动模块边界、架构演进、避免脚本式堆叠

- `refactoring/`
  来源：SkillsMP / `tswr/engineering-mastery-plugin`
  用途：做行为不变的代码整理、拆分和命名优化

- `defensive-programming/`
  来源：SkillsMP / `tswr/engineering-mastery-plugin`
  用途：强化接口契约、错误边界和更难误用的代码设计

- `documentation/`
  来源：SkillsMP / `tswr/engineering-mastery-plugin`
  用途：推进实现、说明书、接口文档的同步治理

## 说明

- 这些 skill 是 **项目内参考资源**，不是已经安装到全局 Codex skills 的目录。
- 与 [references/skills/docs-writing](/Users/yuchenzhu/Desktop/github/zhihu/references/skills/docs-writing) 相比，这一层更偏工程治理和代码推进。
- 后续如果要正式做成可复用 skill 系统，建议再在仓库内补一层你自己的项目专用 SKILL，结合这些外部来源二次整理，而不是直接照搬。
