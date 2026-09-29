# Installation

[ภาษาไทย](../th/installation.md) | **English**

The SDK lives in a **private** GitHub repository:

```
https://github.com/Nextjingjing/wms-sdk
```

| You want to | Read |
|---|---|
| use the SDK in a factory project | [Install as a package](#install-as-a-package) |
| change the SDK itself | [Work on the SDK](#work-on-the-sdk) |
| publish a new version | [Release a version](#release-a-version) |

## Before you start

- **Python 3.11** or later
- **Git** (pip installs from GitHub through git)
- **Access to the repository**: it is private, so ask the owner to add your GitHub account
- **Microsoft ODBC Driver 18 for SQL Server**, only if you connect to SQL Server ([download](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)). Not needed for SQLite-only tests

## Install as a package

Always pin a version tag, so everyone installs the same code.

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

- `[mssql]` also installs `pyodbc` for SQL Server; leave it out for SQLite-only use
- Extras for optional features, combined with commas, e.g. `wms-sdk[mssql,routing,floor_map]`:

  | Extra | Installs | Needed for |
  |---|---|---|
  | `mssql` | pyodbc | connecting to SQL Server |
  | `routing` | networkx | `features.routing.graph` / `repository` (shortest routes) |
  | `floor_map` | shapely | `features.floor_map.geometry` (outline checks) |

  The feature tables themselves need no extra, so migrations run without them
- `@v0.1.2` is the version tag. See the repository's tags / releases for available versions

### Signing in to a private repository

pip runs git, and git needs your GitHub credentials.

| Method | How |
|---|---|
| **Windows, Git Credential Manager** (easiest) | comes with Git for Windows; the first install opens a browser to sign in to GitHub |
| **GitHub CLI** | `gh auth login`, then `gh auth setup-git` |
| **SSH key** | add your key to GitHub, then use the SSH URL below |
| **Personal access token** (CI, servers) | a fine-grained token with *Contents: Read* on this repository only |

SSH URL:

```bash
pip install "wms-sdk[mssql] @ git+ssh://git@github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

With a token, read it from an environment variable. **Never write a token into a file that is committed.**

```bash
pip install "wms-sdk[mssql] @ git+https://${GITHUB_TOKEN}@github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

### Add it to your project

`requirements.txt`:

```
wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2
```

or `pyproject.toml`:

```toml
[project]
dependencies = [
    "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2",
]
```

### Check the install

```bash
python -c "import wms_sdk; print(wms_sdk.__version__)"
```

Prints `0.1.2`. Then continue with [Building a factory project](factory-guide.md).

### Pin to something other than a tag

| Pin | Example | Use for |
|---|---|---|
| tag | `@v0.1.2` | normal use (recommended) |
| commit | `@6997a3f` | trying a fix before it is released |
| branch | `@main` | never in production: the code changes under you |

### Upgrade

Change the tag in `requirements.txt` / `pyproject.toml`, then:

```bash
pip install --upgrade -r requirements.txt
```

If you pinned a branch, pip will not notice new commits by itself; add `--force-reinstall --no-deps` for `wms-sdk`.

Upgrading can change the schema. Read the release notes, then create an Alembic migration in your factory project (see [factory-guide.md](factory-guide.md#7-alembic)).

### Without access to GitHub

Someone with access builds a wheel and hands you the file:

```bash
python -m pip install build
python -m build --wheel          # creates dist/wms_sdk-0.1.2-py3-none-any.whl
```

```bash
pip install "wms_sdk-0.1.2-py3-none-any.whl[mssql]"
```

### Uninstall

```bash
pip uninstall wms-sdk
```

## Work on the SDK

```bash
git clone https://github.com/Nextjingjing/wms-sdk.git
cd wms-sdk
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Linux / macOS: .venv/bin/python
.venv\Scripts\python -m pytest
```

Continue with [Getting started](getting-started.md). The rules for changing the code are in [CLAUDE.md](../../CLAUDE.md).

## Release a version

For maintainers. Versions follow `MAJOR.MINOR.PATCH`; a change that breaks factory projects (renamed column, removed table, new required interface) raises MAJOR.

1. Set `__version__` in `wms_sdk/__init__.py`
2. `python -m pytest` passes
3. `python -m dev.gen_schema_doc` if the schema changed
4. Commit, then tag and push:

   ```bash
   git tag v0.2.0
   git push origin main
   git push origin v0.2.0
   ```

5. Optional: create a GitHub release for the tag, attach the wheel from `python -m build --wheel`, and list the schema changes factories must migrate
