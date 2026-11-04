"""Entry point for the MCP Meetup-Claude server."""

import logging
import sys

from . import __version__
from .config import Config
from .server import mcp


def _setup_logging() -> None:
    level_name = Config.from_env().LOG_LEVEL.upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    """Run the MCP server over stdio (the transport MCP clients expect)."""
    _setup_logging()
    logging.getLogger(__name__).info(
        "Starting MCP Meetup-Claude server v%s", __version__
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
