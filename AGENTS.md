# AI Agent Entry: game_4x_agentic

## Purpose
- Minimal, actionable guidance for AI coding agents working on this 4X strategy game.

## Quick links
- Repository README: [README.md](README.md)
- Style notes: [STYLES.md](STYLES.md)
- Source files: `src/` (core C++ code)

## Build & test (common):
```bash
# configure a build directory and build (cross-platform)
cmake -S . -B build
cmake --build build --config Release
# run tests (if CTest configured)
cmake --build build --target RUN_TESTS
```

## Key conventions (short):
- Memory-safety: prefer `std::unique_ptr<T>`, `std::make_unique<T>(...)`, and RAII.
- Avoid raw `new`/`delete` in new or refactored code; prefer value semantics for small objects.
- Keep public APIs stable unless ownership changes require adjustments.
- Comments: concise, usually one line; use multiline only for complex logic.
- Keep refactors minimal and localized; do not redesign systems without asking.

## Where to focus
- `src/` contains core game classes
- `src/Libraries.h` functions as a header to include external libraries. If needing to add new external libraries to individual .h or .cpp files, prefer to add them to `src/Libraries.h` instead.
- `src/Aliases.h` contains type aliases for complex types. If needing to add new type aliases to individual .h or .cpp files, prefer to add them to `src/Aliases.h` instead.
- `src/Globals.h` contains global constants and variables. If needing to add new global constants or variables to individual .h or .cpp files, prefer to add them to `src/Globals.h` instead.

## How to act
- Act as a C++ memory-safety specialist and mentor.
- Preserve game behavior; prefer surgical ownership fixes (replace owning raw pointers with `unique_ptr`).
- When changing an API, provide a small migration note and update one example call site in `src/`.
- Ask for clarification before making broad architectural changes.

## Example prompts
- "Refactor `src` to replace owning `new`/`delete` patterns with `std::unique_ptr`."
- "Make `Map` own its `Tile` objects with `unique_ptr` while keeping public API stable."
- "Explain ownership for `Game` and recommend minimal changes to use RAII."

## Style Guide
- Guides on code style and conventions are in [STYLES.md](STYLES.md). Follow them for consistency.

## Notes
- Link to other documentation rather than copying it. Keep this file concise and actionable.
- If a change may affect many files, propose a short plan and get approval first.
