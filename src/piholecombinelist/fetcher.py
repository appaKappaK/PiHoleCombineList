"""Fetch blocklists from URLs or local files."""

import requests
from typing import List, Optional, Union
from pathlib import Path
import time

class ListFetcher:
    """Fetch blocklists from various sources."""
    
    def __init__(self, timeout: int = 30, user_agent: Optional[str] = None):
        """
        Initialize fetcher.
        
        Args:
            timeout: Request timeout in seconds
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.user_agent = user_agent or "PiHoleCombineList/0.1.0"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.stats = {
            "successful": 0,
            "failed": 0,
            "total_bytes": 0
        }
    
    def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch a blocklist from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Content as string or None if failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            content = response.text
            self.stats["successful"] += 1
            self.stats["total_bytes"] += len(content)
            
            return content
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            self.stats["failed"] += 1
            return None
    
    def fetch_file(self, path: Union[str, Path]) -> Optional[str]:
        """
        Read a blocklist from local file.
        
        Args:
            path: Path to local file
            
        Returns:
            Content as string or None if failed
        """
        try:
            path = Path(path)
            content = path.read_text()
            self.stats["successful"] += 1
            self.stats["total_bytes"] += len(content)
            return content
            
        except Exception as e:
            print(f"Failed to read {path}: {e}")
            self.stats["failed"] += 1
            return None
    
    def fetch_multiple(self, sources: List[str]) -> List[str]:
        """
        Fetch multiple blocklists.
        
        Args:
            sources: List of URLs or file paths
            
        Returns:
            List of successful content strings
        """
        results = []
        
        for source in sources:
            if source.startswith(('http://', 'https://')):
                content = self.fetch_url(source)
            else:
                content = self.fetch_file(source)
            
            if content:
                results.append(content)
            
            # Small delay to be nice to servers
            time.sleep(0.5)
        
        return results
    
    def get_stats(self) -> dict:
        """Get fetch statistics."""
        return self.stats.copy()