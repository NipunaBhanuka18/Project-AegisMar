# Developer Installation & Environment Setup Guide

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.1  
**Target Runtime:** Python 3.11.9  
**Toolchain:** `uv` Package Manager  

---

## 1. System Prerequisites

Before installing Project AegisMar, ensure your workstation meets the following prerequisites:

- **Operating System**: Windows 10/11 (64-bit), Ubuntu 22.04+ (or other modern Linux), or macOS 13+ (Apple Silicon or Intel).
- **Git**: Version 2.40 or higher.
- **Python**: CPython 3.11.9 installed.
- **uv Package Manager**: Version 0.11.0 or higher.
  - Windows installation: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Linux/macOS installation: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## 2. Step-by-Step Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/NipunaBhanuka18/Project-AegisMar.git
cd Project-AegisMar
```

### Step 2: Synchronize Environment with `uv`
AegisMar utilizes `uv` to manage the virtual environment and deterministic dependency locking via `uv.lock`.

Execute the sync command from the project root:
```bash
uv sync
```
This command automatically:
1. Detects `.python-version` (pinned to 3.11.9).
2. Creates or links the local virtual environment under `.venv`.
3. Installs the development dependencies (`pytest`, `ruff`, `mypy`, `pytest-cov`).
4. Installs the `aegismar` package in editable mode (`-e .`).

---

## 3. Verification & Quality Assurance

Verify that your environment is correctly initialized and passes all static and dynamic quality gates:

```powershell
# 1. Verify Python runtime version
uv run python --version
# Expected: Python 3.11.x

# 2. Verify clean package import
uv run python -c "import aegismar; print('Package import OK:', aegismar.__version__)"
# Expected: Package import OK: 0.1.0.dev1

# 3. Run automated smoke tests
uv run pytest -v

# 4. Run static linting checks
uv run ruff check .

# 5. Run formatting verification
uv run ruff format --check .

# 6. Run static type checking
uv run mypy src
```

---

## 4. Troubleshooting Common Setup Issues

### Issue A: Windows Hardlink Fallback Warning during `uv sync`
- **Symptom**: `warning: Failed to hardlink files; falling back to full copy. This may lead to degraded performance.`
- **Explanation**: This occurs on Windows systems when the global `uv` package cache (`C:\Users\<user>\AppData\Local\uv\cache`) resides on a different volume or drive from the workspace directory (e.g., `D:\Project AegisMar`).
- **Resolution**: This warning is completely harmless. Packages are copied directly into `.venv\Lib\site-packages` and operate identically. To suppress the warning, you can pass `--link-mode=copy` to uv commands.

### Issue B: Python Version Mismatch
- **Symptom**: `uv sync` reports that Python 3.11 is not found.
- **Resolution**: Ensure CPython 3.11 is installed, or allow `uv` to fetch a hermetic CPython 3.11 runtime:
  ```bash
  uv python install 3.11.9
  uv sync
  ```

### Issue C: Mypy Package Discovery
- **Symptom**: `mypy src` reports `Cannot find implementation or library stub for module named '...'`
- **Resolution**: Run all commands via `uv run` (e.g., `uv run mypy src`) to guarantee that type checkers execute within the isolated virtual environment context where packages and types are installed.

