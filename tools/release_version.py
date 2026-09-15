#!/usr/bin/env python3
"""Připraví pracovní strom na novou verzi aplikace.

Jediný zdroj čísla verze zůstává core/version.py → APP_VERSION.
Nové číslo se nezadává: helper zachová major i minor a patch zvýší o 1.

Příklad:
    python tools/release_version.py "Úprava Kontrol změn RPP"
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
APP_VERSION_ASSIGNMENT = re.compile(
    r'^APP_VERSION = "([^"]*)"$',
    re.MULTILINE,
)
APP_NAME_ASSIGNMENT = re.compile(
    r'^APP_NAME = "([^"]*)"$',
    re.MULTILINE,
)
CHANGELOG_INSERT_MARK = "# Historie verzí\n\n---\n\n"
GENERATOR_SCRIPTS = ("generate_version_info.py", "generate_installer_iss.py")


class ReleaseVersionError(ValueError):
    """Neplatný vstup nebo selhání přípravy release."""


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    existed: bool
    content: bytes | None


@dataclass(frozen=True)
class ReleasePreparation:
    old_version: str
    new_version: str
    changelog_added: bool
    updated_paths: tuple[Path, ...]


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _czech_date(value: date) -> str:
    return f"{value.day}. {value.month}. {value.year}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _snapshot(paths: list[Path]) -> list[FileSnapshot]:
    snapshots: list[FileSnapshot] = []
    for path in paths:
        existed = path.exists()
        snapshots.append(
            FileSnapshot(
                path=path,
                existed=existed,
                content=path.read_bytes() if existed else None,
            )
        )
    return snapshots


def _restore(snapshots: list[FileSnapshot]) -> None:
    for snapshot in snapshots:
        if snapshot.existed:
            assert snapshot.content is not None
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.content)
        elif snapshot.path.exists():
            snapshot.path.unlink()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ReleaseVersionError(f"Chybí {label}: {path}")


def _parse_app_version(version_source: str) -> str:
    matches = list(APP_VERSION_ASSIGNMENT.finditer(version_source))
    if len(matches) != 1:
        raise ReleaseVersionError(
            "V core/version.py musí být právě jedno přiřazení APP_VERSION."
        )
    current = matches[0].group(1)
    if not VERSION_PATTERN.fullmatch(current):
        raise ReleaseVersionError(
            f"Stávající APP_VERSION nemá formát X.Y.Z: {current!r}"
        )
    return current


def next_patch_version(current: str) -> str:
    if not VERSION_PATTERN.fullmatch(current):
        raise ReleaseVersionError(
            f"Stávající APP_VERSION nemá formát X.Y.Z: {current!r}"
        )
    major, minor, patch = current.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def _parse_app_name(version_source: str) -> str:
    match = APP_NAME_ASSIGNMENT.search(version_source)
    if match is None:
        raise ReleaseVersionError("V core/version.py chybí APP_NAME.")
    return match.group(1)


def _replace_app_version(version_source: str, new_version: str) -> str:
    return APP_VERSION_ASSIGNMENT.sub(
        f'APP_VERSION = "{new_version}"',
        version_source,
        count=1,
    )


def _update_readme(readme: str, app_name: str, old_version: str, new_version: str) -> str:
    old_heading = f"# {app_name} {old_version}"
    new_heading = f"# {app_name} {new_version}"
    if readme.startswith(new_heading):
        return readme
    if not readme.startswith(old_heading):
        raise ReleaseVersionError(
            "README.md nezačíná očekávaným nadpisem "
            f"{old_heading!r}."
        )
    return new_heading + readme[len(old_heading):]


def _changelog_has_version(changelog: str, version: str) -> bool:
    return re.search(
        rf"^# Verze {re.escape(version)}$",
        changelog,
        re.MULTILINE,
    ) is not None


def _insert_changelog_section(
    changelog: str,
    version: str,
    description: str,
    today: date,
) -> tuple[str, bool]:
    if _changelog_has_version(changelog, version):
        return changelog, False
    if CHANGELOG_INSERT_MARK not in changelog:
        raise ReleaseVersionError(
            "CHANGELOG.md nemá očekávanou značku '# Historie verzí'."
        )
    section = (
        f"# Verze {version}\n"
        "\n"
        "Datum vydání:\n"
        "\n"
        f"{_czech_date(today)}\n"
        "\n"
        f"{description}\n"
        "\n"
        "---\n"
        "\n"
    )
    return changelog.replace(CHANGELOG_INSERT_MARK, CHANGELOG_INSERT_MARK + section, 1), True


def _run_generator(root: Path, script_name: str) -> None:
    script = root / script_name
    env = os.environ.copy()
    pythonpath = str(root)
    existing = env.get("PYTHONPATH", "").strip()
    if existing:
        pythonpath = pythonpath + os.pathsep + existing
    env["PYTHONPATH"] = pythonpath
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        message = f"Generátor {script_name} selhal."
        if detail:
            message = f"{message}\n{detail}"
        raise ReleaseVersionError(message)


def _validate(
    root: Path,
    description: str,
) -> tuple[Path, Path, Path, Path, Path, str, str, str]:
    normalized_description = description.strip()
    if not normalized_description:
        raise ReleaseVersionError("Popis změny nesmí být prázdný.")

    version_path = root / "core" / "version.py"
    readme_path = root / "README.md"
    changelog_path = root / "CHANGELOG.md"
    version_info_path = root / "version_info.txt"
    installer_path = root / "installer.iss"

    _require_file(version_path, "zdroj verze")
    _require_file(readme_path, "README.md")
    _require_file(changelog_path, "CHANGELOG.md")
    for script_name in GENERATOR_SCRIPTS:
        _require_file(root / script_name, f"generátor {script_name}")

    version_source = _read_text(version_path)
    old_version = _parse_app_version(version_source)
    new_version = next_patch_version(old_version)
    app_name = _parse_app_name(version_source)
    readme = _read_text(readme_path)
    changelog = _read_text(changelog_path)

    _update_readme(readme, app_name, old_version, new_version)
    if CHANGELOG_INSERT_MARK not in changelog and not _changelog_has_version(
        changelog,
        new_version,
    ):
        raise ReleaseVersionError(
            "CHANGELOG.md nemá očekávanou značku '# Historie verzí'."
        )

    return (
        version_path,
        readme_path,
        changelog_path,
        version_info_path,
        installer_path,
        old_version,
        new_version,
        app_name,
    )


def prepare_release(
    description: str,
    *,
    project_root: Path | None = None,
    today: date | None = None,
) -> ReleasePreparation:
    root = (project_root or PROJECT_ROOT).resolve()
    release_date = today or date.today()
    normalized_description = description.strip()
    if not normalized_description:
        raise ReleaseVersionError("Popis změny nesmí být prázdný.")

    (
        version_path,
        readme_path,
        changelog_path,
        version_info_path,
        installer_path,
        old_version,
        new_version,
        app_name,
    ) = _validate(root, normalized_description)

    targets = [
        version_path,
        readme_path,
        changelog_path,
        version_info_path,
        installer_path,
    ]
    snapshots = _snapshot(targets)
    changelog_added = False
    try:
        version_source = _read_text(version_path)
        _write_text(version_path, _replace_app_version(version_source, new_version))
        _write_text(
            readme_path,
            _update_readme(_read_text(readme_path), app_name, old_version, new_version),
        )
        changelog, changelog_added = _insert_changelog_section(
            _read_text(changelog_path),
            new_version,
            normalized_description,
            release_date,
        )
        _write_text(changelog_path, changelog)
        for script_name in GENERATOR_SCRIPTS:
            _run_generator(root, script_name)

        generated_info = _read_text(version_info_path)
        generated_installer = _read_text(installer_path)
        setup_name = f"Manazer_BOZP_{new_version.replace('.', '_')}_Setup"
        if f"StringStruct('FileVersion', '{new_version}')" not in generated_info:
            raise ReleaseVersionError(
                "version_info.txt neobsahuje novou FileVersion."
            )
        if f'#define MyAppVersion "{new_version}"' not in generated_installer:
            raise ReleaseVersionError(
                "installer.iss neobsahuje novou MyAppVersion."
            )
        if f"OutputBaseFilename={setup_name}" not in generated_installer:
            raise ReleaseVersionError(
                "installer.iss neobsahuje očekávaný OutputBaseFilename."
            )
    except Exception:
        _restore(snapshots)
        raise

    return ReleasePreparation(
        old_version=old_version,
        new_version=new_version,
        changelog_added=changelog_added,
        updated_paths=tuple(targets),
    )


def format_report(result: ReleasePreparation, *, project_root: Path | None = None) -> str:
    root = (project_root or PROJECT_ROOT).resolve()
    lines = [
        "Release připraven:",
        f"  {result.old_version} → {result.new_version}",
        "",
        "Aktualizováno:",
    ]
    for path in result.updated_paths:
        suffix = ""
        if path.name == "CHANGELOG.md" and not result.changelog_added:
            suffix = " (sekce už existovala, nepřidáno)"
        lines.append(f"  {_relative(root, path)}{suffix}")
    lines.extend(
        [
            "",
            "Další krok:",
            "  zkontrolovat git diff a spustit release testy",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Zvýší poslední číslo verze Manažera BOZP o 1 a připraví pracovní strom."
        ),
    )
    parser.add_argument(
        "description",
        help="Stručný popis změny pro novou sekci CHANGELOG.md",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = prepare_release(args.description)
    except ReleaseVersionError as exc:
        print(f"Chyba: {exc}", file=sys.stderr)
        return 1
    print(format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
