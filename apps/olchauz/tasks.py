import time
from django.db.models import Q
import requests
from bs4 import BeautifulSoup
from celery import shared_task
from django.utils import timezone
from fake_useragent import UserAgent

from .models import Category, Product, ProductPrice, ProductSpecification, ProductImage

# single
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

ua = UserAgent()

@shared_task
def parse_category_products_task():
    base_url = "https://olcha.uz"
    categories = list(
        Category.objects.filter(
            Q(parent_category__isnull=False), Q(last_parsed__isnull=True)
        )
    )
    total_categories = len(categories)

    for cat_index, category in enumerate(categories, start=1):
        url = category.url_category.strip('/')
        page = 1
        parsed_any = False

        if not url.startswith('http'):
            url_path = f"{base_url}/{url}"
        else:
            url = url.replace(base_url, '').lstrip('/')
            url_path = f"{base_url}/{url}"

        print(f"\n📂 Kategoriya [{cat_index}/{total_categories}] → `{category.name}` boshlanmoqda...")

        while True:
            full_url = f"{base_url}/{url}?page={page}"
            headers = {'User-Agent': ua.random}
            response = requests.get(full_url, headers=headers)

            if response.status_code != 200:
                print(f"❌ Sahifa olinmadi: {full_url}")
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            product_blocks = soup.find_all('div', class_='product-card _big _slider')
            total_products = len(product_blocks)

            if total_products == 0:
                print(f"📭 Mahsulot topilmadi: {full_url}")
                break

            print(f"\n📄 Sahifa: {page} | Mahsulotlar soni: {total_products}")

            for index, block in enumerate(product_blocks, start=1):
                url_tag = block.find('a', class_='product-card__link')
                product_url = f"{base_url}{url_tag['href']}" if url_tag and url_tag.get('href') else None

                if product_url:
                    product_obj, created = Product.objects.get_or_create(
                        product_url=product_url,
                        defaults={
                            'title': "",
                            'brand': None,
                            'sku': None,
                            'category': category,
                            'description': "",
                        }
                    )

                    status = "➕ Yaratildi" if created else "🔄 Mavjud"
                    print(f"    [{index}/{total_products}] {status}: {product_url}")
                    parsed_any = True

            page += 1

        if parsed_any:
            category.last_parsed = timezone.now()
            category.save(update_fields=["last_parsed"])
            print(
                f"✅ Yakunlandi: `{category.name}` | So‘nggi parse: {category.last_parsed.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"⚠️ `{category.name}` uchun mahsulotlar topilmadi.")
            category.last_parsed = timezone.now()
            category.save(update_fields=["last_parsed"])

@shared_task
def get_detail_product():
    ua = UserAgent()
    products = Product.objects.filter(is_parsed=False).order_by('created_at')
    total_products = products.count()
    print(f"Jami mahsulotlar: {total_products}")
    for idx, product in enumerate(products, start=1):
        product_url = product.product_url
        category_url = product.category.url_category if product.category else ""
        cat_index = idx
        total_categories = total_products

        print(
            f"\n[{cat_index}/{total_categories}] 🔍 Mahsulot: `{product_url}` ni parse qilish boshlandi...")
        get_product(product_url, ua, category_url, cat_index, total_categories)
        print(f"✅ Mahsulot parse qilindi: {product.title}")

def get_product(product_url, ua, category_url, cat_index, total_categories):
    print(f"\n[{cat_index}/{total_categories}] 📦 Mahsulot yuklanmoqda: {product_url}")
    headers = {'User-Agent': ua.random}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ Mahsulot sahifasi olinmadi: {product_url} | Status: {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        name = soup.find('h1', class_='catalog-title')
        product_title = name.text.strip() if name and name.text else "Noma'lum"

        pricing_block = soup.find('div', class_='product-details__pricing')
        price_text = (pricing_block.find('div', class_='price__main').text.strip().replace(" ", "").replace("сум", "")
                      if pricing_block and pricing_block.find('div', class_='price__main') else None)
        price = float(price_text) if price_text and price_text.isdigit() else 0.0

        shop_address = pricing_block.find('p', class_='product-details__widget-shop-address') if pricing_block else None
        address = shop_address.text.strip() if shop_address and shop_address.text else ""

        store_block = pricing_block.find('div', class_='product-details__widget-shop-name _confirmed') if pricing_block else None
        store = store_block.find('a') if store_block else None
        store_name = store.text.strip() if store and store.text else "Olcha.uz"

        specs = {}
        params_block = soup.find('div', class_='product-params product-details__params params')
        if params_block:
            param_rows = params_block.find_all('div', class_='params__row')
            for row in param_rows:
                cols = row.find_all('div', class_='params__col')
                if len(cols) == 2:
                    key = cols[0].text.strip() if cols[0] and cols[0].text else ""
                    value = cols[1].text.strip() if cols[1] and cols[1].text else ""
                    specs[key] = value

        image_urls = []
        image_block = soup.find_all('div', class_='img-wrapper')
        for image in image_block:
            img = image.find('img')
            if img and img.get('src'):
                image_urls.append(img['src'])

        category_url = category_url.strip()
        category = Category.objects.filter(url_category=category_url).first()
        if not category:
            print(f"❗ Kategoriya topilmadi: {category_url}")
        else:
            print(f"📂 Kategoriya: {category.name}")

        product, created = Product.objects.update_or_create(
            product_url=product_url,
            defaults={
                'title': product_title,
                'brand': None,
                'sku': None,
                'category': category,
                'description': "",
            }
        )
        print(f"📌 {'Yaratildi' if created else 'Yangilandi'}: {product.title}")

        for idx, img_url in enumerate(image_urls):
            img_obj, created = ProductImage.objects.get_or_create(
                product=product,
                image_url=img_url,
                defaults={'is_main': idx == 0}
            )
            print(f"🖼️ {'Yaratildi' if created else 'Mavjud'} rasm: {img_url}")

        price_obj, created = ProductPrice.objects.update_or_create(
            product=product,
            store=store_name,
            defaults={
                'price': price,
                'currency': 'UZS',
                'address': address,
            }
        )
        product.is_parsed = True
        product.save(update_fields=['is_parsed'])

        print(f"💰 {'Yaratildi' if created else 'Yangilandi'} narx: {store_name} - {price} UZS")

        for key, value in specs.items():
            spec_obj, created = ProductSpecification.objects.update_or_create(
                product=product,
                key=key,
                defaults={'value': value}
            )
            print(f"⚙️ {'Yaratildi' if created else 'Yangilandi'} xususiyat: {key}: {value}")

    except Exception as e:
        print(f"🔥 Xatolik: {str(e)}")