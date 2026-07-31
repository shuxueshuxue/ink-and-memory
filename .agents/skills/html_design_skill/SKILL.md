---
name: html-design-workflow
description: >
  Multi-agent UI/UX design workflow that converts images to HTML/Tailwind code.
  Use when users want to generate HTML/CSS from UI screenshots, create PRD documents
  from visual designs, convert wireframes to working code, or build responsive web
  pages from mockups. Orchestrates 4 specialized agents sequentially.
---

# HTML Design Workflow

A 4-stage automated pipeline that transforms design images into production-ready HTML/Tailwind code.

## Required Inputs

Create these files before running:
- `files/inputs/target_image.png` - The UI design image
- `files/inputs/topic.txt` - Topic/context description (e.g., "个人主页")

## Workflow Stages

The pipeline runs sequentially - each stage depends on the previous:

### Stage 1: PRD Architect
- **Input**: `target_image.png` + `topic.txt`
- **Output**: `files/workspace/1_prd_draft.md`
- **Full prompt**: [references/agent1-prd-architect.md](references/agent1-prd-architect.md)

### Stage 2: Structure Sketch Designer  
- **Input**: PRD draft + original image
- **Output**: `files/workspace/2_structure_sketch.md`
- **Full prompt**: [references/agent2-sketch-designer.md](references/agent2-sketch-designer.md)

### Stage 3: Hierarchy Logic Mapper
- **Input**: PRD + Structure Sketch
- **Output**: `files/workspace/3_hierarchy_logic.md`
- **Full prompt**: [references/agent3-logic-mapper.md](references/agent3-logic-mapper.md)

### Stage 4: UI Art Director
- **Input**: PRD (style) + Hierarchy (structure)
- **Output**: `files/workspace/4_ui_design.md`
- **Full prompt**: [references/agent4-ui-director.md](references/agent4-ui-director.md)

## Orchestrator

For automated pipeline management, see: [references/orchestrator.md](references/orchestrator.md)

The orchestrator:
- Verifies inputs exist
- Spawns agents sequentially
- Validates each stage output before proceeding
- Reports completion status

## Technical Stack

- HTML5 + Tailwind CSS 2.2.19
- Font Awesome 6.0.0
- Google Fonts: Noto Serif SC, Noto Sans SC

## Quick Start

```bash
mkdir -p files/inputs files/workspace
cp your-design.png files/inputs/target_image.png
echo "个人主页" > files/inputs/topic.txt
```

Then follow the orchestrator workflow or run each agent stage manually.
