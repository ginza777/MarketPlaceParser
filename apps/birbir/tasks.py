import time

from apps.birbir.gettoken import check_token
from .proxies import proxy_list
from celery import shared_task
from django.db import transaction, OperationalError
from fake_useragent import UserAgent

from .models import Category, Product, Photo, SiteToken

ua = UserAgent()

import requests

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'authorization': '',
    'content-type': 'application/json',
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
    'category': 1000480,
    'courierDeliveryOnly': False,
    'freeOnly': False,
    'urgentSaleOnly': False,
    'sort': 1,
    'features': [],
    'page': 1,
    'perPage': 24,
}


def create_category(category_data):
    with transaction.atomic():
        Category.objects.update_or_create(
            category_id=category_data['id'],
            url=category_data.get('webUri', ),
            defaults={
                'name': category_data['title'],
                'slug': category_data['key'],
            }
        )


def create_or_update_photos(product, photos_data):
    with transaction.atomic():
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


@shared_task
def get_product_single(product_id, token, retries=3, delay=1):
    url = f"https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/{product_id}/card"
    dynamic_headers = headers.copy()

    dynamic_headers['user-agent'] = ua.random
    dynamic_headers['authorization'] = str(token)

    for attempt in range(retries):
        try:
            with transaction.atomic():
                response = requests.get(url, headers=dynamic_headers, timeout=10)  # Timeout qo‘shildi
                time.sleep(0.5)  # API limitlaridan qochish uchun pauza
                if response.status_code != 200:
                    print(f"Failed to fetch product {product_id}: {response.status_code}")
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
                }
                for feature in card['features']:
                    if feature['title'] == 'Toifa' and feature['featureValues']:
                        product_data['type'] = feature['featureValues'][0]['formattedValue']
                    elif feature['title'] == 'Holat' and feature['featureValues']:
                        product_data['status'] = feature['featureValues'][0]['formattedValue']
                    elif feature['title'] == 'Ishlab chiqaruvchi' and feature['featureValues']:
                        product_data['developer'] = feature['featureValues'][0]['formattedValue']
                product, created = Product.objects.update_or_create(
                    product_id=product_id,
                    defaults=product_data
                )
                category_data = content.get('relatedCategory')
                if category_data:
                    create_category(category_data)
                else:
                    print(f"Warning: product {product_id} has no relatedCategory")
                if card.get('photos'):
                    create_or_update_photos(product, card['photos'])
                return product_data
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                print(f"Database locked for product {product_id}, retrying in {delay}s...")
                time.sleep(delay)
                continue
            print(f"Error processing product {product_id}: {e}")
            return None
        except requests.exceptions.Timeout:
            print(f"Timeout fetching product {product_id}, retrying in {delay}s...")
            time.sleep(delay)
            continue
        except Exception as e:
            print(f"Error processing product {product_id}: {e}")
            return None
    return None


@shared_task(ignore_result=False)
def get_product_contact(product_id, token, retries=3, delay=1):
    url = f"https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/{product_id}/contact"
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random
    dynamic_headers['authorization'] = str(token)
    for attempt in range(retries):
        try:
            with transaction.atomic():
                response = requests.post(url, headers=dynamic_headers)
                if response.status_code != 200:
                    print(f"Failed to fetch contact for product {product_id}: {response.status_code}")
                    return None
                product_data = response.json()
                if not product_data or 'content' not in product_data or 'phone' not in product_data['content']:
                    print(f"No phone data found for product {product_id}")
                    return None
                product = Product.objects.get(product_id=product_id)
                product.phone = product_data['content']['phone']
                product.is_parsed = True
                product.save()
                print(f"Phone number for product {product_id} saved.")
                return product_data['content']['phone']
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                print(f"Database locked for contact {product_id}, retrying in {delay}s...")
                time.sleep(delay)
                continue
            print(f"Error fetching contact for product {product_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching contact for product {product_id}: {e}")
            return None
    return None


@shared_task(ignore_result=False)
def get_product_response(category_id, page, token):
    dynamic_headers = headers.copy()
    dynamic_headers['user-agent'] = ua.random
    dynamic_headers['authorization'] = str(token)
    payload = json_data.copy()
    payload['category'] = category_id
    payload['page'] = page
    payload['perPage'] = 100

    import random
    random_proxy = random.choice(proxy_list)
    dynamic_headers['proxy'] = f'https://{random_proxy}'
    print(f"***********Using proxy: {random_proxy}")
    try:

        response = requests.post(
            'https://api.birbir.uz/api/frontoffice/1.3.2.0/offer/feed',
            headers=dynamic_headers,
            json=payload,
            timeout=10  # Timeout qo‘shildi
        )
        time.sleep(0.5)  # API limitlaridan qochish uchun pauza
        if response.status_code == 401:
            token = SiteToken.objects.first().refreshtoken()
            get_product_response.delay(category_id, page)  # Tokenni yangilash va qayta chaqirish
            if not token:
                print("Failed to refresh token, exiting...")
                return []

        if response.status_code != 200:
            print(f"Failed to fetch products for category {category_id}, page {page}: {response.status_code}")
            return []
        products = response.json()['content']['items']
        return products
    except requests.exceptions.Timeout:
        print(f"Timeout fetching products for category {category_id}, page {page}")
        return []
    except Exception as e:
        print(f"Error fetching products for category {category_id}, page {page}: {e}")
        return []


@shared_task(ignore_result=False)
def create_products(products, category_id, token):
    for product in products:
        product_id = product.get("id")
        slug = product.get("slug")
        title = product.get("title")
        url = product.get("webUri")
        try:
            with transaction.atomic():
                # Mahsulotni tekshirish
                existing_product = Product.objects.filter(product_id=product_id).first()
                if existing_product and existing_product.phone and existing_product.is_parsed:
                    print(f"{title} (ID: {product_id}) skip qilindi")
                    continue  # Skip qilamiz

                category = Category.objects.filter(category_id=category_id).first()
                u, created = Product.objects.update_or_create(
                    product_id=product_id,
                    defaults={
                        'slug': slug,
                        'title': title,
                        'category': category,
                        'url': url,
                    }
                )
                # Natija formatini o‘zgartirish
                if created:
                    print(f"{title} (ID: {product_id}) qo'shildi")
                else:
                    print(f"{title} (ID: {product_id}) update qilindi")

                # Chain get_product_single and get_product_contact tasks
                get_product_single.delay(product_id, str(token))
                get_product_contact.delay(product_id, str(token))

            time.sleep(0.5)  # API limitlaridan qochish uchun pauza (oldingi 0.2 dan 0.5 ga oshirildi)
        except OperationalError as e:
            if "database is locked" in str(e):
                print(f"Database locked for product {product_id}, skipping...\n{e}")
                continue
            print(f"Error creating product {product_id}: {e}")
            continue


@shared_task(ignore_result=False)
def fetch_all_products():
    category_list = Category.objects.filter(is_processing=False)
    print("Categoriyalar soni: ", category_list.count())
    current_category = None
    try:
        for category in category_list:
            category_id = category.category_id
            current_category = category
            print(f"\n>>> Processing category ID: {category_id}")
            # check_token
            status, token = check_token()
            page = 1
            while True:
                print(f"\n--- Page: {page} ---")
                current_category.is_processing = True
                current_category.save()
                products = get_product_response(category_id, page, str(token))
                if not products:
                    print("No more products, moving to next category...")
                    break
                create_products(products, category_id, token)
                print(f"Processed {len(products)} products on page {page}")
                #update product count
                category.product_count = Product.objects.filter(category=current_category).count()
                category.is_processing = False
                category.parsed = True
                category.save()
                page += 1
    except KeyboardInterrupt:
        if current_category:
            current_category.is_processing = False
            current_category.save()
            print(
                f"\n🛑 Process manually stopped. Set is_processing=False for category: {current_category.name}")
        else:
            print("\n🛑 Process manually stopped before any category processing.")
