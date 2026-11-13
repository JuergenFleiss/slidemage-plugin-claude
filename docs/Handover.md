# Claude plugin handover

The plugin targets SlideMage phase 7, `feature/ai-free-core` (PR #26), checked out at `/home/juergen/github/SlideMage/.worktrees/ai-free-core`. Its packaged code imports SlideMage only through `slidemage.plugin_api`. The public task validation, image description prompt and image translation prompt helpers accept `RouteContext` directly, including project-specific settings and bibliography; the temporary project-path bridge has been removed. Phase 7 core registers no built-in AI routes, so the plugin owns the Claude route IDs.

The shared Claude settings section reads old API keys through the public legacy reader, preserves the cleared-key marker and notifies the host when the key changes. Claude Code creates its surface with `ChatSurfaceContext` for route selection, focus details, tools, attachments, and editor synchronization. The terminal widget is created before MCP/process startup so startup errors can be displayed in it. Session cancellation uses `CancelToken`; The hook uses `hook_context_from_environment` for snapshots, review and file operations. Core owns the route leases for tasks it starts; the plugin has no additional long-running route job.

Before the 1.0.0 release, make the repository public in the SlideMage organization, pin CI integration tests and the manifest compatibility range to a released SlideMage containing phase 7, and register the release in the plugin catalogue. See [PLAN.md](PLAN.md) for the remaining development-only import decision.

## Checks

Use the test support from the same worktree as the application:

```sh
SLIDEMAGE_TESTS=/home/juergen/github/SlideMage/.worktrees/ai-free-core/tests \
PYTHONPATH=/home/juergen/github/SlideMage/.worktrees/ai-free-core/src:. \
QT_QPA_PLATFORM=offscreen XDG_CONFIG_HOME=$(mktemp -d) \
/home/juergen/github/SlideMage/.venv/bin/python -m pytest -q
python3 build.py --check
```

Tests use local fake HTTP/MCP servers, not Anthropic's service. This sandbox denies sockets and can trap when Qt/WebEngine starts the terminal; the orchestrator must rerun the full suite where loopback sockets and WebEngine are available.

Against the phase 7 worktree, `python3 build.py --check` passed. The full test run trapped during terminal startup. With `test_a_process_that_cannot_start_is_shown_in_the_terminal_not_raised` deselected, 127 tests passed, 13 failed and 29 errored because socket creation was denied (10 terminal GUI and three MCP failures; 19 provider and 10 MCP fixture errors). The interrupted and sandbox-limited runs are not a full-suite pass.
