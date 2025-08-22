import random
import re
import time
from decimal import Decimal
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db.models import Q
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from apps.yandex_market.models import Category, Product
from apps.yandex_market.proxies import proxy_list

created_count = 0
updated_count = 0
high_rating_clicked = False


def create_or_update_product(product_data: Dict[str, Optional[str]], category):
    global created_count, updated_count, high_rating_clicked

    try:
        rating = 0.0
        rating_count = 0

        if product_data.get('rating'):
            try:
                rating = float(product_data['rating'].replace(',', '.'))
            except ValueError:
                rating = 0.0

        if product_data.get('reviews_count'):
            try:
                rating_count = int(product_data['reviews_count'])
            except ValueError:
                rating_count = 0

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
        else:
            updated_count += 1

        print(f"Product {'created' if created else 'updated'}: {product.name}")

        category.product_count = Product.objects.filter(category=category).count()
        category.last_parsed = product.updated_at
        category.parsed = True
        category.is_processing = False
        category.save()
        high_rating_clicked = False

    except Exception as e:
        print(f"Error creating/updating product: {str(e)}")


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
            raise True
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
    except NoSuchElementException:
        pass

    try:
        login_popup = driver.find_element(By.CSS_SELECTOR, 'div[data-baobab-name="login_popup"]')
        if login_popup.is_displayed():
            print("⚠️ Login popup aniqlandi")
            ActionChains(driver).move_by_offset(300, 300).click().perform()
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


def click_high_rating_safe(driver, timeout=1):
    try:
        # Tugma mavjudligini kutish
        button = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'высокий рейтинг')]"))
        )
        # Scroll qilish
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        # Bosish uchun tayyor holatga kelishini kutish
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'высокий рейтинг')]"))
        )
        # JavaScript orqali bosish
        driver.execute_script("arguments[0].click();", button)
    except Exception:
        pass


def check_captcha_head(driver, url, proxy_list, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            # CAPTCHA sahifasi URL orqali tekshiriladi
            if "showcaptcha" in driver.current_url:
                print(f"🛑 CAPTCHA aniqlandi (URL orqali), urinish: {attempt + 1}")
                driver.quit()
                # Yangi proxy bilan qayta urinish
                return load_and_parse_yandex_market(url)

            # CAPTCHA elementi sahifada mavjudligini tekshirish
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CAPTCHA')]"))
            )
            print(f"🛑 CAPTCHA elementi sahifada aniqlandi, urinish: {attempt + 1}")
            driver.quit()
            # Yangi proxy bilan qayta urinish
            return load_and_parse_yandex_market(url)

        except Exception as e:
            if "CAPTCHA" not in str(e):
                print("✅ CAPTCHA aniqlanmadi")
                return True
            print(f"❌ Xato: {e}")
            attempt += 1
            if attempt == max_attempts:
                raise Exception("Maksimal urinishlar soni tugadi, CAPTCHA hal qilinmadi")

    return False


def click_reviews_link_safe(driver, timeout=1):
    try:
        link = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-auto="reviews-all-link"]'))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", link)
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-auto="reviews-all-link"]'))
        )
        driver.execute_script("arguments[0].click();", link)
        print("✅ 'Otzivlar' havolasi bosildi")
    except:
        pass


# scroll

def scroll_and_collect(driver):
    scroll_increment = 1500
    max_scrolls = 10000
    scroll_count = 0
    stagnant_scrolls = 0
    max_stagnant_scrolls = 10
    last_product_count = 0

    driver.execute_script("document.body.style.zoom='50%'")
    print(f"🌐 Initial page height: {driver.execute_script('return document.body.scrollHeight')}")

    try:
        while scroll_count < max_scrolls:
            print(f"\n🔄 Scroll #{scroll_count + 1} / {max_scrolls}")

            if check_captcha(driver):
                print("🚫 CAPTCHA aniqlandi. Scroll to‘xtatildi.")
                break

            accept_cookie_popup(driver)
            close_popup_if_exists(driver)
            click_reviews_link_safe(driver)

            if scroll_count == 2:
                click_high_rating_safe(driver)
            if last_product_count > 900:
                return driver.page_source
            # Mahsulotlar sonini aniqlash
            try:
                current_product_count = parse_yandex_card_live_count(driver.page_source)
            except Exception as e:
                print(f"⚠️ Product count aniqlanmadi: {e}")
                current_product_count = 0

            # Mahsulotlar soni o‘zgarganmi
            if current_product_count != last_product_count:
                stagnant_scrolls = 0
                scroll_pause = 1.5
            else:
                stagnant_scrolls += 1
                scroll_pause = min(2.5, 1 + stagnant_scrolls * 0.3)
                print(f"⚠️ Yangi mahsulot topilmadi. Stagnant scrolls: {stagnant_scrolls}/{max_stagnant_scrolls}")

            if stagnant_scrolls >= max_stagnant_scrolls:
                print("🚫 Mahsulot soni o‘zgarmayapti. Scroll to‘xtatildi.")
                break

            last_product_count = current_product_count

            # Scroll pastga → agar kerak bo‘lsa, tepaga va yana pastga
            if stagnant_scrolls >= 5:
                print("🔁 Scroll yuqoriga va pastga")
                driver.execute_script(f"window.scrollBy(0, {-scroll_increment * 2});")
                time.sleep(0.5)
                driver.execute_script(f"window.scrollBy(0, {scroll_increment * 2});")

            driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
            scroll_count += 1
            print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
            time.sleep(scroll_pause)

            if is_last_page(driver):
                print("✅ Oxirgi sahifa topildi. Scroll tugadi.")
                break
            else:
                print("🔁 Davom etmoqda...")

    except Exception as e:
        print(f"❌ Scroll jarayonida xatolik: {e}")


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
            clean_price_str = re.sub(r'[^\d]', '', raw_price)  # Faqat raqamlarni olamiz
            product['price'] = Decimal(clean_price_str) if clean_price_str else None
        else:
            product['price'] = None

        # Rating va otziv sonini olish
        rating_elem = article.find('span', {'data-auto': 'reviews'})
        if rating_elem:
            rating_value = rating_elem.find('span', {'class': 'ds-rating__value'})
            product['rating'] = rating_value.get_text(strip=True) if rating_value else 0.0

            reviews_count = rating_elem.find('span', {'class': re.compile(r'ds-text.*ds-text_lineClamp')})
            product['reviews_count'] = re.sub(r'[^\d]', '',
                                              reviews_count.get_text(strip=True)) if reviews_count else 0
        else:
            product['rating'] = 0.0
            product['reviews_count'] = 0

        products.append(product)
    return products


def parse_yandex_card_live_count(html_content: str) -> int:
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all("article", {"data-auto": "searchOrganic"})
    print(f"🔢 Live card count: {len(articles)} ------******------")
    return len(articles)


def load_and_parse_yandex_market(url: str):
    random_proxy = random.choice(proxy_list)
    options = Options()
    options.add_argument("--window-size=720,900")  # Yarim ekran
    options.add_argument("--window-position=720,0")

    # options.add_argument("--blink-settings=imagesEnabled=false")

    options.add_argument("--start-maximized")
    options.add_argument(f'--proxy-server={random_proxy}')  # Set random proxy
    # options.add_argument("--disable-gpu")
    # options.add_argument("--disable-javascript")  # Disable JS to test if it affects scrolling
    options.add_argument("--no-sandbox")  # Improve stability
    options.add_argument("--disable-dev-shm-usage")  # Prevent memory issues
    options.add_argument("--disable-blink-features=AutomationControlled")
    # zoom

    service = Service('/usr/local/bin/chromedriver', port=7979)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    # driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]})
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_script("document.body.style.zoom='50%'")
    time.sleep(1)  # Sahifa yuklanishini kutish

    print(f"🔗 Navigating to: {url}")

    try:
        ActionChains(driver).move_by_offset(200, 200).click().perform()
    except Exception as e:
        print(f"❌ Error during first click: {e}")
    time.sleep(0.5)  # Sahifa elementlari yuklanishini kutish
    check_captcha_head(driver=driver, url=url, proxy_list=proxy_list)
    html = scroll_and_collect(driver)
    # parse qil yoki saqla

    cards = parse_yandex_cards(html)
    print(f"🔢 Total cards: {len(cards)}")
    driver.quit()
    return cards


class Command(BaseCommand):
    help = 'Create or update products in the database from predefined catalogs'
    global high_rating_clicked

    def handle(self, *args, **kwargs):
        category_urls = Category.objects.filter(
            Q(parent__name='Электроника') | Q(name='Электроника'),
            parsed=False,
            is_processing=False
        ).values_list('url', flat=True)
        print(f"🔗 Found {len(category_urls)} categories to process.")

        current_category = None  # hozir ishlayotgan category ni saqlash uchun

        # current_category=Category.objects.filter(name='Электроника').first()
        # category_urls = ["https://market.yandex.ru/catalog--smartfony-i-gadzhety/26893630/list?how=rating&rs=eJwz0v_EqMPBKLDwEKsEg8bLU6wah46zajwG0rsPs2rs6DypqHH-8SU2jfYj-xU1dr_arwgAu40UOg%2C%2C&glfilter=7893318%3A153043"]  # QuerySet ni list ga aylantirish
        try:
            for category_url in category_urls:
                high_rating_clicked = False  # Har bir kategoriya uchun yuqori reyting tugmasi bosilishini reset qilamiz
                current_category = Category.objects.get(url=category_url)
                print(f"🔗 Processing category: {current_category.name} --- URL: {current_category.url}")
                try:
                    current_category.is_processing = True
                    current_category.save()

                    cards = load_and_parse_yandex_market(category_url)

                    global created_count, updated_count
                    for card in cards:
                        create_or_update_product(card, current_category)

                    print(f"✅ {current_category.name} processed.")
                    print(f"Total created products: {created_count}")
                    print(f"Total updated products: {updated_count}")
                    created_count = 0
                    updated_count = 0

                    current_category.parsed = True
                    current_category.is_processing = False
                    current_category.save()

                except Exception as e:
                    current_category.is_processing = False
                    current_category.save()
                    print(f"❌ Error processing category {current_category.name}: {str(e)}")

        except KeyboardInterrupt:
            if current_category:
                current_category.is_processing = False
                current_category.save()
                print(f"\n🛑 Process manually stopped. Set is_processing=False for category: {current_category.name}")
            else:
                print("\n🛑 Process manually stopped before any category processing.")
