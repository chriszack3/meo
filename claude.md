# MEO - Markdown Edit Orchestrator

TUI tool for structured markdown editing. Generates AI-consumable edit instructions.

## Workflow
1. Selection TUI: mark chunks, assign categories (edit/change/tweak/leave)
2. Directions TUI: assign action presets (expand/condense/clarify/etc) + annotations
3. Generate output.md: plain-language instructions for any AI

## Key Abstractions
- **Chunk**: Text range + category + direction + annotation
- **Direction**: Preset (expand/condense/clarify/restructure/simplify) + optional custom annotation
- **Sidecar**: `.meo.yaml` stores all chunk definitions

## Project Layout
- `src/meo/models/` - Pydantic models (Chunk, Direction, ProjectState)
- `src/meo/tui/` - Textual screens (selection, directions)
- `src/meo/core/` - Output generator, sidecar I/O
- `src/meo/presets/` - Built-in direction presets

## CLI Commands
```bash
meo edit <file.md>           # Full TUI workflow
meo edit <file.md> --continue # Resume from sidecar
meo generate <file.md>        # Output without TUI
meo sidecar <file.md> show    # View sidecar
meo presets list              # List direction presets
```

## Output Format
Each task in output.md has: category, direction, text to edit, instructions.
Tasks are sequential. Currently all chunks are edited in isolation (no cross-chunk context).
