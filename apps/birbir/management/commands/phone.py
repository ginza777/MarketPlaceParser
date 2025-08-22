import time

import requests
from django.core.management.base import BaseCommand

from ...models import Category, Product, Photo
from fake_useragent import UserAgent

ua = UserAgent()

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'uz-UZ,uz;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6,en;q=0.5',
    'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzUxMiJ9.eyJqdGkiOiI0OGMwNmVjZS03OWVhLTQyOGMtOTdjNy1mMjRjZTJjZGQzMmYiLCJpYXQiOjE3NDgxMTExNTQsImV4cCI6MTc0ODEyNTU1NCwidSI6ImQ5ZmM1N2RlLTk0YzktNDBjYS05MzdhLTc3YTUyMGNkOTViNCIsInV0IjoxMCwiaXAiOiIyMTMuMjMwLjc2LjIyNyIsInQiOjEsImR0IjoiMjAyNS0wNS0yNFQwODoxODoxOC42Mzk3OTZaIiwiZGkiOnsidXVpZCI6IjMzZGZjZDhmLWU5ODMtNDMxMC04ZWNkLTM2ZTYxODczNzU1YyIsIm9zIjoibWFjT1MgMTAuMTUuNyIsIm5hbWUiOiJBcHBsZSBNYWNpbnRvc2giLCJhY2NlcHRMYW5ndWFnZSI6InV6In0sInYiOiIxLjMuMi4wIn0.AbISQUE3CxPugLz8QfaaeTTTTQIiNNVzJBSoeFNy5uDBrWPN5OFK_i7aV6t-eO_o-WPprQBRm2kDAc7yM-GvocngAOq7RvvjzZ3T4yl3xP0qHyfuXhDa2QI8u0WZlkUbJA0jMFufWyYbpBVMqo5VoMjEcOCPgzbYVxlWCSxUrDowAEpm',
    # 'content-length': '0',
    'dnt': '1',
    'origin': 'https://birbir.uz',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'x-current-language': 'uz',
    'x-current-region': 'toshkent',
}


def get_product_contact(product_id):
    url = f"https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/{product_id}/contact"
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random
    print(f"Fetching product {product_id} contact information...")
    try:
        response = requests.post(url, headers=dynamic_headers)
        if response.status_code != 200:
            print(f"Status code: {response.status_code}")
            print(response.json())
            print(f"Failed to fetch product {product_id}")
            return None
        product_data = response.json()
        print(f"Processing product {product_id}...")
        if not product_data:
            print(f"No data found for product {product_id}")
            return None
        print(response.json()['content']['phone'])
        product = Product.objects.get(product_id=product_id)
        product.phone = product_data['content']['phone']
        product.is_parsed = True
        product.save()



    except Exception as e:
        print(f"Error processing product {product_id}: {e}")
        return None


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        products = Product.objects.filter(phone=None).order_by('created_at')
        print(f"Found {products.count()} products without phone information.")
        print("Starting to fetch phone information for products...")
        i= 0
        for product in products:
            print(f"Processing product {i+1}/{products.count()}: {product.product_id}")
            get_product_contact(product.product_id)
            time.sleep(0.1)
            i += 1