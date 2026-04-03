# References

这个目录只放 **项目内参考资料**，不放运行时代码，也不放本地产物。

现在统一分成两层：

- `skills/`
  从 SkillsMP 和相关来源筛进来的 skill 参考资料
- `openclaw/`
  外部参考仓库占位，当前不纳入正式项目结构，也不参与版本管理

## `skills/` 结构

### `skills/docs-writing/`

这一层保留偏 README / 文档表达的 skill：

- README 结构标准
- README 可读性
- 文案压缩与润色

用途：
- 收紧 [README.md](/Users/yuchenzhu/Desktop/github/zhihu/README.md)
- 收紧 [README_EN.md](/Users/yuchenzhu/Desktop/github/zhihu/README_EN.md)
- 审计 help / manual / 安装说明是否漂移

### `skills/engineering/`

这一层保留偏工程治理的 skill，并继续分成两类：

- `quality-detection/`
  横向审计：质量、测试、结构一致性
- `engineering-progression/`
  纵向推进：架构演进、重构、防御式设计、文档治理

用途：
- 做阶段二的质量盘点
- 做阶段三之后的结构治理和工程推进

## 边界

- `references/` 是参考资料区，不是代码主实现区
- 这里的内容可以被引用，但不应该被业务代码直接 import
- 如果某个参考最终要变成项目规范，应该在 `docs/` 里重新沉淀正式版本，而不是长期直接依赖参考仓库原文
