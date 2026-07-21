"""DX Command launcher - used by run.bat/run_demo.bat alternatives and as the
PyInstaller entry point for the one-file Windows build."""
import os
import threading
import webbrowser


def main() -> None:
    import uvicorn
    from app.config import load_config
    from app.main import app

    cfg = load_config()
    url = f"http://localhost:{cfg.port}"
    print(f"DX Command starting at {url}  (demo mode: {cfg.demo_mode})")
    if os.environ.get("DXDASH_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
