# Path Resolution Guide

This document captures critical lessons about file system path resolution in Ouroboros.

## The Two Path Roots

Ouroboros operates on two separate filesystem roots:

### Code Repository
- **Path:** `/home/cresh/ouroboros-desktop`
- **Purpose:** Self-editing code, configuration, documentation
- **Tool for reading:** `repo_read(filepath)` 
- **Tool for listing:** `repo_list(dir)`

### Data Directory
- **Path:** `/home/cresh/Ouroboros`
- **Purpose:** Runtime state, logs, memory, knowledge
- **Tool for reading:** `data_read(filepath)`
- **Tool for listing:** `data_list(dir)`

## Path Resolution Rule

**CRITICAL:** Never mix these up. Each tool is designed for one root only.

| Operation | Correct Tool | Incorrect Tool | Result |
|----------|-------------|----------------|--------|
| Read VERSION file | `repo_read("VERSION")` | `data_read("VERSION")` | ❌ Path error |
| Read state.json | `data_read("/data/state/state.json")` | `repo_read("state/state.json")` | ❌ Path error |
| Read identity.md | `data_read("memory/identity.md")` | `repo_read("memory/identity.md")` | ❌ Path error |
| Read ARCHITECTURE.md | `repo_read("docs/ARCHITECTURE.md")` | `data_read("docs/ARCHITECTURE.md")` | ❌ Path error |

## The PATH ERROR CORRECTION PATTERN

**Lesson from 2026-04-16:**

When you receive `[Errno 2] No such file or directory`:

1. ✅ **FIX THE PATH ONLY** — remove/add prefix, fix typo, correct directory
2. ❌ **DO NOT SWITCH TOOLS** — repo_read ↔ data_read switching creates confusion
3. ✅ **VERIFY THE ROOT** — confirm which directory the file is in

**Example Error:**

```python
# WRONG: File doesn't exist at constructed path
repo_read("/home/cresh/ouroboros-desktop/memory/knowledge/tool-selection-guide.md")
# → [Errno 2] No such file or directory

# WRONG: Switching tools instead of fixing path
data_read("memory/knowledge/tool-selection-guide.md")
# → Still fails: different tool, same wrong path

# CORRECT: Use the right path for the right tool
repo_read("memory/knowledge/evolution-crisis-recovery-2026-04-15.md")
# → File exists in CODE repository
```

## Quick Reference

**Ask yourself before reading a file:**

1. **What type of file is it?**
   - Code/config/docs that I edit? → Use `repo_read()` or `repo_list()`
   - State/logs/memory that system writes? → Use `data_read()` or `data_list()`

2. **Where does it live?**
   - Code repo? → `/home/cresh/ouroboros-desktop/<path>`
   - Data dir? → `/home/cresh/Ouroboros/data/<path>`

3. **Construct the correct path:**
   - Remove double prefixes (e.g., `data/data/...`)
   - Use the right base directory for the right tool

## Common Mistakes

### Mistake 1: Using repo_read for memory files
```python
# WRONG
repo_read("memory/identity.md")

# CORRECT
data_read("memory/identity.md")
```

### Mistake 2: Using data_read for code files
```python
# WRONG  
data_read("VERSION")

# CORRECT
repo_read("VERSION")
```

### Mistake: Double prefixes in paths
```python
# WRONG - constructs /home/cresh/Ouroboros/data/data/...
repo_read("data/state/state.json")

# CORRECT - file is at /home/cresh/Ouroboros/data/state/state.json
data_read("state/state.json")
```

### Mistake: Switching tools on any error
When `[Errno 2]` happens for the FIRST time with the wrong path:
```python
# WRONG - this wastes tokens and doesn't fix the root cause
repo_read("path/to/file")  # fails
repo_read("path/to/file")  # try again with different tool

# CORRECT - fix the path, stay with the right tool
data_read("correct/path/to/file")
```

## Default Rules

1. **Code repo operations** → `repo_read()` or `repo_list()`
2. **Data dir operations** → `data_read()` or `data_list()`
3. **If unsure → Ask user** which directory the file resides in
4. **If path error → Fix path only** - don't switch tools

## History

This document was created during Evolution #54 on 2026-04-16 to institutionalize the PATH ERROR CORRECTION PATTERN learned from user feedback.