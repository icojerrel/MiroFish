"""
Scraper Service — powered by Scrapling
Fetches web content and converts it to clean text for MiroFish graph building.

Three fetcher modes (selected automatically or by caller):
  basic    — fast HTTP with TLS fingerprint impersonation (most sites)
  stealthy — anti-bot bypass, Cloudflare Turnstile support
  dynamic  — full browser (Playwright/Chromium) for JS-heavy sites

The output is plain text ready to be appended to a project's extracted_text
and fed into the Zep graph building pipeline.
"""

import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.scraper')

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScrapeResult:
    url: str
    title: str
    text: str
    word_count: int
    mode: str          # basic | stealthy | dynamic
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'url': self.url,
            'title': self.title,
            'word_count': self.word_count,
            'mode': self.mode,
            'success': self.success,
            'error': self.error,
        }


@dataclass
class CrawlResult:
    start_url: str
    pages_scraped: int
    total_words: int
    combined_text: str
    pages: list = field(default_factory=list)  # list of ScrapeResult.to_dict()
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'start_url': self.start_url,
            'pages_scraped': self.pages_scraped,
            'total_words': self.total_words,
            'success': self.success,
            'error': self.error,
            'pages': self.pages,
        }


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------

def _html_to_text(page) -> tuple[str, str]:
    """Extract (title, body_text) from a Scrapling page object."""
    try:
        title_el = page.css('title')
        title = title_el[0].text.strip() if title_el else ''
    except Exception:
        title = ''

    # Remove script/style/nav/footer noise
    noise_tags = ['script', 'style', 'nav', 'footer', 'header', 'aside',
                  'noscript', 'iframe', 'svg', 'form']
    for tag in noise_tags:
        try:
            for el in page.css(tag):
                el.remove()  # Scrapling Selector.remove() if available
        except Exception:
            pass

    # Try main content containers first
    body_text = ''
    for selector in ['main', 'article', '[role="main"]', '.content', '#content', 'body']:
        try:
            els = page.css(selector)
            if els:
                body_text = ' '.join(e.text for e in els).strip()
                break
        except Exception:
            continue

    if not body_text:
        try:
            body_text = page.get_all_text(separator='\n').strip()
        except Exception:
            body_text = str(page)

    # Collapse excessive whitespace
    body_text = re.sub(r'\n{3,}', '\n\n', body_text)
    body_text = re.sub(r'[ \t]{2,}', ' ', body_text)

    return title, body_text.strip()


def _format_scraped_block(url: str, title: str, text: str) -> str:
    """Wrap scraped text in a clear document block for graph building."""
    domain = urlparse(url).netloc
    header = f'=== SOURCE: {title or domain} ===\nURL: {url}\n'
    return header + text + '\n\n'


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _get_fetcher(mode: str):
    """Import and return a Scrapling fetcher for the requested mode."""
    try:
        if mode == 'dynamic':
            from scrapling.fetchers import DynamicFetcher
            return DynamicFetcher
        elif mode == 'stealthy':
            from scrapling.fetchers import StealthyFetcher
            return StealthyFetcher
        else:
            from scrapling.fetchers import Fetcher
            return Fetcher
    except ImportError as exc:
        raise RuntimeError(
            f'Scrapling not installed. Run: pip install scrapling\n{exc}'
        )


def _auto_mode(url: str) -> str:
    """Heuristically pick a fetch mode based on the URL."""
    domain = urlparse(url).netloc.lower()
    # Known JS-heavy or bot-protected domains
    dynamic_hints = ['twitter.com', 'x.com', 'linkedin.com', 'instagram.com']
    stealthy_hints = ['bloomberg.com', 'ft.com', 'wsj.com', 'reuters.com',
                      'cloudflare', 'nytimes.com']
    if any(h in domain for h in dynamic_hints):
        return 'dynamic'
    if any(h in domain for h in stealthy_hints):
        return 'stealthy'
    return 'basic'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ScraperService:
    """Fetch and clean web content for MiroFish graph building."""

    MAX_TEXT_PER_PAGE = int(Config.SCRAPER_MAX_TEXT_PER_PAGE
                            if hasattr(Config, 'SCRAPER_MAX_TEXT_PER_PAGE') else 50_000)

    # ------------------------------------------------------------------
    # Single URL
    # ------------------------------------------------------------------

    def fetch_url(self, url: str, mode: str = 'auto') -> ScrapeResult:
        """
        Fetch a single URL and return clean text.

        Args:
            url:  Target URL
            mode: 'auto' | 'basic' | 'stealthy' | 'dynamic'
        """
        if mode == 'auto':
            mode = _auto_mode(url)

        logger.info(f'Scraping [{mode}]: {url}')
        try:
            Fetcher = _get_fetcher(mode)
            page = Fetcher.get(url, stealthy_headers=True, timeout=30)
            title, text = _html_to_text(page)
            text = text[:self.MAX_TEXT_PER_PAGE]
            word_count = len(text.split())
            logger.info(f'Scraped {word_count} words from {url}')
            return ScrapeResult(
                url=url, title=title, text=text,
                word_count=word_count, mode=mode, success=True,
            )
        except Exception as exc:
            logger.warning(f'Scrape failed [{url}]: {exc}')
            return ScrapeResult(
                url=url, title='', text='', word_count=0,
                mode=mode, success=False, error=str(exc),
            )

    # ------------------------------------------------------------------
    # Multiple URLs → combined text block
    # ------------------------------------------------------------------

    def fetch_urls(
        self,
        urls: list[str],
        mode: str = 'auto',
        progress_callback=None,
    ) -> CrawlResult:
        """
        Fetch multiple URLs and return combined clean text.

        Args:
            urls:              List of URLs to scrape
            mode:              Fetcher mode (auto/basic/stealthy/dynamic)
            progress_callback: Optional fn(done, total, url)
        """
        pages = []
        combined_parts = []
        total = len(urls)

        for i, url in enumerate(urls):
            result = self.fetch_url(url, mode=mode)
            pages.append(result.to_dict())
            if result.success and result.text:
                block = _format_scraped_block(url, result.title, result.text)
                combined_parts.append(block)
            if progress_callback:
                progress_callback(i + 1, total, url)

        combined_text = '\n'.join(combined_parts)
        total_words = sum(p.get('word_count', 0) for p in pages if p.get('success'))

        return CrawlResult(
            start_url=urls[0] if urls else '',
            pages_scraped=sum(1 for p in pages if p.get('success')),
            total_words=total_words,
            combined_text=combined_text,
            pages=pages,
        )

    # ------------------------------------------------------------------
    # Spider (domain crawl)
    # ------------------------------------------------------------------

    def crawl_domain(
        self,
        start_url: str,
        max_pages: int = 20,
        mode: str = 'basic',
        progress_callback=None,
    ) -> CrawlResult:
        """
        Crawl a domain up to max_pages, collecting all text.

        Uses Scrapling's Spider framework with pause/resume support.
        Falls back to single-URL fetch if Scrapling spiders unavailable.
        """
        logger.info(f'Crawling domain: {start_url} (max {max_pages} pages)')
        try:
            from scrapling.spiders import Spider, Response

            scraped_pages: list[dict] = []
            combined_parts: list[str] = []
            count = [0]

            class MiroSpider(Spider):
                name = 'mirofish_crawl'
                start_urls = [start_url]
                concurrent_requests = 5

                async def parse(self, response: Response):
                    title, text = _html_to_text(response)
                    text = text[:ScraperService.MAX_TEXT_PER_PAGE]
                    wc = len(text.split())
                    scraped_pages.append({
                        'url': response.url, 'title': title,
                        'word_count': wc, 'success': True,
                    })
                    combined_parts.append(
                        _format_scraped_block(response.url, title, text)
                    )
                    count[0] += 1
                    if progress_callback:
                        progress_callback(count[0], max_pages, response.url)

                    if count[0] < max_pages:
                        for link in response.css('a[href]'):
                            href = link.attrib.get('href', '')
                            if href.startswith('http'):
                                yield response.follow(href)

            MiroSpider(max_requests=max_pages).start()

            combined_text = '\n'.join(combined_parts)
            total_words = sum(p.get('word_count', 0) for p in scraped_pages)
            return CrawlResult(
                start_url=start_url,
                pages_scraped=len(scraped_pages),
                total_words=total_words,
                combined_text=combined_text,
                pages=scraped_pages,
            )

        except Exception as exc:
            logger.warning(f'Spider failed, falling back to single fetch: {exc}')
            return self.fetch_urls([start_url], mode=mode,
                                   progress_callback=progress_callback)
