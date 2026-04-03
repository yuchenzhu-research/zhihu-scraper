# SkillsMP README Skills

这个目录放的是我从 [skillsmp.com](https://skillsmp.com/) 筛出来、并拉到本项目里的 **README / 文档写作技能**。

目标不是堆很多 skill，而是保留一组对你当前项目最有用的组合：

- 一个管 **README 结构与验收标准**
- 一个管 **README 可读性与呈现**
- 一个管 **语言压缩与行文质量**

## 这次保留的 3 个技能

### 1. `hculap-prd-readme-standard`

- 本地路径：
  [references/skills/docs-writing/hculap-prd-readme-standard/SKILL.md](/Users/yuchenzhu/Desktop/github/zhihu/references/skills/docs-writing/hculap-prd-readme-standard/SKILL.md)
- 来源：
  `hculap/better-code`
- 适合你的原因：
  这个 skill 最强的是把 README 当成“产品文档入口”来做，强调首屏判断、5 分钟跑通、支持路径、FAQ、维护状态和防文档漂移。你的项目现在已经有安装脚本、首页菜单、manual、examples，这个 skill 很适合拿来继续收紧主 README 的结构。
- 你可以重点学：
  - Hero 区怎么写
  - Quick Start 怎么控制在 3 到 5 分钟
  - README 应该保留哪些 80/20 信息，哪些放到 manual
  - 怎么用验收标准检查 README 是否啰嗦或失焦

### 2. `wahidyankf-readme-writing-readme-files`

- 本地路径：
  [references/skills/docs-writing/wahidyankf-readme-writing-readme-files/SKILL.md](/Users/yuchenzhu/Desktop/github/zhihu/references/skills/docs-writing/wahidyankf-readme-writing-readme-files/SKILL.md)
- 来源：
  `wahidyankf/open-sharia-enterprise`
- 适合你的原因：
  这个 skill 特别适合你现在这种“功能很多，但首页要尽量清楚”的项目。它强调 problem-solution hook、plain language、段落不宜过长、利益点优先、层级分明。你现在的中英文 README 其实最需要的就是这种“扫描感”和“首屏可读性”。
- 你可以重点学：
  - 项目简介先讲价值而不是先讲实现
  - 每段不要太长
  - README 中尽量少出现没解释的术语
  - 用更强的视觉层级组织 Quick Start / Features / FAQ

### 3. `obra-writing-clearly-and-concisely`

- 本地路径：
  [references/skills/docs-writing/obra-writing-clearly-and-concisely/SKILL.md](/Users/yuchenzhu/Desktop/github/zhihu/references/skills/docs-writing/obra-writing-clearly-and-concisely/SKILL.md)
- 附带参考：
  [references/skills/docs-writing/obra-writing-clearly-and-concisely/elements-of-style.md](/Users/yuchenzhu/Desktop/github/zhihu/references/skills/docs-writing/obra-writing-clearly-and-concisely/elements-of-style.md)
- 来源：
  `obra/the-elements-of-style`
- 适合你的原因：
  这个不是 README 专项，但非常适合做 README 的最后一轮“压缩和润色”。你的仓库现在中英文文档都比较完整，下一步最容易出现的问题不是缺内容，而是句子偏长、技术词偏多、重复解释。这个 skill 就是拿来做最后一层文案收束的。
- 你可以重点学：
  - 删冗余
  - 改成主动语态
  - 把抽象句子改成具体句子
  - 让句子更短、更硬、更可扫读

## 推荐使用顺序

如果你后面继续改中英文 README，我建议按这个顺序参考：

1. 先看 `hculap-prd-readme-standard`
   先确定 README 骨架和章节顺序。
2. 再看 `wahidyankf-readme-writing-readme-files`
   再把首页表达、段落长度、视觉层级和说明方式调顺。
3. 最后看 `obra-writing-clearly-and-concisely`
   最后一轮删冗、压缩、润色。

## 为什么只选这 3 个

因为你现在要的是“把 README 做小而精”，不是做一个文档技能大仓库。

这 3 个加起来已经覆盖了：

- 结构
- 表达
- 语言质量

对你当前这个知乎项目来说，已经足够了。

## 说明

- 这些技能现在是 **项目内参考资料**
- 它们被放在 `references/skills/docs-writing/`，方便你本地对照阅读
- 这不是自动安装到全局 Codex skills 的目录
- 如果你后面想把其中某个 skill 安装到 `~/.codex/skills` 里长期使用，可以再单独做一次全局安装
