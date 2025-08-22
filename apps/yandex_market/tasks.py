import re
import random
import time
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import Category, Product, Shop, Brand
from .proxies import proxy_list

def parse_yandex_cards(html_content: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all("article", {"data-auto": "searchOrganic"})
    products = []
    for article in articles:
        product = {}
        link_elem = article.find('a', href=True)
        product['url'] = link_elem['href'] if link_elem else None
        title_elem = article.find('span', {'data-auto': 'snippet-title'}) or article.find(['span', 'div'], string=re.compile(r'.+'))
        product['title'] = title_elem.get_text(strip=True) if title_elem else None
        img_elem = article.find('img', {'data-auto': 'snippet-image'}) or article.find('img', src=True)
        product['image'] = img_elem['src'] if img_elem else None
        price_elem = article.find('span', {'data-auto': 'snippet-price-current'}) or article.find('span', string=re.compile(r'[\d\s]+₽'))
        product['price'] = price_elem.get_text(strip=True).replace('\u2009', '') if price_elem else None
        products.append(product)
    return products

def create_or_update_product(product_data: Dict[str, Optional[str]], category):
    try:
        price = float(re.search(r'[\d\s]+', product_data['price']).group().replace(' ', '')) if product_data['price'] else 0.0
        product, created = Product.objects.update_or_create(
            url=product_data['url'],
            defaults={
                'name': product_data['title'] or 'Untitled Product',
                'price': price,
                'category': category,
            }
        )
        if created:
            category.product_count += 1
            category.save()
        return created
    except Exception as e:
        print(f"Error creating/updating product {product_data.get('title', 'Unknown')}: {str(e)}")
        return False

@shared_task
def scrape_yandex_market():
    user_agent_random = UserAgent()
    print(f"Total proxies available: {len(proxy_list)}")
    category_urls = list(Category.objects.values_list('url', flat=True))
    total_categories = len(category_urls)
    print(f"Total categories to process: {total_categories}")
    print(f"Category URLs: {category_urls}")
    for cat_idx, category_url in enumerate(category_urls, 1):
        try:
            category = Category.objects.get(url=category_url)
            print(f"[Category {cat_idx}/{total_categories}] Found category: {category.name} ({category_url})")
        except ObjectDoesNotExist:
            print(f"[Category {cat_idx}/{total_categories}] Skipping invalid category: {category_url}")
            continue
        print(f"[Category {cat_idx}/{total_categories}] Processing category: {category_url}")
        page = 1
        products_found = False
        while True:
            random_proxy = random.choice(proxy_list)
            print(f"[Category {cat_idx}/{total_categories}] Using proxy: {random_proxy}")
            proxies = {
                'http': f'http://{random_proxy}',
                'https': f'http://{random_proxy}'
            }
            headers = {"User-Agent": user_agent_random.random}
            print(f"[Category {cat_idx}/{total_categories}] Using User-Agent: {headers['User-Agent']}")
            url = f"{category_url}/list?hid=91307&rs=eJwzcv7E6MDBILDwEKsEg8Lqk6waX1tvsWvsBTJ2PfzCrnEVyPiwaz-7xoJTrBrnDgAZJ4Ei74B4DRB_AeKeU6wAu3Ic9g%2C%2C&page={page}"
            print(f"[Category {cat_idx}/{total_categories}] Fetching page {page}: {url}")
            try:
                response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
                print(f"[Category {cat_idx}/{total_categories}] Status Code: {response.status_code}")
                if response.status_code == 200:
                    products = parse_yandex_cards(response.text)
                    total_products = len(products)
                    print(f"[Category {cat_idx}/{total_categories}] Found {total_products} products on page {page}")
                    if not products:
                        print(f"[Category {cat_idx}/{total_categories}] No products found on page {page}, stopping.")
                        break
                    products_found = True
                    for prod_idx, product in enumerate(products, 1):
                        print(f"[Category {cat_idx}/{total_categories}] [Product {prod_idx}/{total_products}] Processing: {product.get('title', 'Unknown')}")
                        print(f"[Category {cat_idx}/{total_categories}] [Product {prod_idx}/{total_products}] Product details: {product}")
                        created = create_or_update_product(product, category)
                        print(f"[Category {cat_idx}/{total_categories}] [Product {prod_idx}/{total_products}] {'Created' if created else 'Updated'} product: {product.get('title', 'Unknown')}")
                else:
                    print(f"[Category {cat_idx}/{total_categories}] Failed to fetch page {page}, status code: {response.status_code}")
                    break
            except Exception as e:
                print(f"[Category {cat_idx}/{total_categories}] Error on page {page}: {str(e)}")
                break
            page += 1
            sleep_time = random.uniform(1, 5)
            print(f"[Category {cat_idx}/{total_categories}] Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        if products_found:
            category.parsed = True
            category.last_parsed = timezone.now()
            category.save()
            print(f"[Category {cat_idx}/{total_categories}] Marked as parsed: {category.name}, Product count: {category.product_count}")
    print("Scraping completed.")