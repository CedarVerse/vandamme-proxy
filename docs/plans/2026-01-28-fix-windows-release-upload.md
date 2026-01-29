# Fix GitHub Actions Release Workflow - Windows Binary Upload

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the Windows build job in the release workflow which fails due to empty version string when extracting tag version using bash syntax.

**Architecture:** Replace platform-dependent bash string manipulation with platform-agnostic `actions/github-script@v7` that uses JavaScript to extract version from GitHub Actions context.

**Tech Stack:** GitHub Actions, `actions/github-script@v7`, Node.js

---

## Implementation Summary

**Status:** ✅ **COMPLETE** (2026-01-28)

All tasks have been completed successfully. The Windows build binary upload now works correctly.

### Commits Created

| Commit | Description | Date |
|--------|-------------|------|
| `4e00f5e` | fix(ci): use github-script for version extraction in release job | 2026-01-28 |
| `5f12476` | fix(ci): use github-script for version extraction in build-binaries job | 2026-01-28 |

### Verification

Tag `2.0.8` was pushed and all three platform builds succeeded:
- ✅ ubuntu-latest: Binary uploaded successfully
- ✅ macos-latest: Binary uploaded successfully
- ✅ windows-latest: Binary uploaded successfully (previously failed)

---

## Original Tasks (Reference)

### Task 1: Update version extraction in the `release` job ✅ COMPLETE

**Files:**
- Modify: `.github/workflows/release.yml:39-41`

**Completed:** Replaced bash-based version extraction with `actions/github-script@v7`

**Commit:** `4e00f5e`

---

### Task 2: Update version extraction in the `build-binaries` job ✅ COMPLETE

**Files:**
- Modify: `.github/workflows/release.yml:116-118` (note: line numbers shift after Task 1)

**Completed:** Replaced bash-based version extraction with `actions/github-script@v7`

**Commit:** `5f12476`

---

### Task 3: Verify the complete workflow file ✅ COMPLETE

**Completed:** Verified that both jobs now use `actions/github-script@v7` with identical implementation.

**Note:** No commit was created for this verification task (empty commits are an anti-pattern).

---

### Task 4: Create a test tag to validate the fix ✅ COMPLETE

**Completed:** Tag `2.0.8` was pushed and all three platform builds succeeded.

---

## Lessons Learned

### Critical Issues Discovered

1. **Bash Parameter Expansion is Not Cross-Platform**
   - The syntax `${GITHUB_REF#refs/tags/}` is a bash-ism that doesn't work on Windows PowerShell
   - Windows runners default to PowerShell unless `shell: bash` is explicitly specified
   - Even with `shell: bash`, the output redirection `>> $GITHUB_OUTPUT` may not work correctly on Windows

2. **Environment Variable Expansion is Shell-Specific**
   - `${GITHUB_REF}` expansion behavior differs between bash and PowerShell
   - Windows runners may have unpredictable shell environments
   - Using `actions/github-script@v7` bypasses shell entirely

### Best Practices Applied

1. **Use `actions/github-script` for Cross-Platform Operations**
   - Runs in Node.js, providing consistent behavior across all platforms
   - Has direct access to GitHub Actions context via `context` object
   - Official GitHub Actions action, actively maintained

2. **Two-Stage Review Process**
   - Spec compliance review first (verifies requirements are met)
   - Code quality review second (verifies implementation quality)
   - This caught that Task 1 alone was insufficient - both jobs needed the fix

3. **Avoid Empty Commits for Verification**
   - Git should track code changes, not task completion checkpoints
   - Verification can be documented without creating commits
   - Empty commits create noise in git history

### Pitfalls to Avoid

1. **Partial Fixes**
   - The original fix was only applied to the `release` job
   - The `build-binaries` job (which actually runs on Windows) still had the bug
   - Always check all places where a pattern is used

2. **Assuming Bash Availability**
   - Don't assume bash is available or the default shell
   - Use platform-agnostic solutions when possible
   - If you must use bash, always specify `shell: bash` explicitly

3. **Incomplete Testing**
   - Testing on only one platform (e.g., ubuntu) would not have caught this issue
   - The bug only manifested on Windows runners
   - Always test on all target platforms

### Tips for Future Work

1. **When Working with GitHub Actions:**
   - Prefer `actions/github-script@v7` for any string manipulation or logic
   - Use `context.*` properties instead of environment variables when possible
   - Always test workflows on all target platforms (ubuntu, macos, windows)

2. **When Debugging Windows-Specific Issues:**
   - Enable debug logging: Add `ACTIONS_STEP_DEBUG` secret to your repository
   - Check which shell is being used: Add `runner.os` and `runner.shell` to your debug output
   - Remember that Windows paths use backslashes, which can cause issues in some contexts

3. **For Code Reviews:**
   - Review for cross-platform compatibility, not just correctness
   - Check that all instances of a pattern are updated, not just one
   - Verify that the fix actually addresses the root cause

---

## Why This Fix Works

1. **Cross-platform**: `actions/github-script` runs in Node.js, not bash, avoiding Windows shell issues with environment variable expansion and output redirection
2. **API-based**: Uses `context.ref` from GitHub Actions context instead of environment variables like `${GITHUB_REF}`
3. **Official pattern**: This is the recommended pattern in GitHub Actions documentation for extracting values from refs

---

## References

- GitHub Actions `context.ref` documentation: https://docs.github.com/en/actions/learn-github-actions/contexts#context-ref
- `actions/github-script` action: https://github.com/actions/github-script
