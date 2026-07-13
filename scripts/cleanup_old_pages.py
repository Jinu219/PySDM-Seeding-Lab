from __future__ import annotations

from pathlib import Path


OLD_PAGES = [
    Path("pages/05_run.py"),
    Path("pages/06_results.py"),
    Path("pages/07_parameter_sweep.py"),
]


def main() -> None:
    removed = []
    for path in OLD_PAGES:
        if path.exists():
            path.unlink()
            removed.append(str(path))

    if removed:
        print("Removed old page files:")
        for path in removed:
            print(f"- {path}")
    else:
        print("No old page files found.")

    print("\nCurrent expected page order:")
    print("- pages/00_experiment_scenarios.py")
    print("- pages/01_environment.py")
    print("- pages/02_aerosol.py")
    print("- pages/03_seeding.py")
    print("- pages/04_dynamics.py")
    print("- pages/05_parameter_sweep.py")
    print("- pages/06_run.py")
    print("- pages/07_results.py")
    print("\nIf Streamlit still reports duplicate pathnames, fully stop it with Ctrl+C and restart.")


if __name__ == "__main__":
    main()
