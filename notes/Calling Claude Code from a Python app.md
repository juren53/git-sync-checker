## Calling Claude Code from a Python app

There are several ways to call Claude Code from a Pyton app:  

**1. Via the Anthropic API (most common)**

You can call Claude models directly from Python using the `anthropic` SDK, passing the user's problem as a prompt. This is essentially embedding Claude in your app:

```python
import anthropic

client = anthropic.Anthropic(api_key="your-key")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[
        {"role": "user", "content": "My Python script is throwing a KeyError on line 42..."}
    ]
)
print(response.content[0].text)
```

**2. Via the Claude Code CLI as a subprocess**

Claude Code (`claude`) has a `--print` flag for non-interactive use, so you can shell out to it:

```python
import subprocess

result = subprocess.run(
    ["claude", "--print", "Explain why this regex fails: r'\\d{3}-\\d{4}'"],
    capture_output=True,
    text=True
)
print(result.stdout)
```

This approach lets you leverage Claude Code's agentic capabilities (file reading, running code, etc.) rather than just text generation.

**3. Via the Claude Code SDK (newer)**

Anthropic released a Python/TypeScript SDK specifically for Claude Code that allows you to run it programmatically with more control over its agentic behavior — including tool use, file access, and multi-turn sessions. This is the most powerful option if you want Claude to actually *act* on the problem (read files, suggest edits, run tests, etc.).

**Which approach fits your use case?** If you're thinking about embedding problem-solving help into one of your PyQt6 apps — like the HST-Metadata project — the API approach is the simplest to integrate. The Claude Code SDK is better if you want it to actually read and modify project files autonomously.
