"""Main list combining logic."""

from typing import List, Set, Optional
from pathlib import Path

class ListCombiner:
    """Combine multiple blocklists into one."""
    
    def __init__(self):
        self.lists: List[str] = []
        self.combined: Set[str] = set()
        self.stats = {
            "total_lines": 0,
            "domains_added": 0,
            "lists_processed": 0
        }
    
    def add_list(self, content: str, source: str = "unknown") -> int:
        """
        Add a blocklist content.
        
        Args:
            content: The blocklist content as string
            source: Source identifier for stats
            
        Returns:
            Number of domains added from this list
        """
        lines = content.splitlines()
        self.stats["total_lines"] += len(lines)
        
        # Filter out comments and empty lines
        domains = set()
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('#', '!', '[')):
                # Handle different Pi-hole list formats
                if line.startswith('0.0.0.0 '):
                    domain = line.replace('0.0.0.0 ', '').strip()
                elif line.startswith('127.0.0.1 '):
                    domain = line.replace('127.0.0.1 ', '').strip()
                else:
                    domain = line
                
                # Remove any trailing comments
                if '#' in domain:
                    domain = domain.split('#')[0].strip()
                    
                if domain:
                    domains.add(domain)
        
        before_count = len(self.combined)
        self.combined.update(domains)
        added = len(self.combined) - before_count
        
        self.stats["domains_added"] += added
        self.stats["lists_processed"] += 1
        
        return added
    
    def get_combined(self, include_header: bool = True) -> str:
        """
        Get combined list as string.
        
        Args:
            include_header: Whether to include Pi-hole header
            
        Returns:
            Combined list as string
        """
        lines = []
        
        if include_header:
            lines.extend([
                "# Pi-hole Combined Blocklist",
                f"# Generated: {__import__('datetime').datetime.now()}",
                f"# Total domains: {len(self.combined)}",
                f"# Lists combined: {self.stats['lists_processed']}",
                ""
            ])
        
        lines.extend(sorted(self.combined))
        return '\n'.join(lines)
    
    def save(self, filename: str, include_header: bool = True) -> None:
        """
        Save combined list to file.
        
        Args:
            filename: Output file path
            include_header: Whether to include header
        """
        content = self.get_combined(include_header)
        Path(filename).write_text(content)
        print(f"Saved {len(self.combined)} domains to {filename}")
    
    def clear(self) -> None:
        """Clear all lists and reset stats."""
        self.lists.clear()
        self.combined.clear()
        self.stats = {
            "total_lines": 0,
            "domains_added": 0,
            "lists_processed": 0
        }
    
    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {
            **self.stats,
            "unique_domains": len(self.combined)
        }