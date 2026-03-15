"""Command-line interface for Pi-hole Combine List."""

import click
from pathlib import Path
from typing import Optional

from .combiner import ListCombiner
from .fetcher import ListFetcher
from .deduplicator import Deduplicator
from . import __version__

@click.command()
@click.version_option(version=__version__)
@click.argument('sources', nargs=-1, required=True)
@click.option('-o', '--output', default='combined.txt', 
              help='Output file path (default: combined.txt)')
@click.option('--no-header', is_flag=True, 
              help='Don\'t include header in output')
@click.option('--timeout', default=30, 
              help='Timeout for URL fetches in seconds (default: 30)')
@click.option('--save-failed', is_flag=True,
              help='Save failed URLs to a file')
def main(sources, output, no_header, timeout, save_failed):
    """
    Combine multiple Pi-hole blocklists into one.
    
    SOURCES can be URLs or local file paths. Example:
    
    \b
    pihole-combine https://example.com/list.txt local-list.txt -o combined.txt
    """
    click.echo(f"Pi-hole Combine List v{__version__}")
    click.echo(f"Processing {len(sources)} sources...")
    
    # Initialize components
    fetcher = ListFetcher(timeout=timeout)
    combiner = ListCombiner()
    
    # Fetch all lists
    successful = 0
    failed_urls = []
    
    with click.progressbar(sources, label='Fetching lists') as bar:
        for source in bar:
            if source.startswith(('http://', 'https://')):
                content = fetcher.fetch_url(source)
            else:
                content = fetcher.fetch_file(source)
            
            if content:
                domains_added = combiner.add_list(content, source)
                successful += 1
                if domains_added > 0:
                    click.echo(f"  Added {domains_added} domains from {source}", err=True)
            else:
                failed_urls.append(source)
    
    # Save failed URLs if requested
    if save_failed and failed_urls:
        failed_file = 'failed_sources.txt'
        Path(failed_file).write_text('\n'.join(failed_urls))
        click.echo(f"Failed sources saved to {failed_file}")
    
    # Save combined list
    combiner.save(output, include_header=not no_header)
    
    # Show stats
    stats = combiner.get_stats()
    fetch_stats = fetcher.get_stats()
    
    click.echo("\nSummary:")
    click.echo(f"  Lists processed: {stats['lists_processed']}")
    click.echo(f"  Successful fetches: {fetch_stats['successful']}")
    click.echo(f"  Failed fetches: {fetch_stats['failed']}")
    click.echo(f"  Total lines read: {stats['total_lines']}")
    click.echo(f"  Unique domains: {stats['unique_domains']}")
    click.echo(f"  Output saved to: {output}")

if __name__ == '__main__':
    main()