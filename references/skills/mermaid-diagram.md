---
name: mermaid-diagram
description: Generates educational and architectural diagrams using Mermaid code blocks.
author: mjunaidca
---

# Mermaid Diagram Generation Skill

This skill is designed to help AI agents generate and insert Mermaid.js code blocks visualizing concepts, architectures, and workflows.

## Guidelines

1. **Syntax Integrity**: Always enclose Mermaid definitions inside \`\`\`mermaid ... \`\`\` blocks.
2. **Naming Constraints**: Avoid spaces or special characters in node handles (e.g. `A("Node 1")` not `A Node("Node 1")`).
3. **Themes**: Respect existing codebase themes (e.g. if styling nodes, prefer consistent color palettes).
4. **Validation**: Use strict validation for sequence diagrams, state diagrams, and flowcharts.

To use this skill, generate the corresponding `mermaid` block directly at the spot in the markdown document where the visualization is requested.
