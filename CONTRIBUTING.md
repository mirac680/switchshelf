# Contributing

Thanks for considering a contribution to SwitchShelf.

## Before opening a pull request

- Describe the interruption/resumption workflow the change improves.
- Keep runtime dependencies at zero unless a dependency is essential.
- Do not add source-content capture, remote uploads, or project-command execution without discussing the privacy and safety implications in an issue first.
- Preserve cross-platform behavior for Windows, macOS, and Linux.
- Document any new stored fields and their privacy implications.
- Keep reports useful when Git is unavailable or the project is not a repository.

## Development setup

    py -m pip install -e .

Run the CLI from the repository:

    py -m switchshelf --help

Please include appropriate automated checks with code changes and explain what you ran in the pull request description.
