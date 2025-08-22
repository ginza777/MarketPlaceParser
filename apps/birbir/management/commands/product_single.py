import json
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


def create_category(category_data):
    Category.objects.update_or_create(
        category_id=category_data['id'],
        defaults={
            'name': category_data['title'],
            'slug': category_data['key'],
            'url': category_data['webUri'],
        }
    )


def create_or_update_photos(product, photos_data):
    for photo_data in photos_data:
        upload = photo_data['upload']
        crop_url = upload['cropUrlTemplate'].replace('%s', '1600x1600-fit')
        Photo.objects.update_or_create(
            photo_id=photo_data['id'],
            defaults={
                'product': product,
                'uuid': upload['uuid'],
                'file_size': upload['fileSize'],
                'width': upload['width'],
                'height': upload['height'],
                'crop_url_template': crop_url,
            }
        )


def get_product_single(product_id):
    url = f"https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/{product_id}/card"
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random

    try:
        response = requests.get(url, headers=dynamic_headers)
        # print(response.json())
        # print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        print(f"Status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Failed to fetch product {product_id}")
            return None

        data = response.json()
        content = data.get('content')
        if not content:
            print(f"Error: product {product_id} has no content")
            return None

        card = content.get('card')
        if not card:
            print(f"Error: product {product_id} has no card")
            return None
        price_data = card.get('price') or {}
        region_data = card.get('region') or {}
        # Extract fields
        product_data = {
            'product_id': card.get('id'),
            'slug': card.get('slug'),
            'title': card.get('title'),
            'description': card.get('description'),
            'price': (price_data.get('value') or 0) / 100,
            'currency': price_data.get('currency', 'USD'),
            'region': region_data.get('title', ''),
            'url': card.get('webUri'),
            'published_at': card.get('publishedAt'),
            'business': card.get('business'),
            'courier_delivery': card.get('courierDelivery'),
            'is_parsed': True,
        }

        # Extract type, status, and developer from features
        for feature in card['features']:
            if feature['title'] == 'Toifa' and feature['featureValues']:
                product_data['type'] = feature['featureValues'][0]['formattedValue']
            elif feature['title'] == 'Holat' and feature['featureValues']:
                product_data['status'] = feature['featureValues'][0]['formattedValue']
            elif feature['title'] == 'Ishlab chiqaruvchi' and feature['featureValues']:
                product_data['developer'] = feature['featureValues'][0]['formattedValue']

        # Update or create product
        product, created = Product.objects.update_or_create(
            product_id=product_id,
            defaults=product_data
        )

        # Update or create category
        category_data = content.get('relatedCategory')
        if category_data:
            create_category(category_data)
        else:
            print(f"Warning: product {product_id} has no relatedCategory")

        # Update or create photos
        if card.get('photos'):
            create_or_update_photos(product, card['photos'])

        print(f"Product {product_data['product_id']} {'created' if created else 'updated'} successfully.")
        return product_data

    except Exception as e:
        print(f"Error processing product {product_id}: {e}")
        return None


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # get_product_single(62719685)
        products = Product.objects.filter(is_parsed=False).order_by('created_at')
        print(f"Found {products.count()} products to parse.")
        print("Starting to fetch product details...")
        i= 0
        for product in products:
            i += 1
            print(f"Processing product {i}/{products.count()}: {product.product_id}")
            get_product_single(product.product_id)
            print(100*'*')
            time.sleep(0.01)

