// Logger.cpp
#include "Logger.h"

void Logger::log(Level level, StringView message) {
    String prefix;
    switch (level) {
        case Level::Info:
            prefix = "[INFO] ";
            break;
        case Level::Warning:
            prefix = "[WARNING] ";
            break;
        case Level::Error:
            prefix = "[ERROR] ";
            break;
    }
    std::cout << prefix << message << "\n";
}

void Logger::info(StringView message) {
    log(Level::Info, message);
}

void Logger::warning(StringView message) {
    log(Level::Warning, message);
}

void Logger::error(StringView message) {
    log(Level::Error, message);
}
