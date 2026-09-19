# Testing the MCP Server

## 1. Configure Claude Desktop

Add to your Claude Desktop config:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "uvx",
      "args": ["w8s-astro-mcp"]
    }
  }
}
```

## 2. Restart Claude Desktop

Close and reopen Claude Desktop completely.

## 3. Verify the Tools

You should see 30 tools available. Quick smoke test:

```
Can you check the ephemeris mode using check_ephemeris?
```

## 4. First-Time Setup

If you haven't created a profile yet:

```
Create an astro profile for me — my name is [Name], born [YYYY-MM-DD]
at [HH:MM] in [City, State].
```

Then set yourself as the owner — this tells all tools who you are:

```
Set me as the owner profile.
```

Verify it worked:

```
Show me my natal chart.
```

## 5. Test Transits

```
What are my transits for today?
```

## 6. Test Aspect Direction

```
Which of today's transits to my natal chart are building and which are fading?
```

Each aspect should say which chart each body is from (natal or transit) and whether it is
applying or separating, with an estimated time of exactness in UT. For structured output, ask
for JSON and natal angles explicitly:

```
Compare my natal chart to today's sky as JSON, including my natal angles.
```

(The tool arguments behind that prompt are `format: "json"` and `include_angles: "natal"`.)

## Troubleshooting

**Tools not showing up:**

- Check Claude Desktop config is valid JSON
- Restart Claude Desktop fully
- Check logs: `~/Library/Logs/Claude/mcp.log` (macOS)

**Ephemeris errors:**

- Run `uvx w8s-astro-mcp` in terminal to confirm it starts cleanly
- Use the `check_ephemeris` tool to verify the ephemeris mode
- Use `download_ephemeris_files` to upgrade to full Swiss Ephemeris precision (optional)

**Python/import errors:**

- Re-install: `.venv/bin/python -m pip install -e ".[dev]"` from the repo root
- Confirm you're using `.venv` (the canonical environment — `venv/` no longer exists)
