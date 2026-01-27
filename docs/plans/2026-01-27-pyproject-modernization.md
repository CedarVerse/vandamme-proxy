# pyproject.toml Modernization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modernize pyproject.toml by fixing version inconsistencies, cleaning up dependency configuration, and improving tooling configuration.

**Architecture:** Align all Python version declarations across the project, remove redundant dependency declarations, enhance linting/type checking configuration, and add type stubs for better coverage.

**Tech Stack:** ruff, mypy, pytest

---

## ✅ COMPLETION STATUS

**Date Completed:** 2026-01-27

**All Tasks Complete:** This plan has been fully executed and validated.

**Commits:**
- `dc45681` - fix: align Python version declarations to 3.11+ minimum
- `a17582c` - chore: remove redundant dev from optional-dependencies (use dependency-groups)
- `37cf714` - chore: enable ruff PERF rules for performance anti-pattern detection
- `49ffd1d` - chore: finalize pyproject.toml modernization with comprehensive validation

**Validation Results:**
- ✅ All 439 tests pass (unit + integration)
- ✅ Type checking passes (211 source files)
- ✅ Linting passes (including PERF rules)
- ✅ Build succeeds (wheel + tarball)
- ✅ Version command works
- ✅ Pip install from wheel works

---

## Future Consideration: Replacing Hatchling

**Status:** NOT included in this plan - deferred for future evaluation

### Build Backend Comparison

| Aspect | Hatchling | setuptools | UV (native) |
|--------|-----------|------------|-------------|
| **Status** | PYP A-recommended modern default | Legacy standard, battle-tested | Experimental, not production-ready |
| **Maturity** | Growing rapidly | Mature, decades of development | Pre-release |
| **uv build support** | Full support, well-tested | Full support, known issues (#16828) | N/A (would replace uv build) |
| **VCS versioning** | Via hatch-vcs plugin | Via setuptools_scm | Built-in |
| **Configuration** | Modern, clean | Verbose, complex | TBD (not stable) |
| **Your current setup** | Working perfectly | Would work with migration | Not recommended yet |

### Why Keep Hatchling?

1. **Recommended by PyPA** - Python Packaging User Guide recommends hatchling as the modern default
2. **Already Working** - No issues with current setup; version format is exactly what you need
3. **uv build compatibility** - Excellent support, no known issues with hatchling backend
4. **Zero Migration Effort** - No changes required, no risk of breakage
5. **Your Configuration is Correct** - Proper three-tier version fallback, VCS-based versioning

### Why setuptools_scm is NOT a clear upgrade:

- **Same functionality** - Both provide Git-based versioning via plugins
- **No performance gain** - Build time differences are negligible
- **More verbose config** - Requires `[tool.setuptools]`, `[tool.setuptools_scm]`, `[tool.setuptools.package-data]`
- **Known uv issue** - [uv#16828](https://github.com/astral-sh/uv/issues/16828) - setuptools_scm version retrieval problems

### UV's Future Plans (Important Context)

UV has **experimental** native build support that may eventually replace separate build backends, but it is **not production-ready**:

- Currently in early development
- API is unstable and may change
- Not recommended for production use
- Would require significant refactoring when stable

**Recommendation:** Wait for UV's native build to stabilize before considering a migration.

### When to Reconsider Hatchling:

- If you encounter specific hatchling bugs that block you
- If you need setuptools-specific features not available in hatchling
- If UV's native build backend becomes stable and recommended

**Migration Path (if needed in the future):**

```toml
# Would replace [build-system] and add:
[build-system]
requires = ["setuptools>=80", "setuptools_scm>=8"]
build-backend = "setuptools.build_meta"

[tool.setuptools_scm]
version_file = "src/_version.py"
write_to = "src/_version.py"
```

---

## Task 1: Fix Python Version Inconsistencies ✅

**Status:** COMPLETED - Commit `dc45681`

**What Was Done:**
- Changed `requires-python` from `">=3.13"` to `">=3.11"`
- Added Python 3.13 to classifiers
- Changed `target-version` from `"py310"` to `"py311"`
- Changed `python_version` from `"3.10"` to `"3.11"`

**Verification:** All type checks and linting passed with no version-related warnings.

---

## Task 2: Add Type Stubs for External Dependencies ⏭️

**Status:** SKIPPED - `types-openai` package does not exist

**What We Discovered:**
- The `types-openai` package does not exist on PyPI
- The OpenAI SDK (`openai>=1.54.0`) already includes comprehensive type hints
- No separate stubs package is needed

**Lesson:** Always verify package existence before adding to dependencies. The OpenAI SDK has built-in type hinting support.

---

## Task 3: Remove Redundant dev Dependencies from optional-dependencies ✅

**Status:** COMPLETED - Commit `a17582c`

**What Was Done:**
- Removed the `dev` section from `[project.optional-dependencies]` (pytest, pytest-asyncio, httpx)
- Kept the `cli` section intact
- Verified CLI extra installation still works

**Why This Matters:**
- `[dependency-groups]` is for local development (used by uv)
- `[project.optional-dependencies]` is for published extras (used by pip install)
- Having dev dependencies in both places was redundant and confusing

---

## Task 4: Add Ruff Performance Rules ✅

**Status:** COMPLETED - Commit `37cf714`

**What Was Done:**
- Added `"PERF"` to the `[tool.ruff.lint]` select list
- Added `PERF401` and `PERF403` to the ignore list with rationale

**Why PERF401/PERF403 Were Ignored:**
- 34 violations were detected when PERF was first enabled
- Most violations involved async generators where comprehensions are less readable
- Others involved complex conditional logic that's clearer with explicit loops
- Performance gains from these conversions would be negligible

**Files with PERF401/PERF403 violations:**
- `src/conversion/content_utils.py`
- `src/conversion/openai_stream_to_claude_state_machine.py`
- `src/conversion/openai_to_anthropic.py`
- `src/conversion/pipeline/transformers/system_message.py`
- `src/core/alias_manager.py`
- `src/core/config/validation.py`
- `src/dashboard/data_sources.py`
- `src/middleware/base.py`
- Multiple test files

---

## Task 5: Full Validation ✅

**Status:** COMPLETED - Commit `49ffd1d`

**Validation Results:**
- ✅ All 439 tests pass (unit + integration)
- ✅ Type checking passes (211 source files)
- ✅ Linting passes (310 files formatted correctly)
- ✅ Wheel built successfully: `vandamme_proxy-1.4.2.dev134+g37cf71423.d20260127-py3-none-any.whl`
- ✅ Version command works: `vdm version 1.4.2.dev134+g37cf71423.d20260127`
- ✅ Pip install from wheel works (67 dependencies resolved)

---

## Summary of Changes

| Category | Change | Commit | Impact |
|----------|--------|--------|--------|
| Python Version | >=3.13 → >=3.11 | dc45681 | Matches classifiers, practical |
| Dependency Groups | Removed dev duplication | a17582c | Cleaner configuration |
| Linting | Added PERF rules | 37cf714 | Performance optimization |
| Build Backend | Kept hatchling | N/A | Stable, working, recommended |

---

## Lessons Learned

### 1. Type Stubs Package Availability

**Critical Discovery:** The `types-openai` package does not exist because the OpenAI SDK already includes type hints.

**Tip:** Before adding a `types-*` package, verify:
1. Check if the package exists on PyPI: `pip index types-openai`
2. Check if the library already has type hints built-in
3. Search for existing type stub packages in the `types-*` namespace

**Resources:**
- [python-typeshed](https://github.com/python/typeshed) - Official repository for type stubs
- [OpenAI Python Type Hints](https://github.com/openai/openai-python/issues/551) - Discussion on built-in types

### 2. PERF401/PERF403 - When to Ignore

**Context:** Ruff's PERF401 and PERF403 rules suggest using list/dict comprehensions instead of manual loop-based collection building.

**When to Ignore:**
- **Async generators** - Async comprehensions are harder to debug and understand
- **Complex conditional logic** - Multiple branches with `continue` statements
- **Nested data transformations** - Dictionary operations with multiple method calls
- **Test code** - Readability is more important than micro-optimizations

**When to Fix:**
- Simple synchronous loops with single append operations
- Performance-critical code paths
- Hot loops in production code

**Verification:** Always run `ruff check --select PERF401,PERF403` before adding ignores to confirm violations actually exist.

### 3. dependency-groups vs optional-dependencies

**Key Distinction:**
- **`[dependency-groups]`** - For local development (used by `uv sync`)
- **`[project.optional-dependencies]`** - For published package extras (used by `pip install package[extra]`)

**Best Practice:**
- Put dev dependencies only in `[dependency-groups]`
- Put user-facing extras only in `[project.optional-dependencies]`
- Never duplicate between the two

### 4. Python Version Alignment

**Critical:** Ensure consistency across:
1. `requires-python` in `[project]`
2. `classifiers` in `[project]`
3. `target-version` in `[tool.ruff]`
4. `python_version` in `[tool.mypy]`
5. CI/CD matrix (`.github/workflows/*.yml`)

**Note:** Task 1 aligned pyproject.toml but CI still tests Python 3.10. Consider updating the CI matrix in `.github/workflows/ci.yml` to remove Python 3.10 from testing.

### 5. Code Review Validation

**Pitfall:** One code reviewer incorrectly claimed "no PERF401/PERF403 violations exist."

**Lesson:** Always verify claims by running the actual linter:
```bash
ruff check --select PERF401,PERF403
```

**Why the mistake happened:**
- Reviewer may have run ruff without the `--select` flag
- May have misinterpreted the output format
- May have checked a different codebase state

**Prevention:** Include actual verification commands in code review instructions.

### 6. Hatchling vs setuptools_scm

**Decision:** Kept hatchling after careful analysis.

**Key Factors:**
- Hatchling is the PYP A-recommended modern default
- Both tools provide identical VCS-based versioning
- No performance advantage to switching
- setuptools has a known uv issue (#16828)
- uv build has excellent hatchling support

**Future Watch:** Monitor UV's native build backend development for potential future migration.

---

## Remaining Work (Optional)

### Update CI/CD Matrix

**Status:** NOT DONE - Optional cleanup

**Current State:** `.github/workflows/ci.yml` tests Python `["3.10", "3.11", "3.12"]` despite `requires-python = ">=3.11"`

**Impact:** CI wastes ~5 minutes per run testing Python 3.10, which is no longer supported

**Suggested Change:**
```yaml
# In .github/workflows/ci.yml
matrix:
  python-version: ["3.11", "3.12", "3.13"]  # Remove 3.10
```

### Update Documentation

**Status:** NOT DONE - Documentation drift expected after infrastructure changes

**Files That May Reference Old Python Versions:**
- `QUICKSTART.md`
- `BINARY_PACKAGING.md`
- Wiki pages in `.qoder/repowiki/`

**Suggested Action:** Audit documentation and update Python version references if found.

---

## Testing Checklist

All items verified during Task 5:

- [x] `uv build --wheel` succeeds
- [x] `make build-cli` succeeds with version file
- [x] `vdm version` shows correct version
- [x] `make test` passes (unit + integration)
- [x] `make type-check` passes
- [x] `make lint` passes (including PERF rules)
- [x] Wheel installs via pip correctly
- [x] No version-related warnings in any output

---

## Rollback Plan

If issues occur:

```bash
# To revert all changes
git revert --no-commit HEAD~4..HEAD
git commit -m "revert: rollback pyproject.toml modernization due to issues"
```

---

## Notes

- Hatchling remains unchanged - it's the recommended modern tool and working well
- _version.py continues to be generated by hatch-vcs
- All Makefile targets continue to work without changes
- uv build has full hatchling support
- Version fallback logic in `src/__init__.py` remains unchanged
- All 439 tests pass with the new configuration
