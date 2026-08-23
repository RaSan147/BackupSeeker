# Coding Style Rules

## Avoid URL and Path Line Splitting
- **Never split URLs or Paths across multiple lines**:
  - Always keep URLs (such as `poster` image URLs, API endpoints, web links) as single unbroken line strings.
  - Always keep file system paths, contracted paths (e.g. `%USERPROFILE%/...`), and registry key paths on a single unbroken line string.
  - Do not use implicit string concatenation (`"part1" "part2"`) or binary `+` concatenation over linebreaks to wrap URLs or paths to fit line length limits.
  - URLs and path strings are exempt from maximum line length limits (e.g. PEP 8 line length guidelines).
