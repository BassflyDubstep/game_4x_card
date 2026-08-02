#pragma once

#include "Libraries.h"
#include "Aliases.h"

class Logger {
public:
    enum class Level {
        Info,
        Warning,
        Error
    };

    // Log a message with the specified level.
    static void log(Level level, StringView message);

    // Log an info message.
    static void info(StringView message);

    // Log a warning message.
    static void warning(StringView message);

    // Log an error message.
    static void error(StringView message);
};
