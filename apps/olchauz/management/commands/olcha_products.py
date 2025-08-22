from django.core.management.base import BaseCommand
from fake_useragent import UserAgent
import time
import requests
from bs4 import BeautifulSoup
from ...models import Product, Category, ProductImage, ProductPrice, ProductSpecification

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        ua = UserAgent()
        base_url = "https://olcha.uz"
        category_list = list(Category.objects.filter(parent_category__isnull=False).values_list('url_category', flat=True))
        total_categories = len(category_list)

        for idx, category_url in enumerate(category_list, start=1):
            if category_url.startswith('http'):
                normalized_url = category_url.replace(base_url, '')
            else:
                normalized_url = category_url.lstrip('/')

            self.stdout.write(f"\n[{idx}/{total_categories}] 🔍 Kategoriya: `{normalized_url}` ni parse qilish boshlandi...")
            products = self.get_products(normalized_url, ua, base_url, idx, total_categories)
            self.stdout.write(
                f"✅ Tugadi: {normalized_url}\n"
                f"   ├─ Jami:       {products['total']} ta mahsulot\n"
                f"   ├─ Yaratilgan: {products['created']}\n"
                f"   ├─ Yangilangan:{products['updated']}\n"
                f"   └─ Rad etilgan:{products['rejected']}\n"
                + "#" * 40
            )
            time.sleep(3)

    def get_products(self, category_url, ua, base_url, cat_index, total_categories):
        products = {"total": 0, "updated": 0, "created": 0, "rejected": 0}
        page = 1

        while True:
            headers = {'User-Agent': ua.random}
            url = f"{base_url}/{category_url.lstrip('/')}?page={page}"
            self.stdout.write(f"\n📄 [{cat_index}/{total_categories}] Sahifa {page}: {url}")

            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    self.stdout.write(f"❌ Xatolik: Sahifa {page} olinmadi.")
                    break

                soup = BeautifulSoup(response.content, 'html.parser')
                product_elements = soup.find_all('div', class_='product-card _big _slider')
                total_on_page = len(product_elements)
                self.stdout.write(f"🔎 Topildi: {total_on_page} ta mahsulot")
                products['total'] += total_on_page

                if not product_elements:
                    self.stdout.write("⚠️ Mahsulot topilmadi.")
                    break

                for idx, block in enumerate(product_elements, start=1):
                    self.stdout.write(f"   📦 [{idx}/{total_on_page}] mahsulot")

                    url_tag = block.find('a', class_='product-card__link')
                    product_url = url_tag.get('href', None) if url_tag else None
                    if product_url and not product_url.startswith('http'):
                        product_url = f"{base_url}{product_url}"

                    name_tag = block.find('div', class_='product-card__brand-name')
                    name = name_tag.text.strip() if name_tag else None

                    if not product_url or not name:
                        products['rejected'] += 1
                        continue
                    category_url = category_url.strip()
                    category = Category.objects.filter(url_category=category_url).first()
                    if not category:
                        print(f"❗ Kategoriya topilmadi: {category_url}")
                    else:
                        print(f"📂 Kategoriya: {category.name}")
                    _, created = Product.objects.update_or_create(
                        product_url=product_url,
                        defaults={'title': name,
                                  'category': category,
                                  }
                    )
                    # get_product(product_url, ua, category_url, cat_index, total_categories)
                    products['created' if created else 'updated'] += 1

                page += 1
                time.sleep(0.01)

            except Exception as e:
                self.stdout.write(f"🔥 Xato yuz berdi sahifa {page}: {str(e)}")
                products['rejected'] += 1
                break

        return products


def get_product(product_url, ua, category_url, cat_index, total_categories):
    print(f"\n[{cat_index}/{total_categories}] 📦 Mahsulot yuklanmoqda: {product_url}")
    headers = {'User-Agent': ua.random}

    try:
        response = requests.get(product_url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Mahsulot sahifasi olinmadi: {product_url}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        name = soup.find('h1', class_='catalog-title')
        product_title = name.text.strip() if name else "Noma'lum"

        pricing_block = soup.find('div', class_='product-details__pricing')
        price_text = pricing_block.find('div', class_='price__main').text.strip().replace(" ", "").replace("сум", "") if pricing_block else None
        price = float(price_text) if price_text and price_text.isdigit() else 0.0

        shop_address = pricing_block.find('p', class_='product-details__widget-shop-address') if pricing_block else None
        address = shop_address.text.strip() if shop_address else ""

        store_block = pricing_block.find('div', class_='product-details__widget-shop-name _confirmed') if pricing_block else None
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