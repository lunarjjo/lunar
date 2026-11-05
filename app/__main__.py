"""python -m app — start the lunar console server."""
from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(prog="lunar", description="offline realtime voice console")
    parser.add_argument("--host", default=os.environ.get("LUNAR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LUNAR_PORT", "8765")))
    parser.add_argument("--stub", action="store_true", help="run without the model (UI preview)")
    parser.add_argument("--no-banner", action="store_true")
    args = parser.parse_args()

    if args.stub:
        os.environ["LUNAR_STUB"] = "1"

    import uvicorn

    from . import __version__
    from .server import create_app

    if not args.no_banner:
        print(f"lunar v{__version__} — offline realtime voice console")
        print(f"  live console : http://{args.host}:{args.port}/")
        print(f"  config       : http://{args.host}:{args.port}/config")
        print(f"  ctrl-c stops the server\n")

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
