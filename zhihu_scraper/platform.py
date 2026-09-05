"""Runtime platform differences behind one stable interface."""

from __future__ import annotations

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


class OperatingSystem(StrEnum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


@dataclass(frozen=True, slots=True)
class RuntimePlatform:
    operating_system: OperatingSystem
    user_data_directory: PurePath
    browser_candidates: tuple[PurePath, ...]

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
