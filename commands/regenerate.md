---
description: Regenerate stale .tech.md documentation
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Chronicler Regenerate

Regenerate documentation for files whose source has changed since last scan.

## Step 1: Identify stale files

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.regenerate $ARGUMENTS
```

This prints which files are stale (source changed but docs haven't been updated).

## Step 2: Regenerate the docs

For each stale file reported above:

1. Read the current source file
2. Read the existing `.tech.md` file in `.chronicler/`
3. Update the `.tech.md` to reflect the current state of the source — keep the frontmatter structure, update the body sections (Purpose, Key Components, Dependencies, Architectural Notes)
4. Ensure the `source` frontmatter field and `> Source:` link after frontmatter point to the correct source path
5. Bump `governance.verification_status` to `"ai_draft"`

If `$ARGUMENTS` contains a specific file path, only regenerate that one file. Otherwise, regenerate all stale files.

Process files in batches. For each file, preserve the existing `component_id`, `layer`, `owner_team`, and `edges` where still accurate — only update what actually changed.

## Step 3: Rebuild INDEX.md

After regenerating docs, rebuild the index so it reflects updated purposes:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/chronicler-run.sh skill.index
```
