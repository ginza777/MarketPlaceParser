import random
import re
import time
from decimal import Decimal
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from fake_useragent import UserAgent
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from apps.yandex_market.models import Category, Product
from apps.yandex_market.proxies import proxy_list

created_count = 0
updated_count = 0


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
        category.last_parsed = product.updated_at
        category.parsed = True  # Mark category as parsed
        category.is_processing = False  # Mark as not processing anymore
        category.save()

    except Exception as e:
        print(f"Error creating/updating product: {str(e)}")


from urllib.parse import urlparse, parse_qs

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

    # 🔍 Yangi sahifa ochilganini tekshiramiz
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


def is_last_page(driver):
    try:
        driver.find_element(By.CSS_SELECTOR, '[data-auto="pagination-next"]')
        return False
    except NoSuchElementException:
        return True


# scroll
def scroll_and_collect(driver):
    scroll_pause = 1
    scroll_increment = 300
    max_scrolls = 10000
    scroll_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    print(f"Initial page height: {last_height}")

    # Mahsulot soni va stagnatsiyani kuzatish
    last_product_count = 0
    stagnant_scrolls = 0
    max_stagnant_scrolls = 100

    while scroll_count < max_scrolls:
        print(f"\n\n-------------------\n🔄 Scroll #{scroll_count + 1} / {max_scrolls}")

        if check_captcha(driver):
            print("🚫 Scroll to‘xtatildi - CAPTCHA")
            break

        accept_cookie_popup(driver)
        close_popup_if_exists(driver)

        # Joriy mahsulot sonini olish
        current_product_count = parse_yandex_card_live_count(driver.page_source)

        # Mahsulot soni o'zgarganligini tekshirish
        if current_product_count != last_product_count:
            stagnant_scrolls = 0  # Stagnatsiya hisoblagichini 0 ga qaytarish
            scroll_pause = 2  # Scroll pause ni tiklash

        else:
            stagnant_scrolls += 1
            scroll_pause = 0.1 / stagnant_scrolls  # Stagnatsiya oshgan sari scroll pause oshadi
            print(f"⚠️ Yangi mahsulot topilmadi. Stagnant scrolls: {stagnant_scrolls}/{max_stagnant_scrolls}")

        # Agar 300 ta scroll yangi mahsulotsiz bo'lsa, driver quit qilinsin
        if stagnant_scrolls >= max_stagnant_scrolls:
            print("🚫 Mahsulot soni 300 scroll davomida o‘zgarmadi. Driver to‘xtatilmoqda...")
            driver.quit()
            return  # Funksiyadan chiqish
        last_product_count = current_product_count  # Yangi sonni saqlash

        if stagnant_scrolls > 10:
            scroll_pause = 1 / stagnant_scrolls
            print("🔁 Oxirgi sahifa emas, tepaga va pastga scroll qilinadi")
            driver.execute_script(f"window.scrollBy(0, {-scroll_increment * 2});")
            time.sleep(scroll_pause)
            driver.execute_script(f"window.scrollBy(0, {scroll_increment * 2});")

        time.sleep(scroll_pause)
        # Pastga scroll qilish
        driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
        scroll_count += 1
        print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
        if is_last_page(driver):
            print("✅ Oxirgi sahifaga yetildi")
            break
        else:
            print("🔁 Oxirgi sahifa emas, davom etilmoqda")


def parse_yandex_cards(html_content: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all("article", {"data-auto": "searchOrganic"})
    products = []

    for article in articles:
        product = {}
        link_elem = article.find('a', href=True)
        product['url'], product['product_id'], product['sku'] = url_filter(link_elem['href'])

        title_elem = article.find('span', {'data-auto': 'snippet-title'}) or article.find(['span', 'div'],
                                                                                          string=re.compile(r'.+'))
        product['title'] = title_elem.get_text(strip=True) if title_elem else None

        img_elem = article.find('img', {'data-auto': 'snippet-image'}) or article.find('img', src=True)
        product['image'] = img_elem['src'] if img_elem else None

        price_elem = article.find('span', {'data-auto': 'snippet-price-current'}) or article.find('span',
                                                                                                  string=re.compile(
                                                                                                      r'[\d\s]+₽'))
        if price_elem:
            raw_price = price_elem.get_text(strip=True)
            clean_price_str = re.sub(r'[^\d]', '', raw_price)  # Faqat raqamlarni olib qolamiz
            product['price'] = Decimal(clean_price_str) if clean_price_str else None
        else:
            product['price'] = None

        products.append(product)
    return products


def parse_yandex_card_live_count(html_content: str) -> int:
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all("article", {"data-auto": "searchOrganic"})
    print(f"🔢 Live card count: {len(articles)} ------******------")
    return len(articles)

def click_rating_button(driver):
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-autotest-id='rating']"))
        )
        button.click()
        print("🔘 'Высокий рейтинг' tugmasi bosildi")
        return True
    except Exception as e:
        print(f"❌ Tugmani bosishda xato: {e}")
        return False
def load_and_parse_yandex_market(url: str):
    random_proxy = random.choice(proxy_list)
    options = Options()
    options.add_argument("--window-size=720,900")
    options.add_argument("--window-position=720,0")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    proxy = f"--proxy-server={random_proxy}"
    options.add_argument(proxy)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]})
    driver.execute_cdp_cmd('Network.enable', {})
    time.sleep(5)  # Sahifa yuklanishini kutish
    driver.execute_script("document.body.style.zoom='80%'")
    print(f"🔗 Navigating to: {url}")

    try:
        ActionChains(driver).move_by_offset(200, 200).click().perform()
    except Exception as e:
        print(f"❌ Error during first click: {e}")
    click_rating_button(driver)
    time.sleep(5)  # Rating tugmasi bosilgandan keyin kutish
    #scroll
    scroll_and_collect(driver)
    html = driver.page_source
    driver.quit()

    cards = parse_yandex_cards(html)
    print(f"🔢 Total cards: {len(cards)}")
    return cards


class Command(BaseCommand):
    help = 'Create or update products in the database from predefined catalogs'

    def handle(self, *args, **kwargs):
        base_url= "https://market.yandex.ru/search?text="
        text= "iphone15promax"
        load_and_parse_yandex_market(base_url+ text)
