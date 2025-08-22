import random
import re
import tempfile
import time
from decimal import Decimal
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tabulate import tabulate

from ...models import Category, Product
from ...proxies import proxy_list  # Import your proxy list from the correct module

import time
import random
import tempfile
from typing import Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException


# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC

class YandexMarketScraper:
    def __init__(self, url: str, proxy_list: list):
        self.url = url
        self.proxy_list = proxy_list
        self.high_rating_clicked = False
        self.driver = None

    def check_captcha(self) -> bool:
        if "showcaptcha" in self.driver.current_url:
            print("🛑 CAPTCHA aniqlandi (URL orqali)")
            self.driver.quit()
            return True

        try:
            title = self.driver.title
            if "Доступ ограничен" in title or "Подтвердите" in title:
                print("🛑 CAPTCHA aniqlandi (title orqali)")
                self.driver.quit()
                return True
        except Exception as e:
            print(f"❗ CAPTCHA tekshiruvda xatolik: {e}")
        return False

    def close_popup_if_exists(self):
        main_window = self.driver.current_window_handle
        existing_windows = self.driver.window_handles

        try:
            close_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-auto="close-popup"]')
            close_btn.click()
            print("❎ Modal popup yopildi")
        except NoSuchElementException:
            pass

        try:
            login_popup = self.driver.find_element(By.CSS_SELECTOR, 'div[data-baobab-name="login_popup"]')
            if login_popup.is_displayed():
                print("⚠️ Login popup aniqlandi")
                ActionChains(self.driver).move_by_offset(300, 300).click().perform()
                print("✅ Login popup yopildi (offset click)")
        except NoSuchElementException:
            pass

        new_windows = self.driver.window_handles
        if len(new_windows) > len(existing_windows):
            print("🚨 Yangi sahifa ochildi — uni yopamiz")
            for window_handle in new_windows:
                if window_handle != main_window:
                    self.driver.switch_to.window(window_handle)
                    self.driver.close()
                    print("❌ Yangi sahifa yopildi")
            self.driver.switch_to.window(main_window)
            print("🔙 Asosiy sahifaga qaytildi")

    def accept_cookie_popup(self):
        try:
            btn = self.driver.find_element(By.ID, "gdpr-popup-v3-button-all")
            if btn.is_displayed():
                self.driver.execute_script("arguments[0].click();", btn)
                print("✅ Cookie popup: 'Allow all' bosildi")
        except NoSuchElementException:
            pass

    def close_new_page_if_opened(self):
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                main_handle = handles[0]
                for handle in handles[1:]:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                self.driver.switch_to.window(main_handle)
                print("🗂️ Yangi ochilgan tab yopildi, asosiy tabga qaytildi.")
        except NoSuchWindowException:
            print("⚠️ Tab yopishda xatolik yuz berdi.")

    def parse_yandex_card_live_count(self, html_content: str) -> int:
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = soup.find_all("article", {"data-auto": "searchOrganic"})
        print(f"🔢 Live card count: {len(articles)} ------******------")
        return len(articles)

    def scroll_and_collect(self) -> Optional[str]:
        scroll_increment = 500
        max_scrolls = 10000
        scroll_count = 0
        stagnant_count = 0
        max_stagnant_count = 30

        stagnant_product_count = 0
        last_p_count = -1
        last_page_height = 0

        self.driver.execute_script("document.body.style.zoom='30%'")
        print(f"🌐 Initial page height: {self.driver.execute_script('return document.body.scrollHeight')}")

        try:
            while scroll_count < max_scrolls:
                p_count = self.parse_yandex_card_live_count(self.driver.page_source)

                if p_count == last_p_count:
                    stagnant_product_count += 1
                else:
                    stagnant_product_count = 0

                last_p_count = p_count

                if stagnant_product_count >= 5:
                    print("⬆ Product soni 2 martadan beri o'zgarmadi, 2 qadam orqaga scroll qilamiz")
                    self.driver.execute_script(f"window.scrollBy(0, {-scroll_increment * 1});")
                    stagnant_product_count = 0
                    time.sleep(2)
                    continue

                if p_count > 999:
                    return self.driver.page_source

                print(f"\n🔄 Scroll #{scroll_count + 1} / {max_scrolls}")

                if self.check_captcha():
                    return None

                self.accept_cookie_popup()
                self.close_popup_if_exists()
                self.close_new_page_if_opened()

                current_page_height = self.driver.execute_script("return document.body.scrollHeight")
                if current_page_height == last_page_height:
                    stagnant_count += 1
                    print(f"⚠️ Sahifa balandligi o'zgarmadi. Stagnant count: {stagnant_count}/{max_stagnant_count}")
                    if stagnant_count >= max_stagnant_count:
                        print("✅ Sahifa balandligi 10 ta scroll davomida o'zgarmadi. Scroll tugadi.")
                        return self.driver.page_source
                else:
                    stagnant_count = 0
                    last_page_height = current_page_height

                scroll_pause = 1.0 if stagnant_count > 0 else 1.5
                self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                scroll_count += 1
                print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
                time.sleep(scroll_pause)

                try:
                    if self.driver.find_element(By.CSS_SELECTOR, '[data-auto="pagination-next"]'):
                        print("🔁 Davom etmoqda...")
                    else:
                        print("✅ Oxirgi sahifa topildi. Scroll tugadi.")
                        return self.driver.page_source
                except NoSuchElementException:
                    print("✅ Oxirgi sahifa topildi. Scroll tugadi.")
                    return self.driver.page_source

        except Exception as e:
            print(f"❌ Scroll jarayonida xatolik: {e}")
            return None
        finally:
            self.close_new_page_if_opened()

    def load_and_parse(self) -> Optional[str]:
        """
        Bu metod tasodifiy proksi-server yordamida Chrome brauzerini ishga tushiradi,
        belgilangan URL manzilga kiradi, sahifani oxirigacha aylantirib (scroll),
        to'liq HTML tarkibini qaytaradi. Docker va server muhiti uchun moslashtirilgan.
        """
        random_proxy = random.choice(self.proxy_list)
        print(f"Random proxy: {random_proxy}")

        options = Options()
        service = Service()  # Service obyektini yaratamiz

        # --- Docker konteyneri ichidagi aniq manzillarni ko'rsatamiz ---
        # apt-get orqali o'rnatilgan Chromium brauzerining manzili
        options.binary_location = "/usr/bin/chromium"
        # apt-get orqali o'rnatilgan drayverning manzili
        service = Service('/usr/bin/chromedriver')
        # -----------------------------------------------------------------

        # Aniqlanishdan saqlanish va optimallashtirish sozlamalari
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f'--proxy-server={random_proxy}')

        # Sahifalarni tezroq yuklash uchun rasmlarni o'chirish
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        # Har safar yangi, toza profil bilan ochish
        user_data_dir = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={user_data_dir}")

        self.driver = None  # Xatolik yuz berganda to'g'ri yopilishi uchun
        try:
            # Brauzer va drayverning aniq manzillari bilan ishga tushiramiz
            self.driver = webdriver.Chrome(service=service, options=options)

            self.driver.get(self.url)
            print(f"🔗 Navigating to: {self.url}")
            time.sleep(5)

            self.driver.execute_script("document.body.style.zoom='30%'")
            try:
                ActionChains(self.driver).move_by_offset(200, 200).click().perform()
            except Exception as e:
                print(f"❌ Birinchi bosishda xatolik (jiddiy emas): {e}")

            if not self.check_captcha():
                html_content = self.scroll_and_collect()
                return html_content
            else:
                print("CAPTCHA aniqlandi, jarayon to'xtatildi.")
                return None

        except Exception as e:
            print(f"❌ Chrome ochishda yoki ishlashida jiddiy xatolik: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
            if 'user_data_dir' in locals() and user_data_dir:
                import shutil
                shutil.rmtree(user_data_dir, ignore_errors=True)


def parse_and_save_yandex_products(html_content: str, category, max_retries: int = 3) -> Dict:
    """
    HTML contentni parse qilib, mahsulotlarni bazaga qo'shadi yoki yangilaydi va statistikani tabulate orqali chiqaradi.

    Args:
        html_content: Yandex sahifasining HTML contenti
        category: Mahsulotlar saqlanadigan kategoriya obyekti
        max_retries: Qayta urinishlar soni

    Returns:
        Dict: created_count, updated_count va umumiy statistika
    """
    created_count = 0
    updated_count = 0
    error_count = 0
    stats = []

    def url_filter(full_url: str):
        parsed = urlparse(full_url)
        path_parts = parsed.path.strip('/').split('/')

        # product_id ni topish (oxirgi element raqam bo‘lishi kerak)
        product_id = ''
        for part in reversed(path_parts):
            if part.isdigit():
                product_id = part
                break

        # To'g'ri URL tuzish: domen alohida, path alohida bo'lishi kerak
        product_part = '/'.join(path_parts[:3]) if len(path_parts) >= 3 else parsed.path.strip('/')
        product_url = f"https://market.yandex.ru/{product_part}"

        # SKU (query string ichida bo‘lsa)
        query_params = parse_qs(parsed.query)
        sku = query_params.get('sku')
        sku = sku[0] if sku else None

        return product_url, product_id, sku

    def parse_single_product(article) -> Dict[str, Optional[str]]:
        """Bitta mahsulotni parse qiladi"""
        product = {}

        try:
            # URL, product_id va sku
            link_elem = article.find('a', href=True)
            if link_elem:
                product['url'], product['product_id'], product['sku'] = url_filter(link_elem['href'])
            else:
                product['url'], product['product_id'], product['sku'] = None, None, None

            # Sarlavha
            title_elem = article.find('span', {'data-auto': 'snippet-title'}) or \
                         article.find(['span', 'div'], string=re.compile(r'.+'))
            product['title'] = title_elem.get_text(strip=True) if title_elem else None

            # Rasm
            img_elem = article.find('img', {'data-auto': 'snippet-image'}) or \
                       article.find('img', src=True)
            product['image'] = img_elem['src'] if img_elem else None

            # Narx
            price_elem = article.find('span', {'data-auto': 'snippet-price-current'}) or \
                         article.find('span', string=re.compile(r'[\d\s]+₽'))
            if price_elem:
                raw_price = price_elem.get_text(strip=True)
                clean_price_str = re.sub(r'[^\d]', '', raw_price)
                product['price'] = Decimal(clean_price_str) if clean_price_str else None
            else:
                product['price'] = None

            # Reyting va sharhlar soni
            rating_elem = article.find('span', {'data-auto': 'reviews'})
            if rating_elem:
                rating_value = rating_elem.find('span', {'class': 'ds-rating__value'})
                product['rating'] = rating_value.get_text(strip=True).replace(',', '.') if rating_value else '0.0'

                reviews_count = rating_elem.find('span', {'class': re.compile(r'ds-text.*ds-text_lineClamp')})
                product['reviews_count'] = re.sub(r'[^\d]', '',
                                                  reviews_count.get_text(strip=True)) if reviews_count else '0'
            else:
                product['rating'] = '0.0'
                product['reviews_count'] = '0'

            return product
        except Exception as e:
            print(f"Mahsulotni parse qilishda xato: {str(e)}")
            return None

    def save_product(product_data: Dict[str, Optional[str]], attempt: int = 1) -> tuple:
        """Mahsulotni bazaga saqlaydi yoki yangilaydi"""
        nonlocal created_count, updated_count, error_count

        if not product_data:
            error_count += 1
            return None, False

        try:
            rating = float(product_data['rating'].replace(',', '.')) if product_data.get('rating') else 0.0
            rating_count = int(product_data['reviews_count']) if product_data.get('reviews_count') else 0

            with transaction.atomic():
                product, created = Product.objects.update_or_create(
                    url=product_data['url'],
                    product_id=product_data['product_id'],
                    sku=product_data['sku'],
                    defaults={
                        'name': product_data['title'],
                        'price': product_data['price'],
                        'category': category,
                        'rating': rating,
                        'rating_count': rating_count,
                    }
                )

                if created:
                    created_count += 1
                    status = "Yaratildi"
                else:
                    updated_count += 1
                    status = "Yangilandi"

                return {
                    'Nomi': product.name,
                    'Narxi': product.price,
                    'Status': status
                }, created

        except Exception as e:
            if attempt < max_retries:
                print(f"Qayta urinish {attempt}/{max_retries}: {str(e)}")
                return save_product(product_data, attempt + 1)
            else:
                print(f"Mahsulotni saqlashda xato: {str(e)}")
                error_count += 1
                return None, False

    # HTML contentni parse qilish
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = soup.find_all("article", {"data-auto": "searchOrganic"})

        for article in articles:
            product_data = parse_single_product(article)
            if product_data:
                product_info, _ = save_product(product_data)
                time.sleep(0.05)
                if product_info:
                    stats.append(product_info)

        # Statistika chiqarish
        if stats:
            print("\nMahsulotlar statistikasi:")
            print(tabulate(stats, headers="keys", tablefmt="grid"))

        # Umumiy statistika
        summary = [
            {"Metrika": "Yaratilgan mahsulotlar", "Soni": created_count},
            {"Metrika": "Yangilangan mahsulotlar", "Soni": updated_count},
            {"Metrika": "Xatolar soni", "Soni": error_count},
            {"Metrika": "Jami ishlov berilgan", "Soni": len(articles)}
        ]
        print("\nUmumiy statistika:")
        print(tabulate(summary, headers="keys", tablefmt="grid"))

        return {
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'total_processed': len(articles)
        }

    except Exception as e:
        print(f"HTMLni parse qilishda xato: {str(e)}")
        error_count += 1
        return {
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'total_processed': 0
        }


def get_available_category():
    with transaction.atomic():
        category = (
            Category.objects
            .select_for_update(skip_locked=True)
            .filter(parsed=False, is_processing=False)
            .first()
        )
        if category:
            category.is_processing = True
            category.save()
            current_category = category
            return current_category
        else:
            print("❗️ No categories found to process.")
            return


class Command(BaseCommand):
    help = 'Create or update products in the database from predefined catalogs'

    def handle(self, *args, **kwargs):
        category_count = Category.objects.filter(parsed=False, is_processing=False).count()
        print(f"🔗 Found {category_count} categories to process.")
        current_category = None

        try:
            for i in range(category_count):
                category = get_available_category()
                if not category:
                    print("❗️ No categories found to process.")
                    return

                current_category = category

                # Har bir category uchun 4 xil URL ustida ishlash
                for url in category.all_urls:
                    print(f"🌐 Parsing: {url}")
                    scraper = YandexMarketScraper(url, proxy_list)
                    html_content = scraper.load_and_parse()
                    parse_and_save_yandex_products(html_content, category)

                # Kategoriya statistikasini yangilash
                category.product_count = Product.objects.filter(category=category).count()
                category.parsed = True
                category.is_processing = False
                category.save()
        except KeyboardInterrupt:
            if current_category:
                current_category.is_processing = False
                current_category.save()
                print(f"\n🛑 Process manually stopped. Set is_processing=False for category: {current_category.name}")
            else:
                print("\n🛑 Process manually stopped before any category processing.")
