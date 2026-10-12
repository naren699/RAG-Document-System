# Contributing

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code. Never push directly. |
| `develop` | Integration branch. Features merge here first. |
| `feature/<name>` | Individual features (e.g., `feature/chunking`, `feature/frontend-upload`) |
| `fix/<name>` | Bug fixes |

## Workflow

1. Pull the latest `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   ```

2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Work on your feature. Commit often with clear messages.

4. Push and open a Pull Request into `develop`:
   ```bash
   git push -u origin feature/your-feature-name
   ```

5. Get at least one review before merging.

6. After merging, delete the feature branch.

## Commit Messages

Use this format:

```
<type>: <short description>

<optional body explaining why>
```

Types:
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation only
- `refactor` — code change that doesn't add a feature or fix a bug
- `test` — adding or updating tests
- `chore` — tooling, config, dependencies

Examples:
```
feat: add PDF text extraction with pdfplumber
fix: handle empty pages during chunking
docs: add architecture diagram
```

## Code Style

- Python: follow PEP 8. Use type hints.
- JavaScript/React: use functional components. Format with Prettier.
- Keep functions small and focused.

## Pull Request Rules

- PR title should match the commit message format
- Describe what changed and why
- Link to the relevant GitHub Issue if one exists
- Don't merge your own PR — get a review first
