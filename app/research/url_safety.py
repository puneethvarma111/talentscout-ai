from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class URLSafetyError(ValueError):
    pass


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise URLSafetyError("Only http and https URLs are allowed")
    if not parsed.netloc:
        raise URLSafetyError("Invalid URL")
    host = parsed.hostname
    if not host:
        raise URLSafetyError("Missing hostname")
    lowered = host.lower()
    if lowered in ("localhost", "127.0.0.1", "::1") or lowered.endswith(".local"):
        raise URLSafetyError("Local URLs are not allowed")
    try:
        addr = ipaddress.ip_address(lowered.strip("[]"))
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise URLSafetyError("Private or reserved addresses are not allowed")
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise URLSafetyError("URL resolves to a private or reserved address")
    except socket.gaierror:
        pass
    return url.strip()
