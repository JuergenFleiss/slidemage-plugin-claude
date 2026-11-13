# Claude release history

v1.0.0 (2026-10-29, first release): Claude Code and the Anthropic API as SlideMage's cloud AI, as a plugin; they were part of SlideMage up to v9.0.

v1.0.1 (2026-10-29, website icon): The plugin has its own icon on the SlideMage website and in the plugin list, a cloud with an AI sparkle; the plugin itself is unchanged.

v1.0.2 (2026-10-30, hook on Windows): Claude Code no longer reports a failed UserPromptSubmit hook on Windows: the hook command now uses forward slashes in paths and double quotes, so Git Bash, which Claude Code runs it through, finds SlideMage.exe.

v1.0.3 (2026-10-30, SlideMage names): The hook finds the project with every SlideMage version: Claude Code gets the project folder as SLIDEMAGE_PROJECT, which SlideMage reads from v10 on, and as SLIDEMASTER_PROJECT for the versions before. The tests name the project variable through SlideMage and the bibliography SlideMage.bib.

v1.1.0 (2026-10-30, isolated chat requests): Claude Code can answer one self-contained ai.chat request on the chosen model and effort, with tools, inherited MCP servers and settings disabled. Replies accept free text or JSON without task validation, report CLI truncation signals, and abort ends the process. The assistant conversation stays in the terminal.

v1.2.0 (2026-11-02, any language of the project, with SlideMage v0.13.31): Claude Code translates image descriptions into the language SlideMage asks for, not only German: ClaudeTranslationBackend has a target_lang (German by default), the prompt is the one configured for English to that language, the answer schema has short, long and takeaway, and the result says its language. Requires SlideMage v0.13.31, whose image descriptions are per language.

v1.2.1 (2026-11-06, protected parts as SlideMage defines them): The hook and Claude Code's instructions name the protected parts of a slide as the running SlideMage applies them. From SlideMage v0.14.25 those are the '%%' lines at the top of a slide and its \setSlideVersion line, and the ordinary '%' notes at the top (sources, the user's instructions) are editable; an older SlideMage protects the whole comment block there. The plugin reads which rule applies from plugin_api.protected_spans. Overlay blocks (\vbox to 0pt{...}) are no longer named as protected: SlideMage stopped protecting them in v9.4.0, but the message and the instructions still said so, and Claude Code avoided editing them. The hook no longer refuses an edit because the protected lines stopped being the first thing in the file, so deleting a note above them is allowed.

v1.2.2 (2026-11-07, SlideMage's theme values, with SlideMage v0.14.36): The Claude Code view reads its link colour from theme().info instead of the deprecated theme_color("info"), and its gaps and the setup card's padding from the theme's spacing steps (the card's padding is 12 px like SlideMage's cards, was 14). Requires SlideMage v0.14.36.

v1.3.0 (2026-11-13, Claude Code is the terminal only): SlideMage no longer starts hidden `claude -p` runs: on Cloud · Claude Code the conversation is the terminal, where you ask Claude for fixes, translations and image descriptions, and the task buttons and AI requests say so and need Cloud · Anthropic API or Local. Claude translates slides itself instead of calling translate_slide. Claude Code now gets your environment as you set it, including ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN and the Bedrock, Vertex and Foundry switches (CLAUDE_CODE_USE_*), so it signs in the way you chose; the plugin's own stored API key stays with the Anthropic API route.

v1.4.0 (2026-11-13, Translate types its prompt for Claude Code, with SlideMage v0.16.34): On Cloud · Claude Code the Translate button types a ready prompt into Claude Code's input box (the slide as an @path, the language, and how to translate with add_slide and modify_slide); you read it and press Enter, SlideMage never sends it. If Claude Code is busy or its input box holds text, SlideMage says so and types nothing.
