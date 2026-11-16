# uncomment

[![PyPI](https://img.shields.io/pypi/v/uncomment?style=flat-square&color=2dd4bf)](https://pypi.org/project/uncomment/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2dd4bf?style=flat-square)](https://github.com/polylint/uncomment/blob/main/LICENSE)

A blazing fast Rust-based command-line tool that removes comments from your source code. Perfect for cleaning up AI-generated code that comes with excessive explanations.

## Why Use This?

- 🚀 **Lightning Fast** - Built in Rust for maximum performance
- 🎯 **100% Accurate** - Never accidentally removes code that looks like comments
- 🛡️ **Safe by Default** - Preview changes before applying them
- 🌍 **Multi-language** - 49 built-in languages, 306 available via [tree-sitter-language-pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack)
- 🔧 **Self-contained** - Platform wheels ship the prebuilt binary; nothing is downloaded at install time

## Installation

```bash
pip install uncomment
```

### How the binary gets here

1. **Platform wheel (primary).** Each release publishes one wheel per platform with the
   prebuilt binary inside, so pip installs it with no further download (it works offline
   and in sandboxes) and the wheel hash pip verifies covers the binary:

   | Platform | Wheel tag |
   | --- | --- |
   | macOS (Apple silicon) | `macosx_11_0_arm64` |
   | macOS (Intel) | `macosx_10_12_x86_64` |
   | Linux arm64 (glibc 2.28+) | `manylinux_2_28_aarch64` |
   | Linux x64 (glibc 2.28+) | `manylinux_2_28_x86_64` |
   | Windows x64 | `win_amd64` |

2. **Download (fallback).** On any other host pip picks the pure-Python `py3-none-any`
   wheel, which carries no binary: the first run downloads the release archive for the
   host from GitHub into `~/.cache/uncomment/<version>/`. Set `UNCOMMENT_BINARY` to use a
   binary you already have. pip always prefers a matching platform wheel.

There is no source distribution.

## Quick Start

Remove comments from a single file:

```bash
uncomment main.py
```

Preview changes without modifying files:

```bash
uncomment --dry-run src/
```

Process all Python files in a directory:

```bash
uncomment "src/**/*.py"
```

## Key Features

### Smart Comment Detection

Unlike simple regex-based tools, `uncomment` understands your code's structure:

```python
# This comment will be removed
code = "# But this won't - it's in a string!"
```

### Preserves Important Comments

Keeps what matters:

- `TODO` and `FIXME` comments (configurable)
- License headers and copyright notices
- Linting directives (`# noqa`, `# type: ignore`, etc.)
- Docstrings (configurable)

### Perfect for Python Projects

- Handles all Python comment styles
- Preserves type hints and annotations
- Respects `# pylint:`, `# flake8:`, and other linter directives
- Works with `.py`, `.pyw`, `.pyi`, `.pyx`, and `.pxd` files

## Common Use Cases

**Clean up AI-generated code:**

```bash
uncomment generated_script.py
```

**Remove all comments including TODOs:**

```bash
uncomment --remove-todo --remove-fixme module.py
```

**Remove docstrings:**

```bash
uncomment --remove-doc api.py
```

**Process entire packages:**

```bash
uncomment my_package/
```

**Use multiple threads for large codebases:**

```bash
uncomment --threads 8 entire_project/
```

## Supported Languages

While this tool works great for Python, it also supports:
49 built-in languages including JavaScript, TypeScript, Rust, Go, Java, C/C++, Ruby, Dockerfile, Scala, Dart, and many more. 306 total languages available via [tree-sitter-language-pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack).

## Documentation

For detailed documentation, advanced options, and examples, visit:
[https://github.com/polylint/uncomment](https://github.com/polylint/uncomment)

## polylint organization

uncomment is part of [polylint](https://github.com/polylint), high-performance Rust linters and formatters built for agentic workflows. Sibling tools: [polylint](https://github.com/polylint/polylint) (one linter and formatter for every language; it can run uncomment as an engine), [skif](https://github.com/polylint/skif) (JS/TS dependency linter), [adrlint](https://github.com/polylint/adrlint) (MADR decision records). Install any of them from the Homebrew tap (`brew tap polylint/tap`) or the Scoop bucket.

## License

MIT - see [LICENSE](https://github.com/polylint/uncomment/blob/main/LICENSE) for details.
