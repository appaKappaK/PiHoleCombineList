"""Tests for the combiner module."""

import pytest
from pathlib import Path
from src.piholecombinelist.combiner import ListCombiner

def test_combiner_initialization():
    """Test combiner initializes correctly."""
    combiner = ListCombiner()
    assert combiner.combined == set()
    assert combiner.stats["lists_processed"] == 0

def test_add_simple_list():
    """Test adding a simple domain list."""
    combiner = ListCombiner()
    
    test_list = """
example.com
tracker.com
ads.com
"""
    
    added = combiner.add_list(test_list)
    assert added == 3
    assert len(combiner.combined) == 3
    assert "example.com" in combiner.combined

def test_add_list_with_comments():
    """Test adding list with comments."""
    combiner = ListCombiner()
    
    test_list = """
# This is a comment
example.com
! Another comment
tracker.com
[Adblock Plus 2.0]
ads.com
"""
    
    added = combiner.add_list(test_list)
    assert added == 3
    assert "#" not in str(combiner.combined)

def test_add_list_with_ip_format():
    """Test adding list with IP prefix format."""
    combiner = ListCombiner()
    
    test_list = """
0.0.0.0 example.com
127.0.0.1 tracker.com
0.0.0.0 ads.com # with comment
"""
    
    added = combiner.add_list(test_list)
    assert added == 3
    assert "example.com" in combiner.combined
    assert "tracker.com" in combiner.combined

def test_duplicate_domains():
    """Test duplicate domains are handled correctly."""
    combiner = ListCombiner()
    
    list1 = "example.com\ntracker.com\n"
    list2 = "example.com\nads.com\n"
    
    combiner.add_list(list1)
    combiner.add_list(list2)
    
    assert len(combiner.combined) == 3
    assert combiner.stats["domains_added"] == 3

def test_get_combined_with_header():
    """Test getting combined list with header."""
    combiner = ListCombiner()
    combiner.add_list("example.com")
    
    result = combiner.get_combined(include_header=True)
    assert "# Pi-hole Combined Blocklist" in result
    assert "example.com" in result

def test_save_to_file(tmp_path):
    """Test saving to file."""
    combiner = ListCombiner()
    combiner.add_list("example.com")
    
    output_file = tmp_path / "combined.txt"
    combiner.save(str(output_file))
    
    assert output_file.exists()
    content = output_file.read_text()
    assert "example.com" in content