# Style Guide

## General
- Unless otherwise specified, the language to use is C++20. Use modern C++ idioms and features where appropriate.
- Pointers are to be memory-safe; prefer `std::unique_ptr<T>` and `std::make_unique<T>(...)` for ownership, and avoid raw `new`/`delete` in new or refactored code.

## Comments
- Keep comments concise, usually one line; use multiline only for complex logic.
- Avoid use of emoticons or other non-standard symbols in comments.
- Use the U.S. English spelling of words in comments, e.g., "color" instead of "colour", "initialize" instead of "initialise", etc.
- Keep comments to one grouping of logic. In other words, it's OK to put a block of comments for "Initialization" at the top of a function, but don't put comments for each line of code in that block. Keep comments to a loop or nested loop. Some examples in backticks below.

Example 1 (basic initialization):
```
int main() {
    // Initialization.
    int x = 0;
    int y = 0;

    // Loop through values.
    for (int i = 0; i < 10; ++i) {
        x += i;
        y += i * 2;
    }

    return 0;
}  
```
Example 2 (nested loop over a 2D array):
```
int main() {
    // Initialize a 2D array.
    int arr[3][3] = { {1, 2, 3}, {4, 5, 6}, {7, 8, 9} };

    // Loop through the array and print each element.
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            std::cout << arr[i][j] << " ";
        }
        std::cout << std::endl;
    }

    return 0;
}
```

## Naming Conventions
- Use `snake_case` for variable names and function names, and `PascalCase` for class names.
- Function names need to be descriptive and indicate their purpose. A typical format is `verb_noun`, e.g., `calculate_area`, `get_user_input`, `process_data`, or `verb_noun_action`, e.g., `calculate_area_async`, `get_user_input_sync`, `process_data_in_background`. Do not use generic names such as `handle_event`.
- Class names should be descriptive and indicate their purpose. A typical format is `Noun` or `NounAdjective`, e.g., `Game`, `Map`, `Unit`, `Civilization`, or `Logger`. Do not use generic names such as `Manager` or `Helper`.

### Aliases
- Use `using` to create type aliases for complex types, e.g., `using TilePtr = std::unique_ptr<Tile>;`. This improves readability and maintainability of the code.
- Place aliases in a separate header file, e.g., `Aliases.h`, and include it where needed. Avoid placing aliases in implementation files unless they are local to that file.

### Global Constants
- Use `constexpr` for global constants, e.g., `constexpr int MAX_PLAYERS = 8;`. This allows the compiler to optimize the code and ensures that the value is known at compile time.

## Repository Structure
- Repository structure is typical for a C++ project. The `src/` directory contains the core game classes. Keep the structure organized and avoid unnecessary nesting of directories.
- Prefer to use `CMake` for building and testing. Update the `CMakeLists.txt` file as needed to include new source files or tests.

## Class Structure
- Prefer to use header files (`.h`) for class declarations and implementation files (`.cpp`) for class definitions. Keep the class interface in the header file and the implementation in the source file. Avoid putting implementation code in header files unless it is a template class or inline function.
- Use `#pragma once` in header files to prevent multiple inclusions.

## Examples
- The below is a very basic example of implementation of main().
```
// main.cpp
#include "Libraries.h"

int main() {
    // Initialization.
    Game game;

    // Main game loop.
    while (game.is_running()) {
        game.process_input();
        game.update();
        game.render();
    }

    return 0;
}
```

- The below is a very basic example of implementation of a class.
```
// Game.h
#pragma once
#include "Libraries.h"
#include "Aliases.h"

class Game {
public:
    // Constructor
    Game();

    // Destructor
    ~Game();

    // Processes user input and events.
    void process_input();
    
    // Updates the game state.
    void update();
    
    // Renders the game.
    void render();
    
    // Returns true if the game is running, false otherwise.
    bool is_running() const;
}
```

```
// Game.cpp
#include "Game.h"

Game::Game() {
    // Initialization code.
}

// Additional methods implementation here...
```
