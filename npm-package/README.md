# @polylint/uncomment

[![npm](https://img.shields.io/npm/v/@polylint/uncomment?style=flat-square&color=2dd4bf&label=npm)](https://www.npmjs.com/package/@polylint/uncomment)
[![License: MIT](https://img.shields.io/badge/License-MIT-2dd4bf?style=flat-square)](https://github.com/polylint/uncomment/blob/main/LICENSE)

A blazing fast Rust-based command-line tool that removes comments from your source code. Perfect for cleaning up AI-generated code that comes with excessive explanations.

## Why Use This?

- 🚀 **Lightning Fast** - Built in Rust for maximum performance
- 🎯 **100% Accurate** - Never accidentally removes code that looks like comments
- 🛡️ **Safe by Default** - Preview changes before applying them
- 🌍 **Multi-language** - 49 built-in languages, 306 available via [tree-sitter-language-pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack)
- 🔧 **Self-contained** - Installs a single static Rust binary, checksum-verified against the GitHub release

## Installation

```bash
npm i -g @polylint/uncomment
```

Or run it without installing: `npx @polylint/uncomment .`. The installed command is still
`uncomment`. This package was previously published as `uncomment-cli`, which is deprecated.

The postinstall step downloads the pre-compiled binary for your platform and verifies
it against the release checksum manifest. Prebuilt archives exist for:

| Platform | Architectures |
| --- | --- |
| Linux (glibc) | `x86_64`, `aarch64` |
| macOS | `x86_64`, `aarch64` |
| Windows | `x86_64` |

Anything else — musl/Alpine Linux, 32-bit, other architectures — has no prebuilt
archive; install with `cargo install uncomment` instead.

## Commands

| Command | What it does |
| --- | --- |
| `uncomment <paths>` | Remove comments (the default, with no subcommand) |
| `uncomment init` | Write a template `.uncomment.toml` |
| `uncomment scan` | Report every comment and the verdict a run would reach; writes no files |
| `uncomment keep` | Write `~keep` markers into the comments a decision selected |
| `uncomment lint` | Check tag comments (TODO, FIXME, HACK, XXX) against the `[lint]` convention |

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
- Linting directives (`eslint-disable`, `@ts-ignore`, etc.)
- Documentation strings and JSDoc comments (configurable)

### Supported Languages

49 built-in languages including Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, Ruby, Dockerfile, Scala, Dart, and many more. 306 total languages available via [tree-sitter-language-pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack).

## Common Use Cases

**Clean up AI-generated code:**

```bash
uncomment generated_code.js
```

**Remove all comments including TODOs:**

```bash
uncomment --remove-todo --remove-fixme src/
```

**Remove documentation comments:**

```bash
uncomment --remove-doc api.ts
```

**Use multiple threads for large codebases:**

```bash
uncomment --threads 8 entire_project/
```

## Documentation

For detailed documentation, advanced options, and examples, visit:
[https://github.com/polylint/uncomment](https://github.com/polylint/uncomment)

## polylint organization

uncomment is part of [polylint](https://github.com/polylint), high-performance Rust linters and formatters built for agentic workflows. Sibling tools: [polylint](https://github.com/polylint/polylint) (one linter and formatter for every language; it can run uncomment as an engine), [skif](https://github.com/polylint/skif) (JS/TS dependency linter), [adrlint](https://github.com/polylint/adrlint) (MADR decision records). Install any of them from the Homebrew tap (`brew tap polylint/tap`) or the Scoop bucket.

## License

MIT - see [LICENSE](https://github.com/polylint/uncomment/blob/main/LICENSE) for details.
