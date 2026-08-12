"""Central settings for the CSCEC UI automation project."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from .environments import ENVIRONMENTS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
_ENV_VALUES = {}
if ENV_FILE.exists():
    _ENV_VALUES = {key: value for key, value in dotenv_values(ENV_FILE).items() if value is not None}
else:
    EXAMPLE_ENV_FILE = PROJECT_ROOT / ".env.example"
    if EXAMPLE_ENV_FILE.exists():
        _ENV_VALUES = {key: value for key, value in dotenv_values(EXAMPLE_ENV_FILE).items() if value is not None}


def _read_setting(name: str, default: str = "", env_preferred: bool = False) -> str:
    if env_preferred:
        return os.getenv(name) or _ENV_VALUES.get(name, default)
    return _ENV_VALUES.get(name) or os.getenv(name, default)


def _read_bool(name: str, default: str = "true") -> bool:
    return _read_setting(name, default, env_preferred=True).lower() in ("true", "1", "yes")


@dataclass
class Settings:
    """Runtime settings shared by tests and page objects."""

    ENV: str = "uat"
    BASE_URL: str = ""
    DOC_CENTER_URL: str = ""

    USERNAME: str = ""
    PASSWORD: str = ""
    UAT_PASSWORD: str = ""
    PRE_PASSWORD: str = ""
    PROD_PASSWORD: str = ""

    HEADLESS: bool = True
    SLOW_MO: int = 0
    VIEWPORT: dict = field(default_factory=lambda: {"width": 1920, "height": 1080})
    BROWSER_CHANNEL: str = "chrome"

    NAVIGATION_TIMEOUT: int = 60000
    ACTION_TIMEOUT: int = 15000
    DEFAULT_TIMEOUT: int = 5000

    NETWORK_RETRY_MAX: int = 3
    NETWORK_RETRY_BASE_DELAY: int = 30

    PROJECT_ROOT: Path = field(default_factory=lambda: PROJECT_ROOT)
    SCREENSHOTS_DIR: Path = field(default_factory=lambda: PROJECT_ROOT / "screenshots")
    LOGS_DIR: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    REPORTS_DIR: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    AUTH_STATES_DIR: Path = field(default_factory=lambda: PROJECT_ROOT / "auth_states")

    @classmethod
    def from_env(cls) -> "Settings":
        env = _read_setting("ENV", "uat", env_preferred=True).lower()
        if env not in ENVIRONMENTS:
            raise ValueError(f"Invalid ENV '{env}', expected one of {list(ENVIRONMENTS.keys())}")

        env_urls = ENVIRONMENTS[env]
        return cls(
            ENV=env,
            BASE_URL=env_urls["BASE_URL"],
            DOC_CENTER_URL=env_urls["DOC_CENTER_URL"],
            USERNAME=_read_setting("USERNAME", ""),
            PASSWORD=_read_setting("PASSWORD", ""),
            UAT_PASSWORD=_read_setting("UAT_PASSWORD", ""),
            PRE_PASSWORD=_read_setting("PRE_PASSWORD", ""),
            PROD_PASSWORD=_read_setting("PROD_PASSWORD", ""),
            HEADLESS=_read_bool("HEADLESS"),
            SLOW_MO=int(_read_setting("SLOW_MO", "0", env_preferred=True)),
            BROWSER_CHANNEL=_read_setting("BROWSER_CHANNEL", "chrome", env_preferred=True),
            NAVIGATION_TIMEOUT=int(_read_setting("NAVIGATION_TIMEOUT", "60000", env_preferred=True)),
            ACTION_TIMEOUT=int(_read_setting("ACTION_TIMEOUT", "15000", env_preferred=True)),
            DEFAULT_TIMEOUT=int(_read_setting("DEFAULT_TIMEOUT", "5000", env_preferred=True)),
            NETWORK_RETRY_MAX=int(_read_setting("NETWORK_RETRY_MAX", "3", env_preferred=True)),
            NETWORK_RETRY_BASE_DELAY=int(_read_setting("NETWORK_RETRY_BASE_DELAY", "30", env_preferred=True)),
        )

    def __post_init__(self) -> None:
        for directory in (
            self.SCREENSHOTS_DIR,
            self.LOGS_DIR,
            self.REPORTS_DIR,
            self.AUTH_STATES_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def env_label(self) -> str:
        return {"prod": "PROD", "pre": "PRE", "uat": "UAT"}.get(self.ENV, self.ENV.upper())

    @property
    def effective_password(self) -> str:
        env_passwords = {
            "uat": self.UAT_PASSWORD,
            "pre": self.PRE_PASSWORD,
            "prod": self.PROD_PASSWORD,
        }
        return env_passwords.get(self.ENV) or self.PASSWORD

    @property
    def auth_state_file(self) -> Path:
        return self.AUTH_STATES_DIR / f"{self.ENV}.json"


settings = Settings.from_env()
