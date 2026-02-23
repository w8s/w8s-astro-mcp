# Testing the MCP Server

## 1. Configure Claude Desktop

Add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "w8s-astro-mcp"
    }
  }
}
```

If swetest isn't on your system PATH, add it explicitly:

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "w8s-astro-mcp",
      "env": {
        "PATH": "/path/to/swisseph:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

## 2. Restart Claude Desktop

Close and reopen Claude Desktop completely.

## 3. Verify the Tools

You should see 22 tools available. Quick smoke test:

```
Can you check if swetest is installed using check_swetest_installation?
```

## 4. First-Time Setup

If you haven't created a profile yet:

```
Create an astro profile for me — my name is [Name], born [YYYY-MM-DD]
at [HH:MM] in [City, State].
```

Then verify it worked:

```
Show me my natal chart.
```

## 5. Test Transits

```
What are my transits for today?
```

## Troubleshooting

**Tools not showing up:**
- Check Claude Desktop config is valid JSON
- Restart Claude Desktop fully
- Check logs: `~/Library/Logs/Claude/mcp.log` (macOS)

**swetest errors:**
- Run `which swetest` in terminal to confirm it's on PATH
- Run `swetest -h` to confirm it works
- Add explicit PATH to MCP config (see above)

**Python/import errors:**
- Re-install: `pip install -e .` from the repo root
- Confirm you're using the right Python environment
