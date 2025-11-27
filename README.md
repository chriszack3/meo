# MEO - Markdown Edit Orchestrator

A TUI application for structured AI-assisted markdown editing with atomic chunk processing.

## Tech Stack

- **TUI Framework**: [Textual](https://textual.textualize.io/)
- **CLI**: [Typer](https://typer.tiangolo.com/)
- **Data Validation**: [Pydantic](https://docs.pydantic.dev/)
- **AI Integration**: Claude CLI (`claude --print`)
- **Version Control**: Git (for session change tracking)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                          CLI (cli.py)                        │
│                    Entry point & commands                    │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      TUI Layer (tui/)                        │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ MeoApp      │  │ SelectionScreen  │  │ ProcessingScr  │  │
│  │ (app.py)    │  │ (unified screen) │  │ (processing)   │  │
│  └─────────────┘  └──────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Layer (core/)                       │
│  ┌──────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐  │
│  │ session  │ │ sidecar │ │ git_ops │ │ ai_edit_streaming│  │
│  └──────────┘ └─────────┘ └─────────┘ └──────────────────┘  │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐   │
│  │ chunk_parser   │ │text_replacer │ │ output_generator │   │
│  └────────────────┘ └──────────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Models Layer (models/)                    │
│  ┌───────┐ ┌─────────────┐ ┌─────────┐ ┌────────────────┐   │
│  │ Chunk │ │ProjectState │ │ Session │ │DirectionPreset │   │
│  └───────┘ └─────────────┘ └─────────┘ └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/meo/
├── __init__.py          # Version info
├── cli.py               # Typer CLI commands
├── models/              # Pydantic data models
│   ├── chunk.py         # Chunk, TextRange, Location, ChunkCategory, LockType
│   ├── config.py        # MeoConfig
│   ├── direction.py     # DirectionPreset
│   ├── project.py       # ProjectState
│   └── session.py       # Session
├── core/                # Business logic
│   ├── config.py        # Config file I/O
│   ├── sidecar.py       # ProjectState persistence (.meo.yaml files)
│   ├── session.py       # Session creation & management
│   ├── git_ops.py       # Git repository operations
│   ├── text_replacer.py # Find/replace in working.md
│   ├── chunk_parser.py  # Parse atomic chunk files
│   ├── ai_edit_streaming.py  # Claude CLI integration with streaming
│   └── output_generator.py   # Legacy batch output generation
├── tui/                 # Textual UI
│   ├── app.py           # MeoApp main application
│   ├── widgets.py       # Custom widgets (GenerateConfirmModal)
│   └── screens/
│       ├── file_picker.py   # File selection screen
│       ├── selection.py     # Main unified screen (editing + review)
│       ├── directions.py    # Legacy directions screen
│       ├── processing.py    # AI processing screen
│       └── review_v2.py     # Standalone review screen
└── presets/             # Built-in direction presets
    ├── __init__.py
    └── directions.py    # REPLACE_PRESETS, TWEAK_PRESETS
```

## Key Abstractions

### Chunk Model (`models/chunk.py`)

```python
class Chunk:
    id: str                          # e.g., "chunk_001"
    range: TextRange                 # Start/end location in source
    category: ChunkCategory          # REPLACE, TWEAK, or LOCK
    original_text: str               # Captured text
    direction_preset: Optional[str]  # Preset ID for REPLACE/TWEAK
    annotation: Optional[str]        # Custom user guidance
    lock_type: Optional[LockType]    # EXAMPLE, REFERENCE, CONTEXT (for LOCK)
    execution_order: int             # Processing order
```

### Session Lifecycle (`models/session.py`)

```
creating → generating → editing → reviewing → complete
```

- **creating**: Session ID generated, directory initialized
- **generating**: Atomic chunk files created
- **editing**: Claude processes chunks
- **reviewing**: User approves/rejects responses
- **complete**: All chunks decided

### SelectionScreen State Machine (`tui/screens/selection.py`)

```
EDITING
  │
  ├─[Enter]→ SELECTING_ACTION
  │            ├─[Lock]→ SELECTING_LOCK_TYPE → ENTERING_ANNOTATION
  │            └─[Replace/Tweak]→ SELECTING_DIRECTION → ENTERING_ANNOTATION
  │                                                           │
  │←─────────────────────────────────────────────────────────┘
  │
  ├─['g']→ PROCESSING → REVIEWING
  │                        ├─[←/→]→ toggle approve/deny
  │                        ├─[↑/↓]→ navigate chunks
  │                        ├─[Enter]→ confirm choice
  │                        └─['e']→ REVIEW_EDITING
  │
  └─['q']→ exit
```

## Data Persistence

### Sidecar Files

Chunk definitions stored alongside source files:

```
document.md              # Source file
document.md.meo.yaml     # ProjectState with chunks
```

### Session Directories

```
.meo/sessions/[source_stem]_[YYYYMMDD_HHMMSS]/
├── .git/              # Full git history
├── session.yaml       # Session metadata
├── original.md        # Unmodified source
├── working.md         # Current state (git tracked)
└── chunks/
    └── chunk_001.md   # Atomic file with AI response
```

## Core Module Responsibilities

| Module | Purpose |
|--------|---------|
| `sidecar.py` | Load/save ProjectState to YAML sidecar files |
| `session.py` | Create sessions, generate atomic files, manage session lifecycle |
| `git_ops.py` | Initialize repos, commit chunk responses, get diffs, rollback |
| `text_replacer.py` | Find and replace text in working.md with whitespace handling |
| `chunk_parser.py` | Extract metadata and AI responses from atomic chunk files |
| `ai_edit_streaming.py` | Run Claude CLI with streaming output, append responses |

## Entry Points

### CLI → TUI Flow

```
cli.py:main()
  └─ _run_file_picker()
       └─ FilePickerApp → FilePickerScreen
            └─ on select: _run_meo_app(path)
                 └─ MeoApp → SelectionScreen
```

### Processing Flow

```
SelectionScreen._start_processing()
  └─ create_session()         # Generate atomic files
  └─ _run_processing()        # Background worker
       └─ stream_ai_edit_on_session()
            └─ For each chunk: claude --print [chunk.md]
       └─ _processing_complete()
            └─ _load_review_data() → REVIEWING mode
```

## Atomic File Format

Generated in `session.py:generate_atomic_file()`:

```markdown
# Edit Task: chunk_001

**Category:** Replace

## Instructions
**Direction:** Richer
[Preset prompt template from presets/directions.py]

**User's additional guidance:** [annotation]

## Document Structure
[Locked chunks before/after target as context]
═══════════════════════════════════════════════════
**⬇ YOUR TEXT TO EDIT APPEARS BELOW ⬇**
═══════════════════════════════════════════════════

## Text to Edit
```
[original_text]
```

## Your Response
Write ONLY the edited text below...

---
[AI appends response after this marker]
```

## Adding a New Direction Preset

Edit `presets/directions.py`:

```python
DirectionPreset(
    id="my_preset",
    name="My Preset",
    description="Short description",
    prompt_template="Detailed instructions for AI..."
)
```

Add to `REPLACE_PRESETS` or `TWEAK_PRESETS` list.

## Testing

The codebase uses test documents in `test_docs/` for manual testing.

```bash
# Set up config pointing to test_docs
meo init
# Enter: /path/to/thinking/test_docs

# Launch TUI
meo
```
