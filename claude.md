# MEO - Markdown Edit Orchestrator

TUI tool for structured markdown editing with orchestrated context control.

## Full Workflow

```
Selection → Directions → Generate → AI Edit → Review
```

1. **Selection TUI** - Mark chunks using arrows/shift/enter
2. **Directions TUI** - Assign presets + context visibility rules
3. **Generate** - Per-chunk atomic files (chunk + context + instructions)
4. **AI Edit** - External AI processes each atomic file
5. **Review TUI** - Git-based per-chunk diff approval/rejection

## Key Design Principles

- **Atomic outputs**: Each chunk → one self-contained file
- **Context control**: Chunks can see previous edits or surrounding "leave alone" chunks
- **Read vs Write**: Context is READ-ONLY, only chunk text gets rewritten
- **Git-backed**: Original state tracked, responses applied as patches

## Chunk Categories

- `edit` - Standard edit
- `change_entirely` - Complete rewrite
- `tweak_as_necessary` - Minor adjustments
- `leave_alone` - Context only (visible to other chunks but not edited)

## Context Visibility Modes (Step 2)

- `none` - Chunk edited in isolation
- `previous_edited` - See results of prior tasks
- `surrounding` - See adjacent "leave alone" chunks
- `full` - See entire document

## Selection Controls

- Arrow keys - Navigate cursor
- Shift+Arrow - Extend selection
- Enter - Mark chunk → select category → confirm
- Escape - Cancel pending chunk
- n - Next step (directions)

## Project Layout

- `src/meo/models/` - Pydantic models (Chunk, Direction, ProjectState)
- `src/meo/tui/` - Textual screens (selection, directions, review)
- `src/meo/core/` - Output generator, sidecar I/O, git integration
- `src/meo/presets/` - Built-in direction presets

## Config

Config file: `.meo/config.yaml` in current directory
```yaml
folder: /absolute/path/to/markdown/files
```

## CLI Commands

```bash
meo              # Launch file picker TUI (no arguments)
meo init         # Create .meo/config.yaml interactively
meo presets list # List direction presets
```
