"""
Web scraper for collecting data center policy and impact evidence.
Targets: Legistar PDFs (San Jose, Santa Clara), news articles, utility documents.
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataCenterScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.base_urls = {
            'sanjose_legistar': 'https://sanjose.legistar.com',
            'santaclara_legistar': 'https://santaclara.legistar.com',
            'svp_news': 'https://www.siliconvalleypower.com/home/components/news/news',
            'sjce_news': 'https://sanjosecleanenergy.org'
        }
        self.keywords = [
            'data center', 'datacenter', 'rate increase', 'rate hike',
            'grid upgrade', 'infrastructure', 'water restriction',
            'electricity load', 'capacity', 'resilience'
        ]
        
    def search_legistar_legislation(self, city: str = 'sanjose', 
                                   search_term: str = 'data center',
                                   days_back: int = 90) -> List[Dict]:
        """
        Search Legistar legislation pages for data center mentions.
        """
        logger.info(f"Searching {city} Legistar for '{search_term}'...")
        
        base_url = self.base_urls.get(f'{city}_legistar')
        if not base_url:
            logger.error(f"Unknown city: {city}")
            return []
        
        # Construct search URL with full-text search
        search_url = f"{base_url}/Legislation.aspx"
        params = {
            'Search': search_term,
            'FullText': 1
        }
        
        try:
            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            results = []
            # Parse legislation rows (adjust selectors based on actual HTML structure)
            rows = soup.find_all('tr', class_='row')
            
            for row in rows:
                try:
                    # Extract title, date, link
                    title_cell = row.find('td', class_='title')
                    if not title_cell:
                        continue
                    
                    title = title_cell.get_text(strip=True)
                    link = title_cell.find('a')
                    url = link['href'] if link and link.get('href') else None
                    
                    if url and not url.startswith('http'):
                        url = base_url + url
                    
                    date_cell = row.find('td', class_='date')
                    date_str = date_cell.get_text(strip=True) if date_cell else 'N/A'
                    
                    results.append({
                        'type': 'legistar_legislation',
                        'city': city,
                        'title': title,
                        'url': url,
                        'date': date_str,
                        'search_term': search_term
                    })
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue
            
            logger.info(f"Found {len(results)} results in {city} Legistar")
            return results
        
        except requests.RequestException as e:
            logger.error(f"Request error for {city} Legistar: {e}")
            return []
    
    def search_news_sources(self, source: str = 'svp') -> List[Dict]:
        """
        Search news sources for data center articles.
        """
        logger.info(f"Searching {source} news for data center articles...")
        
        if source == 'svp':
            url = self.base_urls['svp_news']
        elif source == 'sjce':
            url = self.base_urls['sjce_news']
        else:
            logger.error(f"Unknown source: {source}")
            return []
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            results = []
            
            # Find news items (adjust selectors based on actual HTML)
            articles = soup.find_all('article') or soup.find_all('div', class_='news-item')
            
            for article in articles:
                try:
                    title_elem = article.find(['h3', 'h2', 'a'])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Check if article contains relevant keywords
                    article_text = article.get_text().lower()
                    if not any(kw in article_text for kw in self.keywords):
                        continue
                    
                    link = article.find('a')
                    url = link['href'] if link and link.get('href') else None
                    
                    if url and not url.startswith('http'):
                        url = self.base_urls[f'{source}_news'].split('/home')[0] + url
                    
                    date_elem = article.find('time') or article.find(class_='date')
                    date_str = date_elem.get_text(strip=True) if date_elem else 'N/A'
                    
                    results.append({
                        'type': 'news',
                        'source': source,
                        'title': title,
                        'url': url,
                        'date': date_str
                    })
                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
                    continue
            
            logger.info(f"Found {len(results)} relevant articles from {source}")
            return results
        
        except requests.RequestException as e:
            logger.error(f"Request error for {source}: {e}")
            return []
    
    def extract_text_from_url(self, url: str) -> Optional[str]:
        """
        Attempt to extract plain text from a URL (HTML or simple PDF).
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Try HTML first
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            return text if text else None
        
        except requests.RequestException as e:
            logger.warning(f"Could not extract text from {url}: {e}")
            return None
    
    def extract_claims_from_text(self, text: str, source_url: str, 
                                source_title: str) -> List[Dict]:
        """
        Extract claim statements from extracted text.
        Simple heuristic: sentences containing keywords + numbers or strong statements.
        """
        claims = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
            
            # Check for keyword presence
            if any(kw in sentence.lower() for kw in self.keywords):
                # Check for numbers or strong claims
                if re.search(r'\d+', sentence) or any(word in sentence.lower() for word in 
                                                      ['must', 'require', 'will', 'shall', 'project']):
                    claims.append({
                        'text': sentence,
                        'source_url': source_url,
                        'source_title': source_title,
                        'extracted_at': datetime.now().isoformat()
                    })
        
        return claims
    
    def run_full_scrape(self) -> Dict:
        """
        Run full scraper and compile results.
        """
        logger.info("Starting full scrape...")
        
        all_sources = []
        
        # Search Legistar for both cities
        for city in ['sanjose', 'santaclara']:
            legistar_results = self.search_legistar_legislation(city=city, search_term='data center')
            all_sources.extend(legistar_results)
        
        # Search news sources
        for source in ['svp', 'sjce']:
            news_results = self.search_news_sources(source=source)
            all_sources.extend(news_results)
        
        logger.info(f"Total sources found: {len(all_sources)}")
        
        # Extract text and claims from each source
        all_claims = []
        for source in all_sources:
            if source.get('url'):
                text = self.extract_text_from_url(source['url'])
                if text:
                    claims = self.extract_claims_from_text(
                        text, 
                        source['url'], 
                        source.get('title', 'Unknown')
                    )
                    all_claims.extend(claims)
        
        logger.info(f"Total claims extracted: {len(all_claims)}")
        
        return {
            'sources': all_sources,
            'claims': all_claims,
            'scraped_at': datetime.now().isoformat(),
            'total_sources': len(all_sources),
            'total_claims': len(all_claims)
        }


def main():
    scraper = DataCenterScraper()
    results = scraper.run_full_scrape()
    
    # Save results
    output_file = 'src/scrape_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    logger.info(f"Summary: {results['total_sources']} sources, {results['total_claims']} claims")


if __name__ == '__main__':
    main()
