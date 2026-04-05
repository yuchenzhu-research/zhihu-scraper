---
name: readme-generator
description: High-density, concise README generation skills following top GitHub project guidelines.
author: skillsmp-community
---

# README Generator Skill

This skill enforces best-practice structures for GitHub `README.md` files, ensuring they are concise, conversion-oriented, and easy to read.

## Rules for a Great README

1. **Elevator Pitch First**: The top block must have badges followed by a 1-2 sentence punchy description of what the project does. No fluff.
2. **Quick Start**: Below the introduction, immediately show the quickest way to install and run the project (e.g. `git clone`, `./install.sh`, and a 1-line execution command).
3. **Core Features Section**: Use bullet points to list the capabilities. Avoid long paragraphs.
4. **Push Details to Manuals**: Keep the README strictly minimal! Do NOT clutter the README with 20 edge-case API arguments or configuration tables. Explicitly link to a `MANUAL.md` or `docs/wiki` for any detailed technical usage.
5. **Aesthetics over Quantity**: Ensure spacing, bold text, and markdown blocks look premium. Never write a sprawling 500-line README if 100 lines and a link to the docs can do the job better.

When triggered to rewrite a README, an AI agent MUST apply these 5 rules and trim all edge-case fat.
