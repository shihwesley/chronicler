#!/bin/bash
cd /Users/quartershots/Source/Chronicler
git worktree prune
git branch -d orchestrate/phase-5b-plugin-interfaces 2>/dev/null
git log --oneline -5
echo "CLEANUP COMPLETE"
