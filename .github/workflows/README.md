# CI Workflows

## ci.yml
GitHub Actions workflow triggered on push and pull_request.

**Backend job** (ubuntu-latest, Python 3.11):
- Installs test dependencies (pytest, mypy, fastapi, httpx, pydantic, numpy, scikit-learn, ruff)
- Runs pytest with `-q` flag
- Runs mypy (non-blocking; tighten enforcement later as type coverage improves)
- Runs ruff check (non-blocking initially)

**Frontend job** (ubuntu-latest, Node 20):
- Installs npm dependencies via `npm ci`
- Builds the Next.js app via `npm run build`

Both jobs run independently.
