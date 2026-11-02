# Claude release history

v1.0.0 (2026-10-29, first release): Claude Code and the Anthropic API as SlideMage's cloud AI, as a plugin; they were part of SlideMage up to v9.0.

v1.0.1 (2026-10-29, website icon): The plugin has its own icon on the SlideMage website and in the plugin list, a cloud with an AI sparkle; the plugin itself is unchanged.

v1.0.2 (2026-10-30, hook on Windows): Claude Code no longer reports a failed UserPromptSubmit hook on Windows: the hook command now uses forward slashes in paths and double quotes, so Git Bash, which Claude Code runs it through, finds SlideMage.exe.

v1.0.3 (2026-10-30, SlideMage names): The hook finds the project with every SlideMage version: Claude Code gets the project folder as SLIDEMAGE_PROJECT, which SlideMage reads from v10 on, and as SLIDEMASTER_PROJECT for the versions before. The tests name the project variable through SlideMage and the bibliography SlideMage.bib.

v1.1.0 (2026-10-30, isolated chat requests): Claude Code can answer one self-contained ai.chat request on the chosen model and effort, with tools, inherited MCP servers and settings disabled. Replies accept free text or JSON without task validation, report CLI truncation signals, and abort ends the process. The assistant conversation stays in the terminal.

v1.2.0 (2026-11-02, any language of the project, with SlideMage v0.13.31): Claude Code translates image descriptions into the language SlideMage asks for, not only German: ClaudeTranslationBackend has a target_lang (German by default), the prompt is the one configured for English to that language, the answer schema has short, long and takeaway, and the result says its language. Requires SlideMage v0.13.31, whose image descriptions are per language.
