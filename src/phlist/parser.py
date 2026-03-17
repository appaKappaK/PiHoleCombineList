"""Parse individual lines from blocklist files into clean domain entries."""
# v1.1.2

import re
from typing import Optional

# Matches a valid domain: labels separated by dots, each label alphanumeric + hyphens
_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)

# IP prefixes used in hosts-file style blocklists
_IP_PREFIXES = ("0.0.0.0 ", "127.0.0.1 ")


class ListParser:
    """Extract and validate domain names from blocklist lines."""

    def parse_line(self, line: str) -> Optional[str]:
        """
        Extract a domain from a single blocklist line.

        Supported formats:
        - Plain domain:           ``example.com``
        - Hosts-file:             ``0.0.0.0 example.com`` / ``127.0.0.1 example.com``
        - ABP/AdGuard rule:       ``||example.com^``  (with optional options/path)
        - Inline comment:         ``example.com # remark``
        - Pipe delimiter:         ``example.com | remark``

        Returns the domain string if valid, None if the line should be skipped.
        """
        line = line.strip()

        # Skip empty lines and comment/marker lines
        if not line or line[0] in ("#", "!", "["):
            return None

        # ABP/AdGuard-style rule: ||domain^[options]
        if line.startswith("||"):
            line = line[2:]  # strip leading ||
            # Strip from first separator (^ or /) — options/path start here
            for sep in ("^", "/"):
                if sep in line:
                    line = line.split(sep, 1)[0]
            line = line.strip()

        elif line[0] == "|":
            # Single-pipe lines (URL anchors, etc.) are not domain rules
            return None

        else:
            # Strip IP prefix (hosts-file format)
            for prefix in _IP_PREFIXES:
                if line.startswith(prefix):
                    line = line[len(prefix):]
                    break

            # Strip inline comment (#) and pipe delimiter (|)
            for delimiter in ("#", "|"):
                if delimiter in line:
                    line = line.split(delimiter, 1)[0].strip()

        if not line:
            return None

        domain = line.lower()

        if not _DOMAIN_RE.match(domain):
            return None

        return domain
