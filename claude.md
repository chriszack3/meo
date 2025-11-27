# MEO - Markdown Edit Orchestrator

TUI tool for AI-assisted markdown editing with atomic chunk processing and git-backed review.

## Quick Start

```bash
meo init         # Configure markdown folder (creates .meo/config.yaml)
meo              # Launch the TUI
```

## Workflow

MEO uses a unified screen with multiple modes:

```
EDITING → SELECTING_ACTION → SELECTING_DIRECTION/LOCK_TYPE → ANNOTATION → PROCESSING → REVIEWING
```

1. **Select text** - Use arrow keys + Shift to highlight text
2. **Press Enter** - Opens action selector
3. **Choose action** - Replace, Tweak, or Lock
4. **Choose direction/lock type** - Preset or context type
5. **Add annotation** - Optional custom guidance (Enter to skip)
6. **Press 'g'** - Generate session and process with Claude
7. **Review** - Approve or deny each AI response

## Chunk Categories

| Category | Purpose | Direction Presets |
|----------|---------|-------------------|
| **REPLACE** | Complete rewrite | Richer, Tighter, Livelier, Calmer, Elevated, Grounded, Custom |
| **TWEAK** | Minor adjustments | Flow, Precision, Tone, Custom |
| **LOCK** | Context for AI (not edited) | N/A - uses Lock Types instead |

## Lock Types

Lock chunks provide context to AI without being edited:

| Type | Purpose |
|------|---------|
| **Example** | Match this style/format |
| **Reference** | Use this information |
| **Context** | Background awareness only |

## Key Controls

### Editing Mode
| Key | Action |
|-----|--------|
| Arrow keys | Navigate cursor |
| Shift+Arrow | Extend selection |
| Enter | Confirm selection / Start chunk creation |
| Escape | Cancel current operation |
| g | Generate session and start processing |
| d | Delete selected chunk |
| q | Quit |

### Review Mode
| Key | Action |
|-----|--------|
| Left/Right | Toggle between Approve/Deny |
| Up/Down | Navigate between chunks |
| Enter | Confirm current choice |
| e | Edit text in sidebar |

## CLI Commands

```bash
meo              # Launch file picker TUI
meo init         # Create .meo/config.yaml interactively
meo presets list # List available direction presets
meo sessions     # List all editing sessions with progress
```

## Session Structure

When you generate, MEO creates:

```
.meo/sessions/[filename]_[timestamp]/
  ├── session.yaml      # Session metadata
  ├── original.md       # Unmodified source
  ├── working.md        # Modified document (git tracked)
  ├── .git/             # Change history
  └── chunks/
      ├── chunk_001.md  # Atomic file with AI response
      └── chunk_002.md
```

## Atomic File Format

Each chunk becomes a self-contained file for AI processing:

```markdown
# Edit Task: chunk_001

**Category:** Replace

## Instructions
**Direction:** Richer
[Preset prompt template]
**User's additional guidance:** [annotation if provided]

## Document Structure
[Locked chunks appear here as context]

## Text to Edit
[Selected text to be rewritten]

## Your Response
[AI writes response here]
```

## Config

```yaml
# .meo/config.yaml
folder: /absolute/path/to/markdown/files
```

## Sidecar Files

Chunk definitions are stored alongside source files:

```
document.md           # Your markdown file
document.md.meo.yaml  # Chunk definitions (auto-managed)
```
