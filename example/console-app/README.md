# Console Application Example

This is a lightweight, console-only application built using the `fastapi-startkit` framework. It demonstrates how to leverage the framework's core features—such as service providers, dependency injection, and logging—to build robust command-line interfaces.

## Project Structure

- **`artisan`**: The main entry point for the CLI application.
- **`bootstrap/application.py`**: Initializes the `Application` container and registers service providers.
- **`commands/`**: Contains the application's CLI command definitions (built with [Cleo](https://github.com/python-cleo/cleo)).
- **`providers/`**: Service providers responsible for registering commands and services into the application container.
- **`config/`**: Configuration files for various components like logging.

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### Running Commands

The application provides a `hello` command as an example. You can run it using the `artisan` script:

```bash
# Basic usage
uv run python artisan hello

# With an argument
uv run python artisan hello "John Doe"
```

### Creating New Commands

1.  Create a new command class in `commands/`.
2.  Register the command in `providers/console.py` (within the `ConsoleServiceProvider`).

## Features

- **Built-in Logging**: Easily log messages with different levels (info, emergency, etc.) using `Log`.
- **Framework Integration**: Uses the same `Application` container as FastAPI-based projects, allowing for easy sharing of services and logic.
