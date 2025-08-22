import json
import time

import requests
from django.core.management.base import BaseCommand
from fake_useragent import UserAgent

ua = UserAgent()

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'uz-UZ,uz;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6,en;q=0.5',
    'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzUxMiJ9.eyJqdGkiOiJkZGQwNTJkMi00ZTM0LTQ3OGUtOGU2ZC00NzJiMWVlYmE2OGMiLCJpYXQiOjE3NDgxNjYyODksImV4cCI6MTc0ODE4MDY4OSwidSI6IjA1ZmYwYTRkLTRmMGYtNDRmYi05OTU5LTJiM2MyMjNhYzMxMyIsInV0IjoxMSwiaXAiOiIyMTMuMjMwLjc2LjIyNyIsInQiOjEsImR0IjoiMjAyNS0wNS0yNFQyMTozOToyNy4zNTA4NTNaIiwiZGkiOnsidXVpZCI6IjI3NzZhODFiLTlmMjEtNDkwZi1hMWRmLWNhOGNjODkzMDgzMSIsIm9zIjoibWFjT1MgMTAuMTUuNyIsIm5hbWUiOiJBcHBsZSBNYWNpbnRvc2giLCJhY2NlcHRMYW5ndWFnZSI6InV6In0sInYiOiIxLjMuMi4wIn0.ATbJsG0E1_m9RRzDcLt3IPcxQhZXK8JZlhW4m28Y2EUc5ASAUV0w8mpi_Q_SgFvgDTW-9VwKHbirVzUNTWXgp8iAAPak3u_pjZSu_dweoUlmYffKhhKP9N3Ffucguz8h9QFXiGCP7kqSD8ngBVR5LcTMaFAGyQy8ya8yujURMxCa_7Cq',
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


def get_product_single(product_id):
    url = f"https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/{product_id}/card"
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random

    try:
        response = requests.get(url, headers=dynamic_headers)
        # print(response.json())
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

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
        print(product_data)
        return product_data

    except Exception as e:
        print(f"Error processing product {product_id}: {e}")
        return None


get_product_single(62719685)
