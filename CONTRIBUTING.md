# Contributing

Open an issue before making a large change. Keep pull requests focused and include tests for new
behavior or bug fixes.

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Do not include credentials, session files, caches, or exported personal music data.
