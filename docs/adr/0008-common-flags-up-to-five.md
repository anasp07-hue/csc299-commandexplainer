# 0008. Show up to 5 common flags, and allow none

## Status
Accepted (2026-11-19). Changes SPEC.md §3.3 and the `common_flags` row in §5.

## Context
SPEC.md §3.3 said to show "the 3–5 most common flags" when the user types a command with no flags. Many commands don't have 3 flags a beginner actually uses. For example, `cd -P`, `pwd -L`, and `top -o` are rarely what a newcomer needs. Filling the list just to reach 3 would push confusing options at beginners.

## Decision
`common_flags` holds **up to 5** flags that beginners actually use, and it may be empty. When the user types no flags, show the list under a "Common options" heading. If the list is empty, leave the heading out. The data test enforces the limit of 5.

## Consequences
- The output stays focused on what's useful, and commands like `cd` show a short, clean explanation.
- The other flags are still explained when the user types them.
- Choosing what counts as "common" is a judgment call that gets made while writing the data.
