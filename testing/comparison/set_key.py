"""Run in your own terminal for masked, local OpenRouter key entry."""
import getpass
import os
from pathlib import Path
import warnings


def main():
    path = Path(__file__).resolve().parents[2] / ".env.openrouter"
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            key = getpass.getpass("OpenRouter API key (hidden): ").strip()
        except getpass.GetPassWarning:
            raise SystemExit("Masked input unavailable. Run this in your own terminal or edit .env.openrouter locally.")
    if not key or any(ch.isspace() for ch in key):
        raise SystemExit("Key not saved: provide one non-empty key without whitespace.")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.startswith("OPENROUTER_API_KEY=")]
    lines.append("OPENROUTER_API_KEY=" + key)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    print("OpenRouter key saved locally. The key was not printed.")


if __name__ == "__main__":
    main()
