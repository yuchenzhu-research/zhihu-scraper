# Stage 6 Issue Reply Templates

这份文档用于把阶段三到阶段五里已经确认的问题、修复和升级方式整理成可以直接对外回复的文本模板。

## Template A: Missing `questionary` / `structlog` After Branch Switch

### Suggested reply (CN)

问题本身不是命令写错，而是当前环境没有和当前分支的 `pyproject.toml` 完整同步。

这个项目在最近几个阶段新增了运行时依赖，例如：

- `questionary`
- `structlog`
- `textual`

如果是跨分支切换后直接继续用旧环境，很容易出现：

- `ModuleNotFoundError: No module named 'questionary'`
- `ModuleNotFoundError: No module named 'structlog'`

当前建议做法：

```bash
pip install -e .
```

如果环境已经比较乱，直接重建：

```bash
./install.sh --recreate
```

另外，当前版本已经做了两层兼容收口：

1. 缺 `questionary` 时不会再直接裸崩，而是给出明确安装提示
2. 缺 `structlog` 时会退回标准库日志，不再在 import 阶段直接中断

如果你是在 Linux / macOS 上从旧分支切到新分支，优先怀疑环境没重装，而不是命令本身出错。

### Suggested reply (EN)

The command itself is not the main issue here. The actual problem is that the environment was not fully resynced with the current branch’s `pyproject.toml`.

Recent refactor stages added runtime dependencies such as:

- `questionary`
- `structlog`
- `textual`

If you switch branches and keep using an older virtualenv, you may hit:

- `ModuleNotFoundError: No module named 'questionary'`
- `ModuleNotFoundError: No module named 'structlog'`

Recommended recovery path:

```bash
pip install -e .
```

If the environment has drifted too far, recreate it:

```bash
./install.sh --recreate
```

The current codebase also now softens these failures:

1. missing `questionary` exits with a clearer install hint
2. missing `structlog` falls back to standard logging instead of crashing at import time

## Template B: Linux Cannot `ls` the Export Directory

### Suggested reply (CN)

这个问题不是“文件没生成”，而是旧版本输出目录命名对 shell 不友好。

旧目录格式类似：

```text
[2026-03-31] 标题 (answer-123456)
```

这里的：

- `[]`
- `()`
- 空格

虽然不是非法路径，但在 Bash / Zsh 下非常容易导致：

```text
syntax error near unexpected token '('
```

当前版本已经把**新生成的目录**改成更适合 Linux shell 的命名，例如：

```text
2026-03-31_标题--answer-123456
```

注意两点：

1. 这个修复只影响**新导出的内容**
2. 历史目录不会自动改名

如果你现在操作的是旧目录，临时可用：

```bash
ls "/path/to/[2026-03-31] 标题 (answer-123456)"
```

但建议重新抓取一次，让它按新命名规则生成。

### Suggested reply (EN)

This is not usually a “save failed” issue. It is typically an older output naming format that was unfriendly to the shell.

Older directories looked like:

```text
[2026-03-31] Title (answer-123456)
```

Characters such as:

- `[]`
- `()`
- spaces

are not illegal path characters, but they are awkward in Bash / Zsh and can trigger errors like:

```text
syntax error near unexpected token '('
```

Newly generated exports now use a shell-friendlier naming scheme such as:

```text
2026-03-31_Title--answer-123456
```

Two caveats:

1. this only affects newly generated exports
2. old directories are not renamed automatically

For old paths, quoting still works as a temporary workaround:

```bash
ls "/path/to/[2026-03-31] Title (answer-123456)"
```

But the recommended path is to regenerate the export under the new naming scheme.

## Template C: Which Branch Should Be Merged?

### Suggested reply (CN)

当前建议把 `test` 作为治理阶段的合流分支合并回 `main`，并且：

- 用普通 merge commit
- 不要 squash
- 合并后保留 `test` 分支

原因是这条分支里每个阶段都有明确 checkpoint，适合继续追踪和回退。

### Suggested reply (EN)

The current recommendation is to merge `test` back into `main` as the governance/refactor branch, with:

- a normal merge commit
- no squash
- keeping the `test` branch after merge

This preserves the staged checkpoints and keeps rollback granularity intact.
