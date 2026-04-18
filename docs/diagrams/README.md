# C4 Architecture Diagrams

[C4 model](https://c4model.com/) architecture diagrams for Moon Traveler Terminal. All files are in Excalidraw format.

## How to open

- **Web:** Open at [excalidraw.com](https://excalidraw.com) (File > Open)
- **VS Code:** Install the [Excalidraw extension](https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor)

## Diagrams

### Level 1 — System Context
`c4-system-context.excalidraw` — The game and its external dependencies (Player, LLM, SQLite, HuggingFace, OS Sound)

### Level 2 — Container
`c4-container.excalidraw` — Major containers: Entry Points, UI Layer, Game Engine (center), AI/Creature, Player/Companions, Persistence

### Level 3 — Component (one per container)

| File | Container | Key Components |
|------|-----------|----------------|
| `c4-component-tui.excalidraw` | TUI & UI | MoonTravelerApp, UIBridge, GameSuggester, queues, _BridgeConsoleShim |
| `c4-component-game-engine.excalidraw` | Game Engine | GameContext, dispatch, 25+ handlers, world, difficulty, win/lose |
| `c4-component-ai-creature.excalidraw` | AI & Creature | LLM pipeline, memory system, trust thresholds, security layers |
| `c4-component-player.excalidraw` | Player & Companions | Player vitals, Drone upgrades, ShipAI ARIA |
| `c4-component-persistence.excalidraw` | Persistence | SQLite schema, config, model files, auto-save |
