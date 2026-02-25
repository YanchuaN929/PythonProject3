"""Module entry point."""

from .cli import main, maybe_pause_on_error


if __name__ == "__main__":
    code = main()
    maybe_pause_on_error(code)
    raise SystemExit(code)
