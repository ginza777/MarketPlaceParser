from django.core.management.base import BaseCommand
from fake_useragent import UserAgent
import time
import requests
from bs4 import BeautifulSoup
from ...models import Product, Category, ProductImage, ProductPrice, ProductSpecification
import random


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        ua = UserAgent()
        base_url = "https://olcha.uz"
        products = Product.objects.filter(is_parsed=False).order_by('created_at')
        total_products = products.count()
        print(f"Jami mahsulotlar: {total_products}")
        for idx, product in enumerate(products, start=1):
            product_url = product.product_url
            category_url = product.category.url_category if product.category else ""
            cat_index = idx
            total_categories = total_products

            self.stdout.write(
                f"\n[{cat_index}/{total_categories}] 🔍 Mahsulot: `{product_url}` ni parse qilish boshlandi...")
            get_product(product_url, ua, category_url, cat_index, total_categories)
            self.stdout.write(f"✅ Mahsulot parse qilindi: {product.title}")
            time.sleep(2)


def get_product(product_url, ua, category_url, cat_index, total_categories):
    print(f"\n[{cat_index}/{total_categories}] 📦 Mahsulot yuklanmoqda: {product_url}")
    proxies = [
        "156.253.176.219:3129",
        "156.228.109.233:3129",
        "156.253.172.193:3129",
        "156.233.92.165:3129",
        "156.228.102.51:3129",
        "156.228.76.35:3129",
        "156.228.176.6:3129",
        "156.228.179.96:3129",
        "154.94.13.34:3129",
        "156.242.33.236:3129",
        "45.202.78.87:3129",
        "156.249.60.95:3129",
        "156.248.86.112:3129",
        "156.253.169.154:3129",
        "156.228.114.91:3129",
        "156.228.115.39:3129",
        "154.213.193.206:3129",
        "156.228.125.245:3129",
        "154.91.171.46:3129",
        "156.228.179.221:3129",
        "156.253.171.183:3129",
        "156.228.183.41:3129",
        "156.228.113.7:3129",
        "156.233.74.18:3129",
        "45.201.11.44:3129",
        "154.91.171.218:3129",
        "156.228.77.115:3129",
        "156.228.174.139:3129",
        "156.249.57.181:3129",
        "156.228.86.203:3129",
        "156.249.57.136:3129",
        "156.228.95.139:3129",
        "156.249.56.103:3129",
        "156.228.107.51:3129",
        "154.213.160.97:3129",
        "156.253.176.188:3129",
        "156.233.88.214:3129",
        "156.233.94.16:3129",
        "156.242.33.172:3129",
        "156.228.185.73:3129",
        "154.213.197.121:3129",
        "156.233.91.37:3129",
        "156.233.95.224:3129",
        "156.228.77.192:3129",
        "156.228.98.117:3129",
        "156.228.86.142:3129",
        "156.228.175.8:3129",
        "156.233.89.202:3129",
        "156.242.32.99:3129",
        "156.228.93.184:3129",
        "156.242.42.153:3129",
        "156.242.33.71:3129",
        "154.213.161.77:3129",
        "156.228.113.0:3129",
        "154.94.13.141:3129",
        "156.228.97.147:3129",
        "154.94.14.226:3129",
        "156.228.184.134:3129",
        "156.233.75.13:3129",
        "156.249.62.223:3129",
        "156.249.63.83:3129",
        "156.249.138.61:3129",
        "156.228.114.154:3129",
        "154.213.198.48:3129",
        "156.233.95.131:3129",
        "156.228.180.249:3129",
        "156.253.171.83:3129",
        "154.214.1.86:3129",
        "156.248.84.34:3129",
        "156.242.32.158:3129",
        "156.242.39.172:3129",
        "156.253.173.149:3129",
        "156.228.97.62:3129",
        "156.228.83.240:3129",
        "156.233.90.168:3129",
        "156.253.178.100:3129",
        "156.228.93.141:3129",
        "156.242.44.20:3129",
        "156.242.36.178:3129",
        "156.228.190.105:3129",
        "156.253.165.78:3129",
        "156.253.171.230:3129",
        "156.228.108.240:3129",
        "156.228.92.174:3129",
        "45.201.11.153:3129",
        "156.233.91.109:3129",
        "156.253.168.223:3129",
        "154.213.202.176:3129",
        "156.242.41.252:3129",
        "156.248.85.85:3129",
        "156.242.47.58:3129",
        "45.201.11.154:3129",
        "156.249.63.104:3129",
        "156.253.170.70:3129",
        "156.228.78.254:3129",
        "156.228.119.138:3129",
        "156.253.174.233:3129",
        "156.228.179.189:3129",
        "156.233.86.253:3129",
        "156.242.42.147:3129"
    ]
    headers = {'User-Agent': ua.random}
    proxy_ip = random.choice(proxies)  # Random proxy tanlanadi
    proxies = {
        'http': proxy_ip,
        'https': proxy_ip
    }

    try:
        response = requests.get(product_url, headers=headers, proxies=proxies, timeout=10)
        if response.status_code != 200:
            print(f"❌ Mahsulot sahifasi olinmadi: {product_url} | Status: {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        name = soup.find('h1', class_='catalog-title')
        product_title = name.text.strip() if name else "Noma'lum"

        pricing_block = soup.find('div', class_='product-details__pricing')
        price_text = pricing_block.find('div', class_='price__main').text.strip().replace(" ", "").replace("сум",
                                                                                                           "") if pricing_block else None
        price = float(price_text) if price_text and price_text.isdigit() else 0.0

        shop_address = pricing_block.find('p', class_='product-details__widget-shop-address') if pricing_block else None
        address = shop_address.text.strip() if shop_address else ""

        store_block = pricing_block.find('div',
                                         class_='product-details__widget-shop-name _confirmed') if pricing_block else None
        store = store_block.find('a') if store_block else None
        store_name = store.text.strip() if store else "Olcha.uz"

        specs = {}
        params_block = soup.find('div', class_='product-params product-details__params params')
        if params_block:
            param_rows = params_block.find_all('div', class_='params__row')
            for row in param_rows:
                cols = row.find_all('div', class_='params__col')
                if len(cols) == 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
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
