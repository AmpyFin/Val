# scripts/udp_listen.py
from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Optional

# Try to read defaults from control.py, but keep CLI fully overrideable
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5002
try:
    import control  # type: ignore
    DEFAULT_HOST = getattr(control, "BROADCAST_NETWORK", DEFAULT_HOST) or DEFAULT_HOST
    DEFAULT_PORT = int(getattr(control, "BROADCAST_PORT", DEFAULT_PORT))
except Exception:
    pass


def maybe_pretty_json(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    try:
        obj = json.loads(text)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return text


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Listen for AmpyFin UDP broadcasts.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind (default: {DEFAULT_PORT})")
    parser.add_argument("--raw", action="store_true", help="Print raw payload without JSON pretty-print.")
    parser.add_argument("--buf", type=int, default=65535, help="Receive buffer size (default: 65535)")
    args = parser.parse_args(argv)

    print(f"[udp_listen] Binding on {args.host}:{args.port} (Ctrl+C to quit)")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.host, args.port))
    except OSError as e:
        print(f"[udp_listen] Failed to bind: {e}")
        return 1

    try:
        while True:
            data, addr = sock.recvfrom(args.buf)
            print(f"\n[udp_listen] Received {len(data)} bytes from {addr[0]}:{addr[1]}")
            if args.raw:
                print(data.decode("utf-8", errors="replace"))
            else:
                print(maybe_pretty_json(data))
    except KeyboardInterrupt:
        print("\n[udp_listen] Exiting on user interrupt.")
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
