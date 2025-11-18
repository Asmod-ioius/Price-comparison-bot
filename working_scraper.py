import requests
from bs4 import BeautifulSoup
import time
import logging
import urllib.parse
import heapq
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkingPriceComparisonScraper:
    def __init__(self):
        self.results = []
        self.price_queue = []  # Min-heap priority queue
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    def extract_price_value(self, price_string):
        """Extract numeric price value from price string for sorting"""
        try:
            # Remove currency symbols and commas, extract numbers
            numbers = re.findall(r'\d+', price_string.replace(',', ''))
            if numbers:
                return int(''.join(numbers))
            return float('inf')  # If no price found, put at end
        except:
            return float('inf')

    def scrape_prices(self, product_name, include_secondhand=False, include_industrial=False):
        self.results = []
        self.price_queue = []
        counter = 0  # Counter to break ties when prices are equal
        
        # Try Amazon
        try:
            amazon_result = self.scrape_amazon(product_name)
            if amazon_result:
                price_value = self.extract_price_value(amazon_result['price_display'])
                # Push to min-heap: (priority, counter, result)
                heapq.heappush(self.price_queue, (price_value, counter, amazon_result))
                counter += 1
        except Exception as e:
            logger.error(f"Amazon scraping failed: {e}")
            
        # Try Flipkart
        try:
            flipkart_result = self.scrape_flipkart(product_name)
            if flipkart_result:
                price_value = self.extract_price_value(flipkart_result['price_display'])
                heapq.heappush(self.price_queue, (price_value, counter, flipkart_result))
                counter += 1
        except Exception as e:
            logger.error(f"Flipkart scraping failed: {e}")
        
        # Try OLX if second-hand products requested
        if include_secondhand:
            try:
                olx_result = self.scrape_olx(product_name)
                if olx_result:
                    price_value = self.extract_price_value(olx_result['price_display'])
                    heapq.heappush(self.price_queue, (price_value, counter, olx_result))
                    counter += 1
            except Exception as e:
                logger.error(f"OLX scraping failed: {e}")
        
        # Try IndiaMart if industrial products requested
        if include_industrial:
            try:
                indiamart_result = self.scrape_indiamart(product_name)
                if indiamart_result:
                    price_value = self.extract_price_value(indiamart_result['price_display'])
                    heapq.heappush(self.price_queue, (price_value, counter, indiamart_result))
                    counter += 1
            except Exception as e:
                logger.error(f"IndiaMart scraping failed: {e}")
        
        # Extract results from priority queue (lowest price first)
        while self.price_queue:
            price_value, _, result = heapq.heappop(self.price_queue)
            self.results.append(result)
            logger.info(f"Added {result['website']} with price value: {price_value}")
            
        return self.results

    def scrape_amazon(self, product_name):
        try:
            query = urllib.parse.quote_plus(product_name)
            
            # Try multiple Amazon URLs and headers
            urls = [
                f"https://www.amazon.in/s?k={query}&ref=nb_sb_noss",
                f"https://www.amazon.in/s?k={query}",
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
            
            for url in urls:
                try:
                    response = self.session.get(url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        break
                    else:
                        logger.warning(f"Amazon returned status code: {response.status_code} for {url}")
                        time.sleep(2)
                except:
                    continue
            else:
                # If all URLs failed, return a placeholder result
                logger.error("Amazon blocked all requests")
                return {
                    "website": "Amazon",
                    "title": f"{product_name} - Amazon (Blocked)",
                    "price_display": "Visit Amazon directly",
                    "link": f"https://www.amazon.in/s?k={query}"
                }
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product containers with multiple selectors
            products = (soup.find_all('div', {'data-component-type': 's-search-result'}) or
                       soup.find_all('div', class_='s-result-item') or
                       soup.find_all('div', {'data-asin': True}))
            
            if not products:
                logger.warning("No Amazon products found in HTML")
                return {
                    "website": "Amazon",
                    "title": f"{product_name} - Search on Amazon",
                    "price_display": "Click to view prices",
                    "link": f"https://www.amazon.in/s?k={query}"
                }
                
            product = products[0]  # Get first product
            
            # Extract title with multiple selectors
            title_elem = (product.find('h2', class_='a-size-mini') or
                         product.find('span', class_='a-size-medium') or
                         product.find('h2') or
                         product.find('span', class_='a-size-base-plus'))
            title = title_elem.get_text(strip=True) if title_elem else f"{product_name} - Amazon Product"
            
            # Extract price with multiple selectors
            price_elem = (product.find('span', class_='a-price-whole') or
                         product.find('span', class_='a-price') or
                         product.find('span', class_='a-offscreen'))
            price = f"₹{price_elem.get_text(strip=True)}" if price_elem else "Price on Amazon"
            
            # Extract link
            link_elem = product.find('h2').find('a') if product.find('h2') else None
            link = f"https://www.amazon.in{link_elem['href']}" if link_elem and link_elem.get('href') else f"https://www.amazon.in/s?k={query}"
            
            return {
                "website": "Amazon",
                "title": title[:100] + "..." if len(title) > 100 else title,
                "price_display": price,
                "link": link
            }
            
        except Exception as e:
            logger.error(f"Amazon scraping error: {e}")
            return {
                "website": "Amazon",
                "title": f"{product_name} - Search on Amazon",
                "price_display": "Click to view prices",
                "link": f"https://www.amazon.in/s?k={urllib.parse.quote_plus(product_name)}"
            }

    def scrape_flipkart(self, product_name):
        try:
            query = urllib.parse.quote_plus(product_name)
            url = f"https://www.flipkart.com/search?q={query}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Flipkart returned status code: {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product containers
            products = soup.find_all('div', {'data-id': True})
            
            if not products:
                logger.warning("No Flipkart products found")
                return None
                
            product = products[0]  # Get first product
            
            # Extract title
            title_elem = product.find('div', class_='_4rR01T') or product.find('a', class_='s1Q9rs')
            title = title_elem.get_text(strip=True) if title_elem else f"{product_name} - Flipkart Product"
            
            # Extract price
            price_elem = product.find('div', class_='_30jeq3')
            price = price_elem.get_text(strip=True) if price_elem else "Price not available"
            
            # Extract link
            link_elem = product.find('a', class_='_1fQZEK') or product.find('a', class_='s1Q9rs')
            link = f"https://www.flipkart.com{link_elem['href']}" if link_elem and link_elem.get('href') else url
            
            return {
                "website": "Flipkart",
                "title": title[:100] + "..." if len(title) > 100 else title,
                "price_display": price,
                "link": link
            }
            
        except Exception as e:
            logger.error(f"Flipkart scraping error: {e}")
            return None

    def scrape_olx(self, product_name):
        try:
            query = urllib.parse.quote_plus(product_name)
            url = f"https://www.olx.in/items/q-{query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.error(f"OLX returned status code: {response.status_code}")
                return {
                    "website": "OLX (Second-hand)",
                    "title": f"{product_name} - Search on OLX",
                    "price_display": "Click to view prices",
                    "link": url
                }
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product listings
            products = soup.find_all('li', {'data-aut-id': 'itemBox'}) or soup.find_all('div', class_='_1DNjI')
            
            if not products:
                logger.warning("No OLX products found")
                return {
                    "website": "OLX (Second-hand)",
                    "title": f"{product_name} - Search on OLX",
                    "price_display": "Click to view prices",
                    "link": url
                }
                
            product = products[0]
            
            # Extract title
            title_elem = product.find('span', {'data-aut-id': 'itemTitle'}) or product.find('div', class_='_2tW1I')
            title = title_elem.get_text(strip=True) if title_elem else f"{product_name} - OLX Product"
            
            # Extract price
            price_elem = product.find('span', {'data-aut-id': 'itemPrice'}) or product.find('span', class_='_89yzn')
            price = price_elem.get_text(strip=True) if price_elem else "Price not available"
            
            # Extract link
            link_elem = product.find('a', {'data-aut-id': 'itemTitle'}) or product.find('a')
            if link_elem and link_elem.get('href'):
                link = link_elem['href'] if link_elem['href'].startswith('http') else f"https://www.olx.in{link_elem['href']}"
            else:
                link = url
            
            return {
                "website": "OLX (Second-hand)",
                "title": title[:100] + "..." if len(title) > 100 else title,
                "price_display": price,
                "link": link
            }
            
        except Exception as e:
            logger.warning(f"OLX scraping error: {e}")
            return {
                "website": "OLX (Second-hand)",
                "title": f"{product_name} - Search on OLX",
                "price_display": "Click to view prices",
                "link": f"https://www.olx.in/items/q-{urllib.parse.quote_plus(product_name)}"
            }

    def scrape_indiamart(self, product_name):
        try:
            query = urllib.parse.quote_plus(product_name)
            url = f"https://www.indiamart.com/search.mp?ss={query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.error(f"IndiaMart returned status code: {response.status_code}")
                return {
                    "website": "IndiaMart (Industrial)",
                    "title": f"{product_name} - Search on IndiaMart",
                    "price_display": "Click to view prices",
                    "link": url
                }
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product listings
            products = soup.find_all('div', class_='lst') or soup.find_all('div', class_='prd')
            
            if not products:
                logger.warning("No IndiaMart products found")
                return {
                    "website": "IndiaMart (Industrial)",
                    "title": f"{product_name} - Search on IndiaMart",
                    "price_display": "Click to view prices",
                    "link": url
                }
                
            product = products[0]
            
            # Extract title
            title_elem = product.find('p', class_='prd_name') or product.find('a', class_='prd_name') or product.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else f"{product_name} - IndiaMart Product"
            
            # Extract price
            price_elem = product.find('span', class_='prc') or product.find('div', class_='price')
            price = price_elem.get_text(strip=True) if price_elem else "Get Best Price"
            
            # Extract link
            link_elem = product.find('a', class_='prd_name') or product.find('a')
            if link_elem and link_elem.get('href'):
                link = link_elem['href'] if link_elem['href'].startswith('http') else f"https://www.indiamart.com{link_elem['href']}"
            else:
                link = url
            
            return {
                "website": "IndiaMart (Industrial)",
                "title": title[:100] + "..." if len(title) > 100 else title,
                "price_display": price,
                "link": link
            }
            
        except Exception as e:
            logger.warning(f"IndiaMart scraping error: {e}")
            return {
                "website": "IndiaMart (Industrial)",
                "title": f"{product_name} - Search on IndiaMart",
                "price_display": "Get Best Price",
                "link": f"https://www.indiamart.com/search.mp?ss={urllib.parse.quote_plus(product_name)}"
            }