#!/usr/bin/env python3
"""Entry point for w8s-astro-mcp server."""

from w8s_astro_mcp.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
