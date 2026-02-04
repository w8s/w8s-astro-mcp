# Testing the MCP Server

## 1. Configure Claude Desktop

Add this to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "python3",
      "args": [
        "-m",
        "w8s_astro_mcp.server"
      ],
      "env": {
        "PATH": "/Users/w8s/Documents/_git/swisseph:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

**Important:** Update the PATH to include where your swetest is located!

## 2. Restart Claude Desktop

Close and reopen Claude Desktop completely.

## 3. Test the Tools

In Claude Desktop, you should see three new tools available:

### Test 1: Check swetest Installation
```
Can you check if swetest is installed using the check_swetest_installation tool?
```

### Test 2: Configure Birth Data
```
Can you set up my birth data using setup_astro_config?
- Date: 1990-05-15
- Time: 14:30
- Location: Richardson, TX
- Latitude: 32.9483
- Longitude: -96.7297
- Timezone: America/Chicago
```

### Test 3: Get Transits
```
Can you get today's transits using get_transits?
```

## Troubleshooting

**Tools not showing up:**
- Check Claude Desktop config syntax (valid JSON)
- Restart Claude Desktop
- Check logs: `~/Library/Logs/Claude/mcp.log` (macOS)

**swetest errors:**
- Verify PATH includes swetest directory
- Run `which swetest` in terminal to verify
- Check swetest works: `swetest -h`

**Python errors:**
- Ensure virtual environment is activated
- Re-install: `pip install -e .`
