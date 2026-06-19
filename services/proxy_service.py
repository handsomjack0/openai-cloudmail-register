from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


def normalize_proxy_url(url: str) -> str:
    candidate = str(url or "").strip()
    if candidate and "://" not in candidate and ":" in candidate:
        candidate = f"http://{candidate}"
    lowered = candidate.lower()
    if lowered.startswith("socks://"):
        return "socks5h://" + candidate[len("socks://") :]
    if lowered.startswith("socks5://"):
        return "socks5h://" + candidate[len("socks5://") :]
    return candidate


@dataclass(frozen=True)
class ClearanceBundle:
    target_host: str = ""
    proxy_url: str = ""
    cookies: dict[str, str] = field(default_factory=dict)
    user_agent: str = ""


@dataclass(frozen=True)
class ProxyRuntimeProfile:
    proxy_url: str = ""
    clearance_enabled: bool = False


class ProxySettings:
    def get_profile(self, proxy: str = "", **_: object) -> ProxyRuntimeProfile:
        return ProxyRuntimeProfile(proxy_url=normalize_proxy_url(proxy), clearance_enabled=False)

    def build_session_kwargs(self, proxy: str = "", **session_kwargs: object) -> dict[str, object]:
        session_kwargs.pop("account", None)
        session_kwargs.pop("resource", None)
        session_kwargs.pop("upstream", None)
        proxy_url = normalize_proxy_url(proxy)
        if proxy_url:
            session_kwargs["proxy"] = proxy_url
        return session_kwargs

    def build_headers(self, headers: dict | None = None, **_: object) -> dict:
        return dict(headers or {})

    def refresh_clearance(self, target_url: str = "", proxy: str = "", **_: object) -> ClearanceBundle | None:
        parsed = urlparse(str(target_url or ""))
        return ClearanceBundle(target_host=parsed.hostname or "", proxy_url=normalize_proxy_url(proxy))


proxy_settings = ProxySettings()
