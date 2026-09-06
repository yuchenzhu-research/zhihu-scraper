"""Runtime platform differences behind one stable interface."""

from __future__ import annotations

import ntpath
import os
import platform as system_platform
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath


class UnsupportedPlatformError(RuntimeError):
    """Raised when the runtime cannot provide a supported platform adapter."""


class ArchivePathError(ValueError):
    """An archive cannot fit within portable Windows path limits."""


class OperatingSystem(StrEnum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


@dataclass(frozen=True, slots=True)
class RuntimePlatform:
    operating_system: OperatingSystem
    user_data_directory: PurePath
    browser_candidates: tuple[PurePath, ...]

    def archive_name_budget(self, root: PurePath, *, media_download: bool = True) -> int | None:
        """Reserve enough absolute-path space for generated titles and temporary files."""

        if self.operating_system is not OperatingSystem.WINDOWS:
            return None
        remaining = 259 - _windows_path_units(root)
        # Two title components, /回答片段/ (the deepest recovery directory),
        # and .html's atomic-write suffix; /内容/ is shorter.
        budget = (remaining - 17) // 2
        if media_download:
            # Keep existing media identities: 64 ASCII filename characters,
            # /media/, and the longest .part.resume.tmp suffix.
            budget = min(budget, remaining - 88)
        if budget < 16:
            raise ArchivePathError(
                "Windows 保存目录过深，无法为正文和媒体预留安全路径；"
                "请缩短 archive.output_dir 后重试。"
            )
        return budget

    def validate_archive_path(self, path: PurePath, *, extra_units: int = 0) -> None:
        """Check existing names without renaming files or changing their identity."""

        if self.operating_system is not OperatingSystem.WINDOWS:
            return
        if _windows_path_units(path) + extra_units > 259:
            raise ArchivePathError(
                "Windows 归档路径过长，无法安全写入正文、媒体或临时文件；"
                "请将现有归档移到更短的保存目录后重试。"
            )

    def secure_private_file(self, path: Path) -> None:
        """Restrict a newly created temporary credential file before writing secrets."""
        if self.operating_system is not OperatingSystem.WINDOWS:
            os.chmod(path, 0o600)
            return
        system_directory = PureWindowsPath(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
        try:
            identity = subprocess.run(
                [str(system_directory / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            sid = re.search(r"S-1-(?:\d+-)+\d+", identity.stdout)
            if sid is None:
                raise OSError("无法确认当前 Windows 用户权限。")
            subprocess.run(
                [
                    str(system_directory / "icacls.exe"),
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"*{sid.group()}:F",
                    "/Q",
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            raise OSError("无法为 Cookie 临时文件设置当前用户专属权限，未保存凭证。") from None

    @classmethod
    @cache
    def detect(cls) -> RuntimePlatform:
        """Detect and retain the process-wide platform adapter."""
        return cls.for_system(
            system_platform.system(),
            home_directory=Path.home(),
            environment=os.environ,
        )

    @classmethod
    def for_system(
        cls,
        system_name: str,
        *,
        home_directory: PurePath,
        environment: Mapping[str, str],
    ) -> RuntimePlatform:
        normalized_name = system_name.casefold()
        if normalized_name == "darwin":
            home = PurePosixPath(home_directory)
            return cls(
                operating_system=OperatingSystem.MACOS,
                user_data_directory=home / "Library" / "Application Support" / "zhihu-scraper",
                browser_candidates=(
                    PurePosixPath("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                    home
                    / "Applications"
                    / "Google Chrome.app"
                    / "Contents"
                    / "MacOS"
                    / "Google Chrome",
                    PurePosixPath("/Applications/Chromium.app/Contents/MacOS/Chromium"),
                ),
            )
        if normalized_name == "linux":
            home = PurePosixPath(home_directory)
            data_home = PurePosixPath(
                environment.get("XDG_DATA_HOME", str(home / ".local" / "share"))
            )
            return cls(
                operating_system=OperatingSystem.LINUX,
                user_data_directory=data_home / "zhihu-scraper",
                browser_candidates=(
                    PurePosixPath("/usr/bin/google-chrome"),
                    PurePosixPath("/usr/bin/google-chrome-stable"),
                    PurePosixPath("/usr/bin/chromium"),
                    PurePosixPath("/usr/bin/chromium-browser"),
                    PurePosixPath("/snap/bin/chromium"),
                ),
            )
        if normalized_name != "windows":
            raise UnsupportedPlatformError(
                f"Unsupported operating system {system_name!r}; "
                "supported systems are Windows, macOS, and Linux"
            )

        windows_home = PureWindowsPath(home_directory)
        local_app_data = PureWindowsPath(
            environment.get("LOCALAPPDATA", str(windows_home / "AppData" / "Local"))
        )
        program_files = PureWindowsPath(environment.get("PROGRAMFILES", "C:/Program Files"))
        program_files_x86 = PureWindowsPath(
            environment.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")
        )

        return cls(
            operating_system=OperatingSystem.WINDOWS,
            user_data_directory=local_app_data / "ZhihuScraper",
            browser_candidates=(
                local_app_data / "Google" / "Chrome" / "Application" / "chrome.exe",
                program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
                program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
                local_app_data / "Chromium" / "Application" / "chrome.exe",
            ),
        )


def _windows_path_units(path: PurePath) -> int:
    absolute = path if path.is_absolute() else Path(path).expanduser().resolve()
    return len(ntpath.normpath(str(absolute)).encode("utf-16-le")) // 2
