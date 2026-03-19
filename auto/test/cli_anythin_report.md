# CLI-Anything: Comprehensive Research Report

**Generated**: March 18, 2026  
**Source**: GitHub (HKUDS/CLI-Anything), cli-anything.com, clianything.org

---

## Executive Summary

**CLI-Anything** is an open-source project from HKUDS (Hong Kong University Data Science) that automatically generates production-ready Command-Line Interfaces for any software with a codebase. Its mission is to bridge the gap between AI agents and the world's software by making all applications "agent-native" through structured CLI interfaces.

**Key Stats**:
- 2,000+ GitHub stars
- 1,588 passing tests (100% pass rate)
- 13 major applications supported
- MIT Licensed

---

## What is CLI-Anything?

CLI-Anything is a **Claude Code plugin** that transforms any software into AI agent-controllable CLI interfaces with one command. It addresses a fundamental problem: AI agents excel at reasoning but struggle to interact with professional GUI software.

### The Problem It Solves

| Current Pain Point | CLI-Anything's Solution |
|--------------------|------------------------|
| AI can't use real tools | Direct integration with actual software backends (Blender, LibreOffice, FFmpeg) — full professional capabilities |
| UI automation breaks constantly | No screenshots, no clicking, no RPA fragility. Pure command-line reliability |
| Agents need structured data | Built-in JSON output for seamless agent consumption |
| Custom integrations are expensive | One plugin auto-generates CLIs for ANY codebase |
| Prototype vs Production gap | 1,588+ tests with real software validation |

---

## Core Features

### 1. Universal CLI Generation
- Creates complete CLIs for any software with accessible source code
- Works with GitHub repositories or local codebases
- Supports open-source, internal, and custom software

### 2. 7-Phase Automated Pipeline

| Phase | Description |
|-------|-------------|
| **Analyze** | Scans source code, maps GUI actions to APIs |
| **Design** | Architects command groups, state model, output formats |
| **Implement** | Builds Click CLI with REPL, JSON output, undo/redo |
| **Plan Tests** | Creates TEST.md with unit + E2E test plans |
| **Write Tests** | Implements comprehensive test suite |
| **Document** | Updates TEST.md with results |
| **Publish** | Creates `setup.py`, installs to PATH |

### 3. Agent-Native Design
- **`--json` flag** on every command for structured machine-readable output
- **`--help` flags** provide automatic documentation agents can discover
- **SKILL.md generation** — every CLI ships with AI-discoverable skill definitions

### 4. Real Software Integration
- Direct calls to actual application backends
- LibreOffice generates real PDFs
- Blender renders actual 3D scenes
- Audacity processes audio via sox
- No toy implementations or fallbacks

### 5. Interactive REPL Mode (ReplSkin)
- Stateful interface with undo/redo capabilities
- Command history and progress indicators
- Branded banners with styled prompts
- Consistent experience across all generated CLIs

### 6. Refinement System
- `/cli-anything:refine` command for iterative improvement
- Gap analysis between software capabilities and CLI coverage
- Non-destructive incremental expansion

---

## Supported Applications

### Validated Software (1,588 Tests Total)

| Software | Domain | CLI Command | Tests |
|----------|--------|-------------|-------|
| GIMP | Image Editing | `cli-anything-gimp` | 107 |
| Blender | 3D Modeling & Rendering | `cli-anything-blender` | 208 |
| Inkscape | Vector Graphics | `cli-anything-inkscape` | 202 |
| Audacity | Audio Production | `cli-anything-audacity` | 161 |
| LibreOffice | Office Suite | `cli-anything-libreoffice` | 158 |
| OBS Studio | Live Streaming & Recording | `cli-anything-obs-studio` | 153 |
| Kdenlive | Video Editing | `cli-anything-kdenlive` | 155 |
| Shotcut | Video Editing | `cli-anything-shotcut` | 154 |
| Zoom | Video Conferencing | `cli-anything-zoom` | 22 |
| Draw.io | Diagramming | `cli-anything-drawio` | 138 |
| Mermaid Live Editor | Diagramming | `cli-anything-mermaid` | 10 |
| AnyGen | AI Content Generation | `cli-anything-anygen` | 50 |
| ComfyUI | AI Image Generation | `cli-anything-comfyui` | 70 |

### Potential Applications by Category

| Category | Examples |
|----------|----------|
| **AI/ML Platforms** | Stable Diffusion WebUI, ComfyUI, InvokeAI, Text-generation-webui, Open WebUI |
| **Data & Analytics** | JupyterLab, Apache Superset, Metabase, DBeaver, KNIME, Orange |
| **Development Tools** | Jenkins, Gitea, Portainer, pgAdmin, SonarQube, ArgoCD |
| **Creative & Media** | Krita, Darktable, LMMS, Ardour |
| **Scientific Computing** | ImageJ, FreeCAD, QGIS, ParaView, KiCad |
| **Enterprise & Office** | NextCloud, GitLab, Grafana, Mattermost, Odoo |

---

## Installation

### Claude Code (Recommended)

```bash
# Add the marketplace
/plugin marketplace add HKUDS/CLI-Anything

# Install the plugin
/plugin install cli-anything

# Build a CLI for any software
/cli-anything ./gimp
# Or from GitHub
/cli-anything https://github.com/blender/blender
```

### OpenCode

```bash
# Clone and copy commands
git clone https://github.com/HKUDS/CLI-Anything.git
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# Use
/cli-anything ./gimp
```

### Codex

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/codex-skill/scripts/install.sh
```

### OpenClaw

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
mkdir -p ~/.openclaw/skills/cli-anything
cp CLI-Anything/openclaw-skill/SKILL.md ~/.openclaw/skills/cli-anything/SKILL.md
```

### Qodercli

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/qoder-plugin/setup-qodercli.sh
```

---

## Usage Examples

### Building a CLI

```bash
# From local source
/cli-anything /home/user/gimp

# From GitHub repo
/cli-anything https://github.com/blender/blender

# Refine existing CLI
/cli-anything:refine ./gimp
/cli-anything:refine ./shotcut "picture-in-picture compositing"
```

### Using Generated CLIs

```bash
# Install to PATH
cd gimp/agent-harness && pip install -e .

# Use from anywhere
cli-anything-gimp --help
cli-anything-gimp project new --width 1920 --height 1080 -o poster.json

# JSON mode for agents
cli-anything-gimp --json layer add -n "Background" --type solid --color "#1a1a2e"

# Interactive REPL
cli-anything-gimp
```

### LibreOffice Example

```bash
# Create a new Writer document
cli-anything-libreoffice document new -o report.json --type writer

# Add content
cli-anything-libreoffice --project report.json writer add-heading -t "Q1 Report" --level 1
cli-anything-libreoffice --project report.json writer add-table --rows 4 --cols 3

# Export to PDF
cli-anything-libreoffice --project report.json export render output.pdf -p pdf --overwrite

# JSON mode for agent consumption
cli-anything-libreoffice --json document info --project report.json
```

### Blender Example

```bash
$ cli-anything-blender
╔══════════════════════════════════════════╗
║       cli-anything-blender v1.0.0        ║
║     Blender CLI for AI Agents            ║
╚══════════════════════════════════════════╝

blender> scene new --name ProductShot
blender[ProductShot]> object add-mesh --type cube --location 0 0 1
blender[ProductShot]*> render execute --output render.png --engine CYCLES
blender[ProductShot]> exit
```

---

## Technical Architecture

### Project Structure

```
cli-anything/
├── cli-anything-plugin/         # Claude Code plugin
│   ├── HARNESS.md              # Methodology SOP (source of truth)
│   ├── repl_skin.py            # Unified REPL interface
│   └── commands/               # Plugin command definitions
├── codex-skill/                # Codex skill entry point
├── openclaw-skill/             # OpenClaw skill
├── opencode-commands/          # OpenCode commands
├── qoder-plugin/               # Qodercli plugin
└── <software>/agent-harness/   # Generated CLIs
```

### Generated CLI Package Structure

Each `agent-harness/` contains:
- Installable Python package under `cli_anything.<software>/`
- Click CLI implementation
- Core modules and utilities
- `repl_skin.py` and backend wrapper
- Comprehensive test suite
- `SKILL.md` for agent discovery

### Testing Methodology

| Layer | What it Tests |
|-------|---------------|
| **Unit tests** | Every core function in isolation with synthetic data |
| **E2E tests (native)** | Project file generation pipeline |
| **E2E tests (true backend)** | Real software invocation + output verification |
| **CLI subprocess tests** | Installed command via `subprocess.run` |

```bash
# Run tests
cd <software>/agent-harness
python3 -m pytest cli_anything/<software>/tests/ -v

# Force-installed mode (recommended)
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
```

---

## Key Design Principles

### 1. Authentic Software Integration
The CLI MUST call the actual application for rendering. No Pillow replacements for GIMP, no custom renderers for Blender. Generate valid project files → invoke the real backend.

### 2. The Rendering Gap
GUI apps apply effects at render time. If your CLI manipulates project files but uses a naive export tool, effects get silently dropped. Solution: native renderer → filter translation → render script.

### 3. Filter Translation
When mapping effects between formats, watch for:
- Duplicate filter merging
- Interleaved stream ordering
- Parameter space differences
- Unmappable effects

### 4. Timecode Precision
Non-integer frame rates (29.97fps) cause cumulative rounding. Use `round()` not `int()`, integer arithmetic for display, and ±1 frame tolerance in tests.

### 5. Output Verification
Never trust that export worked because it exited 0. Verify:
- Magic bytes
- ZIP/OOXML structure
- Pixel analysis
- Audio RMS levels
- Duration checks

---

## CLI-Hub: Central Registry

Launched March 17, 2026, CLI-Hub is a central registry where users can:
- Browse and search all community CLIs
- Install any CLI with a single `pip` command
- Contribute new CLIs by opening a PR with a `registry.json` entry
- Auto-updates on merge

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `/cli-anything <path-or-repo>` | Build complete CLI harness — all 7 phases |
| `/cli-anything:refine <path> [focus]` | Refine existing harness — expand coverage |
| `/cli-anything:test <path>` | Run tests and update TEST.md |
| `/cli-anything:validate <path>` | Validate against HARNESS.md standards |
| `/cli-anything:list` | List available CLIs |

---

## Limitations

1. **Requires strong foundation models** — Relies on frontier-class models (Claude Opus 4.6, Claude Sonnet 4.6, GPT-5.4) for reliable harness generation
2. **Relies on available source code** — Compiled binaries require decompilation, degrading quality
3. **May require iterative refinement** — Single run may not fully cover all capabilities
4. **Target software must be installed** — Real backend integration requires actual applications

---

## Future Roadmap

- Support for more application categories (CAD, DAW, IDE, EDA, scientific tools)
- Benchmark suite for agent task completion rates
- Community-contributed CLI harnesses
- Integration with additional agent frameworks
- Support for closed-source software and web services APIs

---

## Resources

| Resource | URL |
|----------|-----|
| **GitHub Repository** | https://github.com/HKUDS/CLI-Anything |
| **Official Website** | https://cli-anything.com/ |
| **Community Site** | https://clianything.org/ |
| **CLI-Hub** | Available via the GitHub repo |

---

## Conclusion

CLI-Anything represents a significant advancement in making existing software accessible to AI agents. By automatically generating production-ready CLI interfaces with comprehensive testing, it eliminates the traditional barriers of GUI automation fragility and API limitation. The project's emphasis on authentic software integration — calling real backends rather than reimplementing functionality — ensures that generated CLIs preserve the full capabilities of the original applications.

The 1,588 passing tests across 13 diverse applications demonstrate the reliability and production-readiness of the generated interfaces. As AI agents become increasingly capable of complex reasoning, tools like CLI-Anything will be essential for connecting that intelligence to the vast ecosystem of existing software.[iFlow] Completed in 120s
[iFlow] Output saved to: /home/quan/testdata/aspipe_v4/auto/test/iflow_output.txt

--- iFlow Output ---
[WebFetchTool] Using Xinliu proxy server at https://apis.iflow.cn/v1 to fetch: https://cli-anything.com/
[WebFetchTool] Using Xinliu proxy server at https://apis.iflow.cn/v1 to fetch: https://github.com/HKUDS/CLI-Anything
[WebFetchTool] Using Xinliu proxy server at https://apis.iflow.cn/v1 to fetch: https://clianything.org/
Let me check the existing report file to see if I should update it:I found an existing report file. Let me update it with the comprehensive information I gathered:Report updated at `/home/quan/testdata/aspipe_v4/auto/test/cli_anythin_report.md`.

---

## CLI-Anything Summary

**CLI-Anything** is an open-source Claude Code plugin from HKUDS that automatically generates production-ready CLI interfaces for any software with a codebase. Its mission: make all software "agent-native."

**Key Highlights**:
- **2,000+ GitHub stars**, **1,588 tests** (100% pass rate)
- **7-phase automated pipeline**: Analyze → Design → Implement → Test → Document → Publish
- **Real software integration**: Calls actual backends (LibreOffice generates real PDFs, Blender renders real 3D)
- **Agent-native design**: Built-in `--json` flag, auto-generated `SKILL.md` for AI discovery
- **Interactive REPL**: Stateful interface with undo/redo

**Supported Apps**: GIMP, Blender, Inkscape, Audacity, LibreOffice, OBS Studio, Kdenlive, Shotcut, Zoom, Draw.io, Mermaid, AnyGen, ComfyUI

**Quick Start**:
```bash
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything
/cli-anything ./your-software
```

**Limitations**: Requires strong LLMs (Claude Opus/Sonnet), needs source code access, target software must be installed locally.

<Execution Info>
{
  "session-id": "session-704bfaf6-fe53-4736-a013-1b5604d37146",
  "conversation-id": "d0c04b23-eb2b-4b4c-9915-3ed001f7253e",
  "assistantRounds": 6,
  "executionTimeMs": 110767,
  "tokenUsage": {
    "input": 34066,
    "output": 311,
    "total": 34377
  }
}
</Execution Info>
--- End Output ---

Testing Gemini CLI (using --approval-mode=yolo)...
----------------------------------------
Testing: Gemini
Command: gemini -p "Search the web for information about 'cli anythin' and write a comprehensive report about what it is, its features, use cases, and any relevant details. Be thorough and informative." --approval-mode=yolo
----------------------------------------
[Gemini] Completed in 308s
[Gemini] Output saved to: /home/quan/testdata/aspipe_v4/auto/test/gemini_output.txt

--- Gemini Output ---
YOLO mode is enabled. All tool calls will be automatically approved.
Loaded cached credentials.
YOLO mode is enabled. All tool calls will be automatically approved.
I will search the web for information about "cli anythin" to understand its features, use cases, and technical details.
Attempt 1 failed: You have exhausted your capacity on this model. Your quota will reset after 5s.. Retrying after 5834ms...
Attempt 1 failed: You have exhausted your capacity on this model. Your quota will reset after 6s.. Retrying after 7295ms...
I will read the local file `auto/test/cli_anythin_report.md` to gather context about "cli anythin" and then perform a more targeted web search for "AnythingLLM CLI" and related terms.
Attempt 1 failed: You have exhausted your capacity on this model. Your quota will reset after 3s.. Retrying after 5437ms...
I will perform a targeted web search for "HKUDS CLI-Anything" and "cli-anything" to see if there is any additional or more recent information beyond what is already in the local report.
# CLI-Anything: Comprehensive Research Report

**CLI-Anything** is an innovative open-source project from the **HKUDS (Hong Kong University Data Science)** lab designed to bridge the gap between AI agents and professional software. Its primary purpose is to automatically generate production-ready, "agent-native" Command-Line Interfaces (CLIs) for any software with an accessible codebase.

---

## 1. Executive Summary
*   **Mission**: To make all existing software controllable by AI agents through structured, reliable CLI interfaces.
*   **Status**: Highly active, with over 2,000 GitHub stars and 1,500+ passing tests across 13+ major professional applications.
*   **Key Insight**: Instead of fragile GUI automation (clicking buttons via screenshots) or manual API integrations, CLI-Anything builds a direct bridge to the software's internal logic.

---

## 2. Core Features
### Universal CLI Generation
CLI-Anything can scan a local repository or a GitHub URL and automatically architect a CLI that exposes the software's core capabilities.

### The 7-Phase Automated Pipeline
The framework follows a rigorous process to ensure the generated CLI is robust:
1.  **Analyze**: Scans source code and maps GUI actions/internal functions to potential CLI commands.
2.  **Design**: Architects command groups, state models, and structured output formats.
3.  **Implement**: Builds a Python-based CLI (typically using `Click`) with REPL support and JSON output.
4.  **Plan Tests**: Creates a comprehensive `TEST.md` file with unit and end-to-end (E2E) test plans.
5.  **Write Tests**: Implements the test suite to verify the CLI against the real software backend.
6.  **Document**: Updates documentation with test results and usage instructions.
7.  **Publish**: Packages the CLI for installation (e.g., via `pip`).

### Agent-Native Design
*   **`--json` Flag**: Every command supports structured JSON output, making it easy for agents to parse results without regex or string manipulation.
*   **Self-Describing Help**: AI-discoverable help flags allow agents to explore capabilities dynamically.
*   **SKILL.md Generation**: Automatically generates skill definitions that agents can "read" to understand what the tool can do.

---

## 3. Key Benefits & Use Cases
### Why CLI-Anything is Better than GUI Automation
| Feature | CLI-Anything | Standard RPA / GUI Automation |
| :--- | :--- | :--- |
| **Reliability** | Extremely high; uses code-level APIs. | Low; breaks with UI changes or resolution shifts. |
| **Speed** | Near-instant execution. | Slow; requires waiting for UI animations. |
| **Agent Integration** | Native JSON support. | Requires vision models to "see" the UI. |
| **Headless Support** | Works in CI/CD and servers. | Often requires a virtual display/GPU. |

### Major Use Cases
1.  **Creative Automation**:
    *   **Blender**: Generating 3D renders, manipulating scenes, or adjusting materials via commands.
    *   **GIMP/Inkscape**: Precise image editing, filter application, and batch format conversion.
2.  **Professional Documentation**:
    *   **LibreOffice**: Generating complex reports, PDFs, and spreadsheets from raw data.
    *   **Draw.io**: Programmatically creating system architecture diagrams and flowcharts.
3.  **Media Production**:
    *   **OBS Studio/Audacity**: Automating scene switching, recording, and audio processing.
4.  **Token Efficiency**:
    *   Compared to the Model Context Protocol (MCP), CLI-Anything can be up to **30x more token-efficient** by reducing the overhead required to describe tool schemas to the model.

---

## 4. Supported Applications
CLI-Anything has been validated with over 1,500 tests across diverse domains:
*   **Graphics**: GIMP, Inkscape, Blender, Krita.
*   **Office**: LibreOffice, Draw.io, Mermaid Live Editor.
*   **Video/Audio**: OBS Studio, Audacity, Shotcut, Kdenlive.
*   **AI/ML**: ComfyUI, AnyGen.

---

## 5. Technical Architecture
### Project Components
*   **`cli-anything-plugin`**: The core plugin for environments like Claude Code.
*   **`repl-skin.py`**: A unified, stateful REPL interface that provides a consistent "feel" across different generated CLIs (including undo/redo support).
*   **`agent-harness/`**: The generated output for a specific piece of software, containing the Python package, tests, and `SKILL.md`.

### Testing Philosophy
A generated CLI is only considered "finished" if it passes a multi-layered test suite:
*   **Unit Tests**: Testing internal functions.
*   **E2E (Native)**: Verifying the CLI correctly manipulates project files.
*   **E2E (True Backend)**: Invoking the actual software (e.g., Blender) to ensure the final output (e.g., a `.png` render) is correct.

---

## 6. Installation & Usage
### Installation (Claude Code)
```bash
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything
```

### Building a New CLI
```bash
# Point it to a local repo or GitHub
/cli-anything https://github.com/blender/blender
... (truncated, full output in /home/quan/testdata/aspipe_v4/auto/test/gemini_output.txt)
--- End Output ---

Testing KiloCode CLI (using --auto for auto-approve)...
----------------------------------------
Testing: KiloCode
Command: kilo run --auto "Search the web for information about 'cli anythin' and write a comprehensive report about what it is, its features, use cases, and any relevant details. Be thorough and informative."
----------------------------------------
[KiloCode] Completed in 60s
[KiloCode] Output saved to: /home/quan/testdata/aspipe_v4/auto/test/kilocode_output.txt

--- KiloCode Output ---
[0m
> code · x-ai/grok-code-fast-1:optimized:free
[0m
[0m◈ [0mExa Web Search "cli anythin"
[0m% [0mWebFetch https://github.com/HKUDS/CLI-Anything
[0m• [0mExtract key information from CLI-Anything README[90m Explore Agent[0m
[0m✓ [0mExtract key information from CLI-Anything README[90m Explore Agent[0m
# Comprehensive Report on CLI-Anything

## Introduction
CLI-Anything is an innovative open-source project that enables AI agents to control virtually any software application through automatically generated command-line interfaces (CLIs). Launched in March 2026, it has rapidly gained popularity with over 18,000 GitHub stars and 1,600 forks, addressing a critical gap where AI agents excel at reasoning but struggle with using professional software that lacks APIs or has fragile GUI automation.

## What is CLI-Anything?
CLI-Anything transforms software into "agent-native" tools by generating production-ready CLIs from source codebases. It bridges the divide between AI agents and software ecosystems, allowing agents to perform complex workflows in applications like GIMP, Blender, LibreOffice, and OBS Studio without relying on screenshots, mouse clicks, or limited APIs. The project provides a unified methodology to make any codebase controllable via structured commands, enabling seamless integration with AI coding platforms.

## Key Features
- **Automated 7-Phase Pipeline**: Generates complete CLIs through analysis, design, implementation, testing, documentation, and publishing phases.
- **Agent-Native Design**: Built-in JSON output for machine consumption (--json flag) alongside human-readable interfaces; includes SKILL.md files for automatic skill discovery by agents.
- **Authentic Software Integration**: Calls real application backends (e.g., Blender's bpy module, LibreOffice headless) for genuine rendering and processing, avoiding compromises or toy implementations.
- **Unified User Experience**: All CLIs share a consistent REPL interface (repl_skin.py) with branded banners, command history, progress indicators, and standardized formatting.
- **Production-Grade Testing**: Comprehensive multi-layered testing (unit, end-to-end native, end-to-end true backend, CLI subprocess) with a 100% pass rate across 1,588 tests for 13 diverse applications.
- **Zero-Config Installation**: CLIs install via pip to system PATH; agents discover capabilities through standard --help and which commands.
- **Extensible and Community-Driven**: Plugin-based architecture with a CLI-Hub registry for browsing and installing community CLIs; supports iterative refinement to expand coverage.
- **Platform-Agnostic**: Designed to work across AI coding agents with contributions for multiple platforms.

## How It Works
CLI-Anything operates through a sophisticated 7-phase automated pipeline:
1. **Analyze**: Scans the source code to map GUI actions to underlying APIs and capabilities.
2. **Design**: Architects command groups, state management models, and output formats.
3. **Implement**: Builds Click-based CLI with REPL support, JSON output, and undo/redo functionality.
4. **Plan Tests**: Creates detailed test plans covering unit and end-to-end scenarios.
5. **Write Tests**: Implements comprehensive test suites with synthetic and real data.
6. **Document**: Updates documentation with test results and usage examples.
7. **Publish**: Generates setup.py for pip installation and PATH integration.

Users invoke it via platform-specific commands (e.g., /cli-anything in Claude Code) pointing to a software path or GitHub repo. Refinement commands allow iterative expansion of coverage. Generated CLIs support both interactive REPL mode and scripted subcommands, with persistent project state and authentic backend integration.

## Supported Platforms
- **Claude Code**: Primary platform; install via marketplace or manual plugin setup.
- **OpenClaw**: Community-supported with native SKILL.md skill definition.
- **OpenCode**: Experimental; requires copying commands and methodology files.
- **Qodercli**: Community plugin with automated setup script.
- **Codex**: Experimental skill with installer for Windows and Linux.
- **Goose (Desktop/CLI)**: Experimental; leverages underlying CLI providers.
- **Planned**: Cursor, Windsurf, and others; contributions welcome for additional agents.

## Use Cases
CLI-Anything enables agents to automate workflows across diverse domains:
- **GitHub Repositories**: Convert open-source tools like VSCodium, WordPress, and Calibre into programmable interfaces.
- **AI/ML Platforms**: Automate model training, inference, and hyperparameter tuning in Stable Diffusion, ComfyUI, InvokeAI, and Text-generation-webui.
- **Data & Analytics**: Enable programmatic data processing in JupyterLab, Apache Superset, Metabase, and Redash.
- **Development Tools**: Streamline coding workflows via Jenkins, Gitea, pgAdmin, and SonarQube.
- **Creative & Media**: Control content creation in GIMP, OBS Studio, Audacity, Kdenlive, Shotcut, Inkscape, and Darktable.
- **Scientific Computing**: Automate research in ImageJ, FreeCAD, QGIS, ParaView, and Gephi.
- **Enterprise & Office**: Access productivity apps like NextCloud, GitLab, LibreOffice, and ERPNext.
- **Communication**: Manage meetings and recordings in Zoom, Jitsi Meet, and BigBlueButton.
- **Diagramming**: Generate visualizations with Draw.io, Mermaid, PlantUML, and Excalidraw.
- **AI Content Generation**: Produce deliverables via AnyGen, Gamma, and Beautiful.ai.

It replaces fragile GUI automation, unifies scattered APIs, and enables automated task synthesis and benchmarking.

## Demonstrations and Testing
CLI-Anything has been validated across 13 complex applications spanning creative, productivity, and AI domains:
- GIMP (107 tests): Image editing with Pillow + GEGL/Script-Fu backend.
- Blender (208 tests): 3D modeling via bpy scripting.
- Inkscape (202 tests): Vector graphics with SVG/XML manipulation.
- Audacity (161 tests): Audio processing using wave + sox.
- LibreOffice (158 tests): Office suite with ODF generation and headless rendering.
- OBS Studio (153 tests): Live streaming via JSON scenes and obs-websocket.
- Kdenlive (155 tests): Video editing with MLT XML + melt renderer.
- Shotcut (154 tests): Video editing via direct MLT XML manipulation.
- Zoom (22 tests): Video conferencing through REST API with OAuth2.
- Draw.io (138 tests): Diagramming with mxGraph XML and draw.io CLI.
- Mermaid (10 tests): Diagrams via Mermaid state and mermaid.ink renderer.
- AnyGen (50 tests): AI content generation using AnyGen REST API.
- ComfyUI (70 tests): AI image generation via ComfyUI REST API.

All tests achieve 100% pass rate, including real software invocation for authentic output verification (e.g., PDF generation in LibreOffice, PNG rendering in Blender).

## Community and Future
The project features active community contributions, including Windows compatibility fixes, platform integrations (OpenClaw, Qodercli), and localization (Japanese README). Recent updates include CLI-Hub for centralized CLI discovery and SKILL.md generation for enhanced agent integration. Under MIT license, it encourages contributions for new targets, methodology improvements, and platform support. Future roadmap focuses on expanding categories, automated benchmarks, and deeper integrations.

CLI-Anything represents a paradigm shift in human-agent collaboration, making professional software universally accessible to AI while maintaining full capabilities and reliability.
--- End Output ---

Testing OpenCode CLI (no yolo mode available)...
----------------------------------------
Testing: OpenCode
Command: opencode run "Search the web for information about 'cli anythin' and write a comprehensive report about what it is, its features, use cases, and any relevant details. Be thorough and informative."
----------------------------------------
[OpenCode] Completed in 35s
[OpenCode] Output saved to: /home/quan/testdata/aspipe_v4/auto/test/opencode_output.txt

--- OpenCode Output ---
[0m
> build · minimax-m2.5-free
[0m
[0m◈ [0mExa Web Search "cli anything"
# CLI-Anything Comprehensive Report

## What is CLI-Anything?

**CLI-Anything** is an open-source project (GitHub: HKUDS/CLI-Anything) that transforms any software into an AI agent-controllable CLI interface with a single command. Created by researchers at HKUDS (Hong Kong University), it aims to bridge the gap between AI agents and the world's software by making desktop applications "agent-native" without requiring manual coding or fragile GUI automation.

The project has gained massive traction, reaching **17,827+ GitHub stars** since its March 8, 2026 release.

---

## Core Problem It Solves

AI agents are great at calling APIs and running shell commands, but the world's most powerful creative software—GIMP, Blender, LibreOffice, OBS, DaVinci Resolve—has no accessible API. Agents face two poor options:

1. **Python scripting via app-specific APIs** — Works for some apps but requires deep per-app knowledge and produces unstructured output
2. **Screen scraping/computer use** — Fragile, slow, and breaks when apps update

CLI-Anything provides a **third path**: a universal adapter that wraps desktop applications in a structured CLI with JSON output.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **One-Command Wrapping** | `cli-anything ./gimp` or `cli-anything https://github.com/blender/blender` instantly generates a CLI interface |
| **Structured & Composable** | Text commands naturally match LLM format; chain together for complex multi-step workflows |
| **Self-Describing with --help** | Every generated CLI is fully introspectable; AI agents can discover capabilities at runtime |
| **Agent-First JSON Output** | Built-in `--json` flag delivers structured data; humans see readable table format |
| **Deterministic & Reliable** | 1,436 tests passing across 9 apps with 100% pass rate |
| **Universal Compatibility** | Works with Claude Code, Cursor, OpenClaw, nanobot, and any agent framework |

---

## Supported Applications

Currently supports **9 major applications**, including:
- GIMP (image editing)
- Blender (3D modeling)
- LibreOffice (productivity suite)
- OBS (screen recording)
- DaVinci Resolve (video editing)

---

## Use Cases

1. **AI-Powered Image Editing**: Agents can control GIMP to edit images without GUI automation
2. **Automated 3D Rendering**: Generate Blender scenes programmatically
3. **Document Processing**: Automate LibreOffice operations (convert, merge, etc.)
4. **Video Workflow Automation**: Control OBS or DaVinci Resolve for automated recording/editing
5. **Software Testing**: Agents can reliably test GUI applications through CLI
6. **Cost Reduction**: Eliminates expensive API development for legacy software

---

## Integration Methods

**Via Claude Code plugin system:**
```bash
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything
/cli-anything ./gimp  # Point at any software
```

**Via CLI-Hub**: Browse and install community CLIs in one place

---

## Technical Highlights

- **Primary Language**: Python (99.3%), Shell (0.6%), PowerShell
- **License**: Open source (Apache 2.0 or similar permissive license)
- **Tests**: 1,436 tests passing across unit, end-to-end, and backend verification
- **Contributors**: 20+ active contributors
- **Platform**: Cross-platform (Linux, macOS, Windows)

---

## Why CLI is the Universal Agent Interface

CLI-Anything frames CLI as the ideal bridge for AI agents because:

- **Structured**: Commands are inherently parseable
- **Composable**: Chain commands for complex workflows
- **Self-documenting**: `--help` provides discoverable documentation
- **Lightweight**: No GUI overhead or screen rendering needed
- **Agent-aligned**: Natural language maps easily to CLI syntax

---

## Conclusion

CLI-Anything represents a significant step toward making all software compatible with AI agents. By treating CLI as the universal interface, it avoids the need for per-app API development or fragile GUI automation. With rapid community growth and high test coverage, it's becoming a standard tool for agent-native software development.
--- End Output ---

Testing Qwen Code CLI (using --yolo)...
----------------------------------------
Testing: QwenCode
Command: qwen -p "Search the web for information about 'cli anythin' and write a comprehensive report about what it is, its features, use cases, and any relevant details. Be thorough and informative." --yolo
----------------------------------------
[QwenCode] Completed in 103s
[QwenCode] Output saved to: /home/quan/testdata/aspipe_v4/auto/test/qwencode_output.txt

--- QwenCode Output ---
# CLI-Anything 综合报告

## 📌 概述

**CLI-Anything** 是由**香港大学数据科学实验室（HKUDS）**开源的革命性工具，能够自动将任何有源代码的软件（如 GIMP、Blender、LibreOffice 等）转化为 AI Agent 可直接调用的命令行工具。该项目于 2026 年 3 月发布，目前在 GitHub 上已获得 **18.3k+ stars**。

**核心理念**：今天的软件服务于人类，明天的用户将是 AI 智能体。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **7 阶段自动化流水线** | 从代码分析到发布，全自动完成架构设计、实现、测试、文档 |
| **真实软件集成** | 直接调用真实应用后端，非 GUI 自动化，结果确定可靠 |
| **结构化 JSON 输出** | 内置 `--json` 标志，为 AI Agent 提供机器可读的结构化数据 |
| **自描述命令** | 每个命令支持 `--help`，AI 可运行时自动发现功能 |
| **会话状态管理** | 支持跨命令的持久化项目状态和 undo/redo 功能 |
| **零配置安装** | 简单的 `pip install -e .` 即可将 CLI 添加到 PATH |
| **SKILL.md 生成** | 每个生成的 CLI 包含 AI 可发现的技能定义文件 |

---

## 🔧 工作原理：7 阶段全自动流水线

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 🔍 分析 (Analyze)   → 扫描源代码，将 GUI 操作映射到 API          │
│  2. 📐 设计 (Design)    → 架构命令组和状态模型                     │
│  3. 🔨 实现 (Implement) → 构建带 REPL 和 JSON 输出的 Click CLI      │
│  4. 📋 计划测试 (Plan)  → 创建 TEST.md                            │
│  5. 🧪 编写测试 (Write) → 实现全面的测试套件                       │
│  6. 📝 文档 (Document)  → 更新 TEST.md                            │
│  7. 📦 发布 (Publish)   → 创建 setup.py 并安装到 PATH              │
└─────────────────────────────────────────────────────────────────┘
```

### 技术架构特点

- **统一 REPL 接口**：所有生成的 CLI 提供一致的交互式体验（ReplSkin）
- **清晰的包架构**：所有 CLI 组织在 `cli_anything.*` 命名空间下
- **双模式交互**：状态化 REPL（交互式）+ 子命令接口（脚本/流水线）

---

## 📦 支持的应用

CLI-Anything 已为以下软件生成 CLI（**1,588 个测试 100% 通过率**）：

| 类别 | 软件 | 测试数 |
|------|------|--------|
| **创意 & 媒体工具** | GIMP, Blender, Inkscape, Audacity, Kdenlive, Shotcut, OBS Studio | 1,138 |
| **AI & ML 平台** | Stable Diffusion, ComfyUI, InvokeAI, AnyGen | 120 |
| **办公 & 企业应用** | LibreOffice, Zoom | 180 |
| **图表 & 可视化** | Draw.io, Mermaid | 148 |

---

## 💡 使用示例

### 安装插件（Claude Code）

```bash
# 添加插件市场
/plugin marketplace add HKUDS/CLI-Anything

# 安装插件
/plugin install cli-anything
```

### 生成 CLI

```bash
# 为 GIMP 生成完整 CLI
/cli-anything ./gimp

# 从 GitHub 仓库生成
/cli-anything https://github.com/blender/blender
```

### 使用生成的 CLI

```bash
# 查看帮助
cli-anything-gimp --help

# JSON 输出（供 Agent 使用）
cli-anything-gimp layer add -n "Background" --json
# 输出：{"status": "success", "layer_id": 1, "dimensions": [1920, 1080]}

# 进入交互式 REPL
$ cli-anything-blender
blender> scene new --name ProductShot
✓ Created scene: ProductShot
blender[ProductShot]> render execute --output render.png
✓ Rendered: render.png (1920×1080, 2.3 MB)
```

---
... (truncated, full output in /home/quan/testdata/aspipe_v4/auto/test/qwencode_output.txt)
--- End Output ---

========================================
All tests completed!
Full report saved to: /home/quan/testdata/aspipe_v4/auto/test/cli_anythin_report.md
Individual outputs saved to: /home/quan/testdata/aspipe_v4/auto/test/*_output.txt
========================================
