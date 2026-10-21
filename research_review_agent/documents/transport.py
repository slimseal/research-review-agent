"""Public HTTPS only, pinned DNS resolution, no proxies/cookies/credentials."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit, urlunsplit

from .contracts import DocumentError

MAX_BYTES = 25 * 1024 * 1024


def clean_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or any(ord(c) < 33 for c in url)
                or "\\" in url or "%" in parts.netloc):
            raise ValueError()
        forbidden = ("token", "key", "secret", "password", "signature", "credential", "auth")
        if any(any(word in key.lower() for word in forbidden) for key, _ in parse_qsl(parts.query)):
            raise DocumentError("CREDENTIAL_URL_UNSUPPORTED", "Use a public URL without embedded credentials or signed tokens.")
        if ".." in unquote(parts.path).split("/"):
            raise ValueError()
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    except ValueError as exc:
        if isinstance(exc, DocumentError):
            raise
        raise DocumentError("UNSAFE_URL", "Only public HTTPS URLs on port 443 without credentials or traversal are supported.") from None


def public_addresses(host: str) -> list[str]:
    try:
        addresses = list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    except OSError:
        raise DocumentError("NETWORK_UNAVAILABLE", "DNS resolution failed; check the public hostname and network.") from None
    parsed = [ipaddress.ip_address(ip) for ip in addresses]
    if not addresses or any(not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local for ip in parsed):
        raise DocumentError("UNSAFE_DESTINATION", "Local, private, reserved or mixed public/private DNS destinations are blocked.")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, timeout: float):
        super().__init__(hostname, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class SecureTransport:
    def __init__(self, timeout: float = 20, max_bytes: int = MAX_BYTES, max_redirects: int = 4):
        self.timeout, self.max_bytes, self.max_redirects = timeout, max_bytes, max_redirects

    def get(self, url: str, *, pdf: bool = False) -> dict:
        current = clean_url(url)
        redirects = []
        deadline = time.monotonic() + self.timeout
        for _ in range(self.max_redirects + 1):
            parts = urlsplit(current)
            addresses = public_addresses(parts.hostname)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DocumentError("TIMEOUT", "Request time budget exhausted; retry later.")
            connection = PinnedHTTPS(parts.hostname, addresses[0], remaining)
            try:
                path = urlunsplit(("", "", parts.path, parts.query, ""))
                connection.request("GET", path, headers={"User-Agent": "ResearchReviewAgent-document-tools/1.0", "Accept": "application/pdf" if pdf else "text/html", "Accept-Encoding": "identity"})
                response = connection.getresponse()
                status = response.status
                if status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise DocumentError("INVALID_REDIRECT", "Redirect has no Location header.", status)
                    current = clean_url(urljoin(current, location))
                    redirects.append(current)
                    continue
                if status != 200:
                    code = {401: "AUTHENTICATION_REQUIRED", 403: "ACCESS_FORBIDDEN", 404: "FULLTEXT_NOT_FOUND", 429: "HTTP_RATE_LIMITED"}.get(status, "HTTP_SERVER_ERROR" if status >= 500 else "HTTP_ERROR")
                    raise DocumentError(code, "Public access failed. Respect provider restrictions; retry later or use an authorized local PDF.", status)
                mime = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
                if pdf and mime not in {"application/pdf", "application/octet-stream"}:
                    raise DocumentError("NOT_PDF_CONTENT_TYPE", "Response is not a PDF; it may be a landing/login page.", status)
                if response.getheader("Content-Encoding", "identity") != "identity":
                    raise DocumentError("UNSUPPORTED_ENCODING", "Compressed HTTP response is unsupported.", status)
                length = response.getheader("Content-Length")
                try:
                    expected = int(length) if length is not None else None
                except ValueError:
                    raise DocumentError("MALFORMED_RESPONSE", "Invalid content length.", status) from None
                if expected is not None and (expected < 0 or expected > self.max_bytes):
                    raise DocumentError("FILE_TOO_LARGE", "Response exceeds the configured size limit.", status)
                data = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DocumentError("TIMEOUT", "Download time budget exhausted.", status)
                    if connection.sock:
                        connection.sock.settimeout(remaining)
                    block = response.read(min(65536, self.max_bytes + 1 - len(data)))
                    if not block:
                        break
                    data.extend(block)
                    if len(data) > self.max_bytes:
                        raise DocumentError("FILE_TOO_LARGE", "Streaming response exceeds the size limit.", status)
                if expected is not None and len(data) != expected:
                    raise DocumentError("DOWNLOAD_INTERRUPTED", "Body length does not match Content-Length; no PDF was registered.", status)
                if pdf and not data.startswith(b"%PDF-"):
                    raise DocumentError("INVALID_PDF_SIGNATURE", "Response does not begin with a PDF signature.", status)
                return {"data": bytes(data), "final_url": current, "redirects": redirects, "http_status": status, "mime_type": mime, "sha256": hashlib.sha256(data).hexdigest()}
            except DocumentError:
                raise
            except (TimeoutError, socket.timeout):
                raise DocumentError("TIMEOUT", "Request timed out; no complete document registered.") from None
            except (OSError, http.client.HTTPException):
                raise DocumentError("NETWORK_INTERRUPTED", "Connection or TLS validation failed; no complete document registered.") from None
            finally:
                connection.close()
        raise DocumentError("TOO_MANY_REDIRECTS", "Redirect limit reached; inspect the source manually.")
