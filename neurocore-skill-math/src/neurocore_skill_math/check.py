"""`python -m neurocore_skill_math.check` — report which math backends are available.

Helps users "take advantage of the math tools available": prints a table of CLI
tools and Python libraries and whether each is installed in the current environment.
"""
from __future__ import annotations

from neurocore_skill_math._availability import availability_report


def main() -> None:
    report = availability_report()
    print("neurocore-skill-math — tool availability\n")
    for section, label in (("cli", "CLI tools"), ("lib", "Python libraries")):
        print(f"{label}:")
        for name, ok in sorted(report[section].items()):
            mark = "✓" if ok else "✗"
            print(f"  [{mark}] {name}")
        print()
    usable = sum(v for s in report.values() for v in s.values())
    total = sum(len(s) for s in report.values())
    print(f"{usable}/{total} backends available.")


if __name__ == "__main__":
    main()
