"""Thin entry point for local development and WSGI servers."""

from letterbox import app, run_dev_server


if __name__ == "__main__":
    run_dev_server()
