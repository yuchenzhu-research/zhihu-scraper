---
name: mermaid-tools
description: Scripts and guidelines for extracting and converting Mermaid code blocks to high-quality images.
author: daymade
---

# Mermaid Tools Skill

This skill provides the execution steps for AI agents to locate Mermaid blocks in markdown and automatically generate high-definition PNGs or SVGs out of them.

## Agent Workflow

1. Search the target markdown file for ````mermaid ... ```` blocks.
2. For each block, extract the text and save it to a temporary `.mmd` file.
3. Validate the `mmd` file locally (using tools like `mmdc` if available).
4. Auto-generate a visual graphic or instruct the user on how they can render the graphic within GitHub natively.

> **Note**: GitHub automatically renders ````mermaid` blocks in READMEs. This skill is primarily used when static images are required (e.g. for embedding in platforms that do not support raw mermaid rendering).
