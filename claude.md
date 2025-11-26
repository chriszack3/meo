# MEO - Markdown Edit Orchestrator

TUI tool for structured markdown editing. Generates AI-consumable edit instructions.

## Workflow
1. Run `meo` → file picker TUI shows .md files from configured folder
2. Select file → (next phase: chunk editing)
3. Directions TUI: assign action presets (expand/condense/clarify/etc) + annotations
4. Generate output.md: plain-language instructions for any AI

## Key Abstractions
- **Chunk**: Text range + category + direction + annotation
- **Direction**: Preset (expand/condense/clarify/restructure/simplify) + optional custom annotation
- **Sidecar**: `.meo.yaml` stores all chunk definitions

## Project Layout
- `src/meo/models/` - Pydantic models (Chunk, Direction, ProjectState)
- `src/meo/tui/` - Textual screens (selection, directions)
- `src/meo/core/` - Output generator, sidecar I/O
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

## Output Format
Each task in output.md has: category, direction, text to edit, instructions.
Tasks are sequential. Currently all chunks are edited in isolation (no cross-chunk context).
