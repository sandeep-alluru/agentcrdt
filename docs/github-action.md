# GitHub Action

Use agentcrdt directly in your GitHub Actions workflow:

```yaml
- name: agentcrdt
  uses: sandeep-alluru/agentcrdt@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install agentcrdt
  run: pip install agentcrdt

- name: Run agentcrdt
  run: agentcrdt --help
```
