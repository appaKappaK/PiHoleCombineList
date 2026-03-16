"""Tests for ListParser."""

import pytest
from piholecombinelist.parser import ListParser


@pytest.fixture
def parser():
    return ListParser()


def test_plain_domain(parser):
    assert parser.parse_line("example.com") == "example.com"


def test_plain_domain_lowercased(parser):
    assert parser.parse_line("EXAMPLE.COM") == "example.com"


def test_ip_prefix_0000(parser):
    assert parser.parse_line("0.0.0.0 tracker.com") == "tracker.com"


def test_ip_prefix_127(parser):
    assert parser.parse_line("127.0.0.1 ads.example.com") == "ads.example.com"


def test_comment_line_hash(parser):
    assert parser.parse_line("# this is a comment") is None


def test_comment_line_bang(parser):
    assert parser.parse_line("! adblock comment") is None


def test_comment_line_bracket(parser):
    assert parser.parse_line("[Adblock Plus]") is None


def test_empty_line(parser):
    assert parser.parse_line("") is None


def test_whitespace_only(parser):
    assert parser.parse_line("   ") is None


def test_inline_comment_stripped(parser):
    assert parser.parse_line("bad-site.org # this is bad") == "bad-site.org"


def test_ip_prefix_with_inline_comment(parser):
    assert parser.parse_line("0.0.0.0 spyware.net # spy") == "spyware.net"


def test_invalid_domain_bare_ip(parser):
    assert parser.parse_line("192.168.1.1") is None


def test_invalid_domain_no_tld(parser):
    assert parser.parse_line("localhost") is None


def test_subdomain(parser):
    assert parser.parse_line("sub.domain.example.co.uk") == "sub.domain.example.co.uk"


# ABP/AdGuard format (||domain^)

def test_abp_rule_basic(parser):
    assert parser.parse_line("||example.com^") == "example.com"


def test_abp_rule_with_options(parser):
    assert parser.parse_line("||example.com^$third-party") == "example.com"


def test_abp_rule_with_path(parser):
    assert parser.parse_line("||example.com/ads^") == "example.com"


def test_abp_rule_subdomain(parser):
    assert parser.parse_line("||ads.example.co.uk^") == "ads.example.co.uk"


def test_single_pipe_skipped(parser):
    assert parser.parse_line("|http://example.com|") is None


# Pipe delimiter in plain domain lines

def test_pipe_delimiter_stripped(parser):
    assert parser.parse_line("bad-site.org | ") == "bad-site.org"
