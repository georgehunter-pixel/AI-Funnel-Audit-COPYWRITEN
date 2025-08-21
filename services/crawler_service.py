import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional
import time
import logging
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

@dataclass
class PageInfo:
    url: str
    title: str
    page_type: str
    load_time: float
    status_code: int
    content_length: int
    links: List[str]
    forms: List[Dict]
    buttons: List[Dict]
    images: List[str]
    meta_description: str
    h1_tags: List[str]
    errors: List[str]

@dataclass
class SiteMap:
    domain: str
    pages: List[PageInfo]
    broken_links: List[str]
    external_links: List[str]
    crawl_stats: Dict
    funnel_pages: Dict[str, List[str]]  # page_type -> [urls]

class CrawlerService:
    def __init__(self, max_pages: int = 50, delay: float = 1.0):
        self.max_pages = max_pages
        self.delay = delay
        self.session = None
        self.robots_cache = {}
        
    async def crawl_website(self, start_url: str) -> SiteMap:
        """Crawl a website and return comprehensive site map"""
        logger.info(f"Starting crawl of {start_url}")
        
        parsed_url = urlparse(start_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Initialize session
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            
            # Check robots.txt
            robots_allowed = await self._check_robots_txt(domain)
            if not robots_allowed:
                logger.warning(f"Robots.txt disallows crawling {domain}")
            
            # Initialize crawl state
            to_crawl = {start_url}
            crawled = set()
            pages = []
            broken_links = []
            external_links = []
            
            crawl_start = time.time()
            
            # Crawl pages
            while to_crawl and len(crawled) < self.max_pages:
                current_url = to_crawl.pop()
                
                if current_url in crawled:
                    continue
                    
                if not self._is_same_domain(current_url, domain):
                    external_links.append(current_url)
                    continue
                
                logger.info(f"Crawling: {current_url}")
                
                try:
                    page_info = await self._crawl_page(current_url)
                    pages.append(page_info)
                    crawled.add(current_url)
                    
                    # Add new links to crawl queue
                    for link in page_info.links:
                        absolute_link = urljoin(current_url, link)
                        if self._is_same_domain(absolute_link, domain):
                            to_crawl.add(absolute_link)
                        else:
                            external_links.append(absolute_link)
                    
                    # Rate limiting
                    await asyncio.sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"Failed to crawl {current_url}: {str(e)}")
                    broken_links.append(current_url)
            
            crawl_time = time.time() - crawl_start
            
            # Analyze funnel pages
            funnel_pages = self._identify_funnel_pages(pages)
            
            # Create crawl stats
            crawl_stats = {
                "total_pages": len(pages),
                "broken_links": len(broken_links),
                "external_links": len(external_links),
                "crawl_time": crawl_time,
                "pages_per_second": len(pages) / crawl_time if crawl_time > 0 else 0
            }
            
            logger.info(f"Crawl completed: {len(pages)} pages in {crawl_time:.2f}s")
            
            return SiteMap(
                domain=domain,
                pages=pages,
                broken_links=broken_links,
                external_links=external_links,
                crawl_stats=crawl_stats,
                funnel_pages=funnel_pages
            )
    
    async def _crawl_page(self, url: str) -> PageInfo:
        """Crawl a single page and extract information"""
        start_time = time.time()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        async with self.session.get(url, headers=headers) as response:
            load_time = time.time() - start_time
            content = await response.text()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract page information
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""
            
            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_description = meta_desc.get('content', '') if meta_desc else ""
            
            # H1 tags
            h1_tags = [h1.get_text().strip() for h1 in soup.find_all('h1')]
            
            # Links
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                if href and not href.startswith('#'):
                    links.append(href)
            
            # Forms
            forms = []
            for form in soup.find_all('form'):
                form_info = {
                    'action': form.get('action', ''),
                    'method': form.get('method', 'get').lower(),
                    'inputs': []
                }
                
                for input_elem in form.find_all(['input', 'select', 'textarea']):
                    input_info = {
                        'type': input_elem.get('type', 'text'),
                        'name': input_elem.get('name', ''),
                        'required': input_elem.has_attr('required'),
                        'placeholder': input_elem.get('placeholder', '')
                    }
                    form_info['inputs'].append(input_info)
                
                forms.append(form_info)
            
            # Buttons
            buttons = []
            for button in soup.find_all(['button', 'input[type="submit"]', 'input[type="button"]']):
                button_info = {
                    'text': button.get_text().strip() or button.get('value', ''),
                    'type': button.get('type', 'button'),
                    'class': ' '.join(button.get('class', [])),
                    'id': button.get('id', '')
                }
                buttons.append(button_info)
            
            # Images
            images = [img.get('src', '') for img in soup.find_all('img', src=True)]
            
            # Determine page type
            page_type = self._classify_page_type(url, title_text, content)
            
            # Check for errors
            errors = self._detect_page_errors(soup, response.status)
            
            return PageInfo(
                url=url,
                title=title_text,
                page_type=page_type,
                load_time=load_time,
                status_code=response.status,
                content_length=len(content),
                links=links,
                forms=forms,
                buttons=buttons,
                images=images,
                meta_description=meta_description,
                h1_tags=h1_tags,
                errors=errors
            )
    
    def _classify_page_type(self, url: str, title: str, content: str) -> str:
        """Classify page type based on URL, title, and content"""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Landing page indicators
        if any(keyword in url_lower for keyword in ['landing', 'lp', 'campaign']):
            return 'landing'
        
        # Product page indicators
        if any(keyword in url_lower for keyword in ['product', 'item', '/p/', 'shop']):
            return 'product'
        
        # Checkout/cart indicators
        if any(keyword in url_lower for keyword in ['checkout', 'cart', 'payment', 'billing']):
            return 'checkout'
        
        # Thank you/confirmation indicators
        if any(keyword in url_lower for keyword in ['thank', 'confirmation', 'success', 'complete']):
            return 'confirmation'
        
        # Contact page indicators
        if any(keyword in url_lower for keyword in ['contact', 'support', 'help']):
            return 'contact'
        
        # About page indicators
        if any(keyword in url_lower for keyword in ['about', 'team', 'company']):
            return 'about'
        
        # Blog/content indicators
        if any(keyword in url_lower for keyword in ['blog', 'news', 'article', 'post']):
            return 'content'
        
        # Check content for indicators
        if 'add to cart' in content_lower or 'buy now' in content_lower:
            return 'product'
        
        if 'sign up' in content_lower or 'get started' in content_lower:
            return 'signup'
        
        # Default to general
        return 'general'
    
    def _identify_funnel_pages(self, pages: List[PageInfo]) -> Dict[str, List[str]]:
        """Identify and group funnel pages"""
        funnel_pages = {
            'landing': [],
            'product': [],
            'checkout': [],
            'confirmation': [],
            'signup': [],
            'contact': []
        }
        
        for page in pages:
            if page.page_type in funnel_pages:
                funnel_pages[page.page_type].append(page.url)
        
        return funnel_pages
    
    def _detect_page_errors(self, soup: BeautifulSoup, status_code: int) -> List[str]:
        """Detect common page errors"""
        errors = []
        
        # HTTP errors
        if status_code >= 400:
            errors.append(f"HTTP {status_code} error")
        
        # Missing title
        title = soup.find('title')
        if not title or not title.get_text().strip():
            errors.append("Missing or empty title tag")
        
        # Missing meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc or not meta_desc.get('content', '').strip():
            errors.append("Missing meta description")
        
        # No H1 tags
        h1_tags = soup.find_all('h1')
        if not h1_tags:
            errors.append("No H1 tags found")
        elif len(h1_tags) > 1:
            errors.append(f"Multiple H1 tags found ({len(h1_tags)})")
        
        # Missing viewport meta tag
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        if not viewport:
            errors.append("Missing viewport meta tag")
        
        # Broken images
        broken_images = soup.find_all('img', src='')
        if broken_images:
            errors.append(f"{len(broken_images)} images with empty src")
        
        return errors
    
    async def _check_robots_txt(self, domain: str) -> bool:
        """Check if crawling is allowed by robots.txt"""
        if domain in self.robots_cache:
            return self.robots_cache[domain]
        
        try:
            robots_url = f"{domain}/robots.txt"
            async with self.session.get(robots_url) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    
                    # Simple robots.txt parsing
                    user_agent_found = False
                    disallow_all = False
                    
                    for line in robots_content.split('\n'):
                        line = line.strip().lower()
                        if line.startswith('user-agent:'):
                            user_agent = line.split(':', 1)[1].strip()
                            user_agent_found = user_agent == '*' or 'funnel' in user_agent
                        elif line.startswith('disallow:') and user_agent_found:
                            disallow_path = line.split(':', 1)[1].strip()
                            if disallow_path == '/':
                                disallow_all = True
                    
                    allowed = not disallow_all
                    self.robots_cache[domain] = allowed
                    return allowed
        
        except Exception as e:
            logger.warning(f"Could not check robots.txt for {domain}: {str(e)}")
        
        # Default to allowed if robots.txt is not accessible
        self.robots_cache[domain] = True
        return True
    
    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if URL belongs to the same domain"""
        try:
            parsed_url = urlparse(url)
            parsed_domain = urlparse(domain)
            return parsed_url.netloc == parsed_domain.netloc
        except:
            return False