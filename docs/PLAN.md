# Claude plugin integration plan

The plugin targets SlideMage phase 7, `feature/ai-free-core` (PR #26), including its unreleased API 1 additions. Activation registers `anthropic_api`, `claude_code`, a shared AI settings section and the hook without creating widgets, reading keys, launching processes or using the network. The package imports only `slidemage.plugin_api` from SlideMage; `python3 build.py --check` enforces this.

Claude Code uses `chat_surface_v2`, the public chat context, terminal service, edit watch and process-aware cancellation token. The hook uses the public hook context for classification, snapshots and review records. The task and image backends use the public definitions and result types; task validation and both image prompt helpers receive `RouteContext` directly. Legacy Anthropic keys are read through the host or route context, with the saved/cleared marker preventing resurrection; saving a key notifies model pickers.

Route tasks, image batches and slide translation are started and leased by core. This plugin has no separate long-running settings job requiring `acquire_route_task` or progress reporting; its sign-in probe uses the ordinary background service. `legacy_ollama_host` is not relevant to the Claude routes. Phase 7 core registers no built-in AI routes, leaving ownership of the Claude IDs to this plugin.

The packaged plugin has no private SlideMage imports. Integration tests still import core internals to construct real application fixtures; they are outside the package.

## Before 1.0.0

- Make the plugin repository public in the SlideMage organization and update its homepage as appropriate.
- Pin CI integration tests to a released SlideMage containing phase 7, and set the manifest's compatibility range to that release. The current `>=10.0` range does not establish compatibility with an unreleased API.
- Register the release in the SlideMage plugin catalogue.

## Needs a decision

- **Development-only imports:** removing private imports from integration tests would require replacing core-specific fixtures. Recommend retaining them until core supplies equivalent public test interfaces; package imports already meet the strict checker.
