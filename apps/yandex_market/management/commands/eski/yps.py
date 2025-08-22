import random
import re
import time
from decimal import Decimal
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from django.db.models import Q
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from apps.yandex_market.models import Category, Product
from apps.yandex_market.proxies import proxy_list

def create_or_update_product(product_data: Dict[str, Optional[str]], category):
    global created_count, updated_count
    try:
        product, created = Product.objects.update_or_create(
            url=product_data['url'],
            product_id=product_data['product_id'],
            sku=product_data['sku'],
            defaults={
                'name': product_data['title'],
                'price': product_data['price'],
                'category': category,
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

        print(f"Product {'created' if created else 'updated'}: {product.name}")

        category.product_count = Product.objects.filter(category=category).count()
        category.last_parsed = product.last_update
        category.parsed = True
        category.is_processing = False
        category.save()
        return created

    except Exception as e:
        print(f"Error creating/updating product: {str(e)}")
        return False

def url_filter(full_url: str):
    parsed = urlparse(full_url)
    path_parts = parsed.path.strip('/').split('/')

    product_id = ''
    for part in reversed(path_parts):
        if part.isdigit():
            product_id = part
            break

    product_part = '/'.join(path_parts[:3]) if len(path_parts) >= 3 else parsed.path.strip('/')
    product_url = f"https://market.yandex.ru/{product_part}"

    query_params = parse_qs(parsed.query)
    sku = query_params.get('sku')
    sku = sku[0] if sku else None

    return product_url, product_id, sku

def check_captcha(driver):
    if "showcaptcha" in driver.current_url:
        return True

    try:
        title = driver.title
        if "Доступ ограничен" in title or "Подтвердите" in title:
            print("🛑 CAPTCHA aniqlandi (title orqali)")
            javob = input("🤖 CAPTCHA ni qo'lda yechasizmi? (ha/yo'q): ").strip().lower()
            if javob == 'ha':
                print("⌛ Iltimos, CAPTCHA ni yeching. 15 soniya kutyapman...")
                time.sleep(15)
                return False
            else:
                print("🚫 CAPTCHA o'tkazib yuboriladi.")
                return True
    except Exception as e:
        print(f"❗ CAPTCHA tekshiruvda xatolik: {e}")

    return False

def close_popup_if_exists(driver):
    main_window = driver.current_window_handle
    existing_windows = driver.window_handles

    try:
        close_btn = driver.find_element(By.CSS_SELECTOR, 'button[data-auto="close-popup"]')
        close_btn.click()
        print("❎ Modal popup yopildi")
        time.sleep(1)
    except NoSuchElementException:
        pass

    try:
        login_popup = driver.find_element(By.CSS_SELECTOR, 'div[data-baobab-name="login_popup"]')
        if login_popup.is_displayed():
            print("⚠️ Login popup aniqlandi")
            ActionChains(driver).move_by_offset(300, 300).click().perform()
            time.sleep(1)
            print("✅ Login popup yopildi (offset click)")
    except NoSuchElementException:
        pass

    new_windows = driver.window_handles
    if len(new_windows) > len(existing_windows):
        print("🚨 Yangi sahifa ochildi — uni yopamiz")
        for window_handle in new_windows:
            if window_handle != main_window:
                driver.switch_to.window(window_handle)
                driver.close()
                print("❌ Yangi sahifa yopildi")
        driver.switch_to.window(main_window)
        print("🔙 Asosiy sahifaga qaytildi")

def accept_cookie_popup(driver):
    try:
        btn = driver.find_element(By.ID, "gdpr-popup-v3-button-all")
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn)
            print("✅ Cookie popup: 'Allow all' bosildi")
    except NoSuchElementException:
        pass

def scroll_and_collect(driver):
    scroll_pause = 1
    scroll_increment = 300
    max_scrolls = 10000
    scroll_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    print(f"Initial page height: {last_height}")

    last_product_count = 0
    stagnant_seconds = 0
    max_stagnant_seconds = 5
    retry_attempted = False

    while scroll_count < max_scrolls:
        print(f"\n\n-------------------\n🔄 Scroll #{scroll_count + 1} / {max_scrolls}")

        if check_captcha(driver):
            print("🚫 Scroll to‘xtatildi - CAPTCHA")
            break

        accept_cookie_popup(driver)
        close_popup_if_exists(driver)

        current_product_count = parse_yandex_card_live_count(driver.page_source)

        if current_product_count != last_product_count:
            stagnant_seconds = 0
            scroll_pause = 2
            retry_attempted = False
        else:
            stagnant_seconds += 1
            scroll_pause = 0.1 / stagnant_seconds
            print(f"⚠️ Yangi mahsulot topilmadi. Stagnant seconds: {stagnant_seconds}/{max_stagnant_seconds}")

        if stagnant_seconds >= max_stagnant_seconds:
            if not retry_attempted:
                print("⬆️ Oxiriga yetildi, 1 ta orqaga qaytish...")
                driver.execute_script(f"window.scrollBy(0, {-scroll_increment})")
                time.sleep(5)
                stagnant_seconds = 0
                retry_attempted = True
                continue
            else:
                print("🚫 5 sekunddan keyin ham yangi mahsulot topilmadi. Jarayon tugadi.")
                break

        time.sleep(scroll_pause)
        driver.execute_script(f"window.scrollBy(0, {scroll_increment})")
        scroll_count += 1
        print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
        last_product_count = current_product_count

def parse_yandex_cards(html_content: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    items = soup.find_all("div", class_="_2rw4E")
    products = []

    for item in items:
        product = {}

        link_elem = item.find('a', class_='EQlfk', href=True)
        if not link_elem:
            continue
        product['url'], product['product_id'], product['sku'] = url_filter(link_elem['href'])

        title_elem = item.find('span', {'data-auto': 'snippet-title'})
        product['title'] = title_elem.get_text(strip=True) if title_elem else None

        img_elem = item.find('img', class_='w7Bf7')
        product['image'] = img_elem['src'] if img_elem else None

        price_elem = item.find('span', {'data-auto': 'snippet-price-current'})
        if price_elem:
            raw_price = price_elem.get_text(strip=True)
            clean_price_str = re.sub(r'[^\d]', '', raw_price)
            product['price'] = Decimal(clean_price_str) if clean_price_str else None
        else:
            product['price'] = None

        products.append(product)
    return products

def parse_yandex_card_live_count(html_content: str) -> int:
    soup = BeautifulSoup(html_content, 'html.parser')
    products = soup.find_all("div", {"data-zone-name": "productSnippet"})
    print(f"🔢 Live card count: {len(products)} ------******------")
    return len(products)

def load_and_parse_yandex_market(url: str):
    random_proxy = random.choice(proxy_list)
    options = Options()
    options.add_argument("--window-size=720,900")
    options.add_argument("--window-position=720,0")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--start-maximized")
    options.add_argument(f'--proxy-server={random_proxy}')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]})
    driver.execute_cdp_cmd('Network.enable', {})
    time.sleep(3)
    driver.execute_script("document.body.style.zoom='25%'")
    print(f"🔗 Navigating to: {url}")

    try:
        ActionChains(driver).move_by_offset(200, 200).click().perform()
    except Exception as e:
        print(f"❌ Error during first click: {e}")

    scroll_and_collect(driver)
    html = driver.page_source
    driver.quit()

    cards = parse_yandex_cards(html)
    print(f"🔢 Total cards: {len(cards)}")
    return cards

class Command(BaseCommand):
    help = 'Create or update products in the database from predefined catalogs'

    def handle(self, *args, **kwargs):
        global created_count, updated_count
        created_count = 0
        updated_count = 0
        products = Product.objects.filter(
            Q(category__name='Электроника') | Q(category__parent__name='Электроника'),
            is_processing=False,
            is_related_parsed=False
        )
        print(f"🔗 Found {len(products)} product url  to process.")

        try:
            for product in products:
                current_category = Category.objects.filter(name=product.category.name).first()
                if not current_category:
                    current_category = Category.objects.filter(name='Электроника').first()
                    if not current_category:
                        raise Category.DoesNotExist(f"No category found for {product.category.name} or 'Электроника'")
                print(f"🔗 Processing card url: {product.name} --- URL: {product.url}")
                try:
                    product.is_processing = True
                    product.save()

                    cards = load_and_parse_yandex_market(product.url)

                    for card in cards:
                        create_or_update_product(card, current_category)

                    print(f"✅ {current_category.name} processed.")
                    print(f"Total created products: {created_count}")
                    print(f"Total updated products: {updated_count}")
                    updated_count = 0
                    created_count = 0

                    product.is_processing = False
                    product.is_related_parsed = True
                    product.save()

                except Exception as e:
                    product.is_processing = False
                    product.is_related_parsed = False
                    product.save()
                    print(f"❌ Error processing category {product.name}: {str(e)}")

        except KeyboardInterrupt:
            if product:
                product.is_processing = False
                product.is_related_parsed = False
                product.save()
                print(f"\n🛑 Process manually stopped. Set is_processing=False for category: {product.name}")
            else:
                print("\n🛑 Process manually stopped before any category processing.")