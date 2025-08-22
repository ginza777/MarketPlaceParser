import time

import requests
from django.core.management.base import BaseCommand

from ...models import Category, Product
from fake_useragent import UserAgent

ua = UserAgent()

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'uz-UZ,uz;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6,en;q=0.5',
    'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzUxMiJ9.eyJqdGkiOiJiMzQyZTNjMi1jNDEyLTRmNmMtYmRhZS0wYWVmZmQ5MTM4YWEiLCJpYXQiOjE3NDgwODkzMjksImV4cCI6MTc0ODEwMzcyOSwidSI6ImFkMDI3ZWRlLTFkNzUtNGE2ZC1iN2M2LTc2MWMzYTM5NWUxNyIsInV0IjoxMSwiaXAiOiIyMTMuMjMwLjc2LjIyNyIsInQiOjEsImR0IjoiMjAyNS0wNS0yNFQwODoxODoxOC42Mzk3OTZaIiwiZGkiOnsidXVpZCI6IjMzZGZjZDhmLWU5ODMtNDMxMC04ZWNkLTM2ZTYxODczNzU1YyIsIm9zIjoibWFjT1MgMTAuMTUuNyIsIm5hbWUiOiJBcHBsZSBNYWNpbnRvc2giLCJhY2NlcHRMYW5ndWFnZSI6InV6In0sInYiOiIxLjMuMi4wIn0.AfcF_PBiSq0u534I_GDgNk4bP7gKm2RNIBGB55LtAoL-iLadHKDE-vd0SR444TOHGw70uhycogd1Q2L2fg_mRKpbAAnV1h_YmqbAwYzafT1XPX1FxYRY_8PEK0TTD7QS21u8lEvqsotTyk0X7T-8zbqCuf1e7hzl1ThNv6NHSLwVJPz5',
    'content-type': 'application/json',
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

json_data = {
    'category': 1000488,
    'courierDeliveryOnly': False,
    'freeOnly': False,
    'urgentSaleOnly': False,
    'sort': 1,
    'features': [],
    'page': 1,
    'perPage': 100,
}

category_list = Category.objects.all().values('category_id')



def print_product_info(products):
    for product in products:
        print("ID:", product.get("id"))
        print("Sarlavha (title):", product.get("title"))
        print("Slug:", product.get("slug"))
        seller = product.get("seller", {})
        print("Sotuvchi:", seller.get("name"))
        print("Ro‘yxatdan o‘tgan sana:", seller.get("registeredDate"))
        print("So‘nggi faollik:", seller.get("lastAccessDate"))
        print("URL:", product.get("webUri"))
        print("-" * 50)


def get_product_response(category_id, page):
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random  # Random User-Agent

    payload = json_data.copy()
    payload['category'] = category_id
    payload['page'] = page
    payload['perPage'] = 100

    response = requests.post(
        'https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/feed',
        headers=dynamic_headers,
        json=payload
    )

    try:
        products = response.json()['content']['items']
        return products
    except Exception as e:
        print(f"Xatolik: {e}")
        return []


def create_products(products,category_id):
    for product in products:
        product_id = product.get("id")
        slug = product.get("slug")
        title = product.get("title")
        url = product.get("webUri")
        category = Category.objects.filter(category_id=category_id).first()
        # Create or update the Product instance
        u, create = Product.objects.update_or_create(
            product_id=product_id,
            defaults={
                'slug': slug,
                'title': title,
                'category': category,
                'url': url,
            }
        )

        if create:
            print(f"Mahsulot yaratildi: {title} (ID: {product_id})")
        else:
            print(f"Mahsulot yangilandi: {title} (ID: {product_id})")


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for category in category_list:
            category_id = category['category_id']
            print(f"\n>>> Kategoriya ID: {category_id}")

            page = 1
            while True:
                print(f"\n--- Sahifa: {page} ---")
                products = get_product_response(category_id, page)

                if not products:
                    print("Mahsulot yo‘q, keyingi kategoriya...")
                    break

                print_product_info(products)
                create_products(products,category_id)

                page += 1
                time.sleep(2)
            time.sleep(10)
            print("Waiting for 10 seconds before next request...\n\n\n")
