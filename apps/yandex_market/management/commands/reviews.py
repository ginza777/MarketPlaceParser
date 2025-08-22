import logging
import random
import tempfile
import time
from decimal import Decimal
from decimal import InvalidOperation
from typing import Optional
from typing import Tuple

from bs4 import BeautifulSoup
from colorlog import ColoredFormatter
from django.core.management import BaseCommand
from django.db import transaction, IntegrityError
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException, NoSuchWindowException,
)
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tabulate import tabulate

from apps.yandex_market.models import Product, ReviewPhoto, Review, ProductImage
from ...proxies import proxy_list

logging.basicConfig(level=logging.INFO)
formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    log_colors={'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red'}
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.getLogger().handlers = [handler]
logger = logging.getLogger('django.db.backends')

logging.basicConfig(level=logging.INFO)
formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    log_colors={'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red'}
)


# single product
class YandexMarketSingleScraper:
    def __init__(self, url: str, proxy_list: list):
        self.url = url
        self.proxy_list = proxy_list
        self.high_rating_clicked = False
        self.driver = None
        self.labels_expanded = False
        self.product_review_expanded = False
        self.product_review_link = None
        self.review_url = ""

    def check_captcha(self):
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

    def expand_both_labels_handler(self):
        """
        'Показать полностью' va 'Все характеристики' tugmalarini kengaytiradi, yozuv ustiga bosish orqali.
        """
        if self.labels_expanded:
            logging.info("✅ Tugmalar allaqachon kengaytirilgan, o'tkazib yuborilmoqda.")
            return

        wait = WebDriverWait(self.driver, 15)  # Kutish vaqtini 15 sekund
        texts_to_click = ["Показать полностью", "Все характеристики"]

        for text in texts_to_click:
            try:
                # Tugma ichidagi <span> elementini topish
                span_xpath = f"//button[contains(@class, 'ds-button')]//span[contains(text(), '{text}')]"
                span_element = wait.until(EC.element_to_be_clickable((By.XPATH, span_xpath)))

                # Elementni ko'rinadigan joyga aylantirish
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                                           span_element)
                time.sleep(0.2)  # Scroll dan keyin qisqa pauza

                # Span elementining ko'rinadigan va bosiladigan ekanligini tekshirish
                if not span_element.is_displayed() or not span_element.is_enabled():
                    logging.warning(f"⚠️ '{text}' yozuvi ko'rinmaydi yoki bosilmaydi.")
                    continue

                try:
                    # Span elementiga to'g'ridan-to'g'ri click qilish
                    ActionChains(self.driver).move_to_element(span_element).click().perform()
                    logging.info(f"✅ '{text}' yozuvi bosildi (ActionChains).")
                except ElementClickInterceptedException:
                    logging.warning(f"⚠️ '{text}' yozuvini bosishda xato: Intercepted. JS click bilan qayta urinish...")
                    self.driver.execute_script("arguments[0].click();", span_element)
                    logging.info(f"✅ '{text}' yozuvi JS bilan bosildi.")
                except Exception as e:
                    logging.error(f"❌ '{text}' yozuvini bosishda xatolik: {e}")
                    continue

                time.sleep(0.2)  # Keyingi harakatdan oldin qisqa kutish

            except TimeoutException:
                logging.warning(f"⚠️ '{text}' yozuvi topilmadi (Timeout).")
            except Exception as e:
                logging.error(f"❌ '{text}' yozuvini qayta ishlashda xatolik: {e}")

        self.labels_expanded = True
        logging.info("✅ Barcha tugmalar kengaytirildi.")

    def close_new_page_if_opened(self):
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                main_handle = handles[0]
                # Boshqa barcha tablarni yopamiz
                for handle in handles[1:]:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                self.driver.switch_to.window(main_handle)
                print("🗂️ Yangi ochilgan tab yopildi, asosiy tabga qaytildi.")
        except NoSuchWindowException:
            print("⚠️ Tab yopishda xatolik yuz berdi.")

    def parse_yandex_card_live_count(self, html_content: str) -> int:
        soup = BeautifulSoup(html_content, 'html.parser')
        cards = soup.find_all("div", {"data-zone-name": "productSnippet"})
        print(f"🔢 Live card count: {len(cards)}")
        return len(cards)

    def click_show_more_or_link(self, timeout=1) -> bool:
        if self.product_review_link:
            logging.info(f"🔗 Review link already found: {self.product_review_link}")
            return True
        if self.product_review_expanded:
            logging.info("✅ Reviews already expanded, skipping.")
            return True

        wait = WebDriverWait(self.driver, timeout)
        try:
            container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.Qx1tY')))
            button_count = 0
            max_button_clicks = 3
            while button_count < max_button_clicks:
                try:
                    button = container.find_element(By.TAG_NAME, 'button')
                    button.click()
                    logging.info(f"🖱️ Button clicked (Attempt {button_count + 1})")
                    button_count += 1
                    time.sleep(1)
                    try:
                        a_tag = container.find_element(By.TAG_NAME, 'a')
                        self.product_review_link = a_tag.get_attribute('href')
                        self.product_review_expanded = True
                        self.review_url = self.product_review_link
                        logging.info(f"🔗 Review link found: {self.product_review_link}")
                        return True
                    except:
                        continue
                except:
                    break
            if button_count > 0:
                logging.info("✅ Buttons clicked, no link found.")
                self.product_review_expanded = True
                return True
            logging.warning("❌ No <a> or <button> elements found.")
            self.product_review_expanded = False
            return False
        except TimeoutException:
            logging.warning("❌ div.Qx1tY element not found.")
            return False

    def scroll_and_collect(self) -> Tuple[Optional[str], Optional[str]]:
        scroll_increment = 900
        max_scrolls = 3
        scroll_count = 0
        stagnant_count = 0
        max_stagnant_count = 20
        last_page_height = 0

        self.driver.execute_script("document.body.style.zoom='50%'")
        print(f"🌐 Initial page height: {self.driver.execute_script('return document.body.scrollHeight')}")

        try:
            while scroll_count < max_scrolls:
                print(f"\n🔄 Scroll #{scroll_count + 1} / {max_scrolls}")

                if self.check_captcha():
                    logging.warning("CAPTCHA detected, stopping scroll")
                    return "", self.review_url or ""  # Return empty string
                self.accept_cookie_popup()
                self.close_popup_if_exists()
                self.expand_both_labels_handler()
                self.click_show_more_or_link(timeout=1)
                self.close_popup_if_exists()
                current_page_height = self.driver.execute_script("return document.body.scrollHeight")
                if current_page_height == last_page_height:
                    stagnant_count += 1
                    print(f"⚠️ Sahifa balandligi o'zgarmadi. Stagnant count: {stagnant_count}/{max_stagnant_count}")
                    if stagnant_count >= max_stagnant_count:
                        print("✅ Sahifa balandligi 20 ta scroll davomida o'zgarmadi. Scroll tugadi.")
                        return self.driver.page_source, self.review_url
                else:
                    stagnant_count = 0
                    last_page_height = current_page_height

                scroll_pause = 1.0 if stagnant_count > 0 else 0.5  # Agar stagnation bo'lsa, ko'proq kutish
                self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                scroll_count += 1
                print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
                time.sleep(scroll_pause)
            return self.driver.page_source, self.review_url  # Return tuple if loop completes
        except Exception as e:
            print(f"❌ Scroll jarayonida xatolik: {e}")
            return "", self.review_url or ""  # Return tuple in case of exception
        finally:
            self.close_new_page_if_opened()

    def load_and_parse(self) -> Tuple[Optional[str], Optional[str]]:
        while True:
            random_proxy = random.choice(self.proxy_list)
            options = webdriver.ChromeOptions()
            options.add_argument("--window-size=600,900")

            # options.add_argument('--headless=new')

            options.add_argument("--start-maximized")
            options.add_argument(f'--proxy-server={random_proxy}')
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            user_data_dir = tempfile.mkdtemp()
            options.add_argument(f"--user-data-dir={user_data_dir}")
            prefs = {
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            service = Service('/usr/local/bin/chromedriver', port=random.randint(49152, 65535))
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get(self.url)
            self.driver.execute_script("document.body.style.zoom='25%'")
            time.sleep(4)

            print(f"🔗  Proxy: {random_proxy}----Port: {service.service_url}")

            try:
                ActionChains(self.driver).move_by_offset(200, 200).click().perform()
            except Exception as e:
                print(f"❌ Error during first click: {e}")
            try:
                if not self.check_captcha():
                    html = self.scroll_and_collect()
                    return html
            except Exception as e:
                print(f"❌ Driver error: {e}")

            finally:
                self.driver.quit()
                print("🔚 Driver closed, retrying with a new proxy...")

    def run(self) -> Tuple[Optional[str], Optional[str]]:
        html, review_url = self.scroll_and_collect()
        return html, review_url


class YandexMarketReviewsScraper:
    def __init__(self, url: str, proxy_list: list):
        self.url = url
        self.proxy_list = proxy_list
        self.driver = None

    def check_captcha(self) -> bool:
        if "showcaptcha" in self.driver.current_url:
            print("🛑 CAPTCHA detected (URL)")
            return True

        try:
            title = self.driver.title
            if "Доступ ограничен" in title or "Подтвердите" in title:
                print("🛑 CAPTCHA detected (title)")
                return True
        except Exception as e:
            print(f"❗ CAPTCHA check error: {e}")
        return False

    def click_reviews_all_button(self):
        try:
            # "Отзывы у всех продавцов" tugmasini kutish va bosish
            wait = WebDriverWait(self.driver, 2)
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-auto="reviews-all-link"] a')))
            button.click()
            # Keyingi sahifani yuklash uchun biroz kutish
            time.sleep(1)
        except NoSuchElementException:
            pass
        except TimeoutException:
            pass

    def close_popup_if_exists(self):
        try:
            close_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-auto="close-popup"]')
            close_btn.click()
            print("❎ Modal popup closed")
        except NoSuchElementException:
            pass

        try:
            login_popup = self.driver.find_element(By.CSS_SELECTOR, 'div[data-baobab-name="login_popup"]')
            if login_popup.is_displayed():
                print("⚠️ Login popup detected")
                ActionChains(self.driver).move_by_offset(300, 300).click().perform()
                print("✅ Login popup closed (offset click)")
        except NoSuchElementException:
            pass

    def accept_cookie_popup(self):
        try:
            btn = self.driver.find_element(By.ID, "gdpr-popup-v3-button-all")
            if btn.is_displayed():
                self.driver.execute_script("arguments[0].click();", btn)
                print("✅ Cookie popup: 'Allow all' clicked")
        except NoSuchElementException:
            pass

    def parse_yandex_reviews_count(self, html_content: str) -> int:
        soup = BeautifulSoup(html_content, "html.parser")
        reviews = soup.select('div[data-apiary-widget-name="@card/ReviewItem"]')
        return len(reviews)

    def close_new_page_if_opened(self):
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                main_handle = handles[0]
                # Boshqa barcha tablarni yopamiz
                for handle in handles[1:]:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                self.driver.switch_to.window(main_handle)
                print("🗂️ Yangi ochilgan tab yopildi, asosiy tabga qaytildi.")
        except NoSuchWindowException:
            print("⚠️ Tab yopishda xatolik yuz berdi.")

    def scroll_and_collect(self) -> Optional[str]:
        scroll_increment = 1000  # kichik step
        max_scrolls = 1000
        scroll_count = 0
        stagnant_count = 0
        max_stagnant_count = 5  # 5 marta o‘zgarmasa orqaga
        zero_change_limit = 10  # 10 marta umumiy o‘zgarmasa tugatish
        review_zero_count = 0
        max_zero_count = 3
        last_review_count = 0
        no_change_total = 0
        scroll_positions = []

        self.driver.execute_script("document.body.style.zoom='50%'")
        print(f"🌐 Initial page height: {self.driver.execute_script('return document.body.scrollHeight')}")

        try:
            while scroll_count < max_scrolls:
                current_reviews = self.parse_yandex_reviews_count(self.driver.page_source)
                print(f"📊 Current review count: {current_reviews}")
                if current_reviews > 99:
                    print("⚠️ 99 dan ortiq review topildi, to‘xtatish.")
                    return self.driver.page_source
                if current_reviews == 0:
                    review_zero_count += 1
                    print(f"❗ 0 ta review topildi. 0 qayta: {review_zero_count}/{max_zero_count}")
                    if review_zero_count >= max_zero_count:
                        print("🔄 0 review ko‘p takrorlandi. Sahifa yangilanmoqda...")
                        self.driver.refresh()
                        time.sleep(3)
                        review_zero_count = 0
                        continue
                else:
                    review_zero_count = 0

                if self.check_captcha():
                    print("🛑 CAPTCHA detected, stopping.")
                    return ""

                self.accept_cookie_popup()
                self.close_popup_if_exists()
                self.click_reviews_all_button()
                self.close_new_page_if_opened()

                if current_reviews == last_review_count and last_review_count > 0:
                    stagnant_count += 1
                    no_change_total += 1
                    print(f"⚠️ Review o‘zgarmadi. Ketma-ket: {stagnant_count}/5 | Umumiy: {no_change_total}/10")

                    if stagnant_count >= max_stagnant_count and len(scroll_positions) >= 2:
                        print("↩️ 5 ta ketma-ket bir xil review. 2 qadam orqaga.")
                        self.driver.execute_script(f"window.scrollTo(0, {scroll_positions[-2]});")
                        scroll_positions = scroll_positions[:-2]
                        stagnant_count = 5
                    if no_change_total >= zero_change_limit:
                        print("🚫 10 ta scrollda o‘zgarish yo‘q. To‘xtatildi.")
                        return self.driver.page_source
                else:
                    stagnant_count = 0
                    last_review_count = current_reviews
                    no_change_total = 0  # reset umumiy o‘zgarmaslik

                # Scroll qilish
                scroll_y = self.driver.execute_script("return window.scrollY")
                scroll_positions.append(scroll_y)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                scroll_count += 1
                print(f"⬇ Scrolling... {scroll_count}/{max_scrolls}")
                time.sleep(1)

            return self.driver.page_source
        except Exception as e:
            print(f"❌ Scroll error: {e}")
            return ""

    def run(self) -> Optional[str]:
        # os.system("pkill -f chromedriver")  # Oldingi jarayonlarni tozalash
        random_proxy = random.choice(self.proxy_list)
        options = webdriver.ChromeOptions()
        options.add_argument("--window-size=600,900")
        options.add_argument("--window-position=720,0")
        options.add_argument("--start-maximized")
        options.add_argument(f'--proxy-server={random_proxy}')
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        user_data_dir = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={user_data_dir}")
        prefs = {
            "profile.managed_default_content_settings.images": 2
        }
        options.add_experimental_option("prefs", prefs)
        service = Service('/usr/local/bin/chromedriver', port=random.randint(49152, 49152))

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get(self.url)
            self.driver.execute_script("document.body.style.zoom='25%'")
            time.sleep(3)
            print(f"🔗  Proxy: {random_proxy}----Port: {service.service_url}")

            try:
                ActionChains(self.driver).move_by_offset(200, 200).click().perform()
            except Exception as e:
                print(f"❌ Error during first click: {e}")

            if not self.check_captcha():
                html_content = self.scroll_and_collect()
                return html_content
            return ""
        except Exception as e:
            print(f"❌ Driver error: {e}")
            return ""
        finally:
            self.driver.quit()


def extract_full_reviews(html_content, product_id: int) -> dict:
    """
    Yandex Market sharhlar sahifasidan sharhlarni ajratib oladi va DB ga saqlaydi.
    """
    if not html_content:
        logging.error("❌ Sharhlar uchun HTML kontent mavjud emas")
        return {}

    soup = BeautifulSoup(html_content, 'html.parser')
    stats = {
        "reviews_total": 0,
        "reviews_created": 0,
        "review_photos_created": 0,
        "review_stats": []
    }

    review_items = soup.find_all('div', attrs={'data-auto': 'review-item'})
    logging.info(f"🔍 To'liq sharhlar sahifasida {len(review_items)} ta sharh topildi.")

    for i, review in enumerate(review_items, 1):
        time.sleep(0.1)  # Har bir sharhni qayta ishlashdan oldin qisqa kutish
        try:
            with transaction.atomic():
                # Username
                username_tag = review.find('span', attrs={'data-auto': 'nickname'})
                username = username_tag.text.strip() if username_tag else None
                if not username:
                    logging.warning(f"⚠️ Sharh #{i}: Foydalanuvchi nomi topilmadi, o'tkazib yuboriladi.")
                    continue

                # Avatar URL
                avatar_tag = review.find('img', attrs={'data-auto': 'avatar'})
                avatar_url = avatar_tag['src'] if avatar_tag else None

                # Stars
                rating_tag = review.find('meta', attrs={'itemprop': 'ratingValue'})
                stars = int(rating_tag['content']) if rating_tag and rating_tag['content'].isdigit() else None

                # Date
                date_tag = review.find('meta', attrs={'itemprop': 'datePublished'})
                date = date_tag['content'] if date_tag else None

                # Pros, Cons, Comment
                pros_tag = review.find('span', attrs={'data-auto': 'review-pro'})
                pros = pros_tag.text.strip() if pros_tag else None

                cons_tag = review.find('span', attrs={'data-auto': 'review-contra'})
                cons = cons_tag.text.strip() if cons_tag else None

                comment_tag = review.find('span', attrs={'data-auto': 'review-comment'})
                comment = comment_tag.text.strip() if comment_tag else None

                # Sharhni saqlash yoki yangilash
                review_obj, created = Review.objects.get_or_create(
                    pros=pros,
                    cons=cons,
                    comment=comment,
                    stars=stars,
                    user_name=username,
                    defaults={
                        'date': date,
                        'avatar_url': avatar_url,
                        'updated_at': None,
                        'created_at': None,
                        'product_id': product_id
                    }
                )

                if not created:
                    # Mavjud sharhni yangilash
                    update_needed = False
                    if review_obj.date != date:
                        review_obj.date = date
                        update_needed = True
                    if review_obj.avatar_url != avatar_url:
                        review_obj.avatar_url = avatar_url
                        update_needed = True
                    if review_obj.stars != stars:
                        review_obj.stars = stars
                        update_needed = True
                    if review_obj.pros != pros:
                        review_obj.pros = pros
                        update_needed = True
                    if review_obj.cons != cons:
                        review_obj.cons = cons
                        update_needed = True
                    if review_obj.comment != comment:
                        review_obj.comment = comment
                        update_needed = True
                    if update_needed:
                        review_obj.save()
                        logging.info(f"✅ Sharh yangilandi: {username}")

                stats['reviews_total'] += 1
                if created:
                    stats['reviews_created'] += 1
                    logging.info(f"✅ Yangi sharh yaratildi: {username}")

                # Rasmlarni qayta ishlash
                image_container = review.find('div', attrs={'data-auto': 'media-viewer-thumbnails'})
                images_src = []
                images_srcset = []

                if image_container:
                    image_list = image_container.find('ul', class_='_1qW4Q')
                    if image_list:
                        images = image_list.find_all('div', attrs={'data-auto': 'item'})
                        for img in images:
                            img_tag = img.find('img')
                            if img_tag:
                                if 'src' in img_tag.attrs:
                                    images_src.append(img_tag['src'])
                                if 'srcset' in img_tag.attrs:
                                    images_srcset.append(img_tag['srcset'])

                existing_photos = ReviewPhoto.objects.filter(review=review_obj).values('image_url', 'image_src')
                existing_data = [(p['image_url'], p['image_src']) for p in existing_photos]
                new_data = [(images_src[i], images_srcset[i] if i < len(images_srcset) else None) for i in
                            range(len(images_src))]

                if set(existing_data) != set(new_data):
                    logging.info(
                        f"🖼️ Sharh uchun rasmlar o'zgardi {username}: {len(existing_data)} dan {len(new_data)} ga")
                    ReviewPhoto.objects.filter(review=review_obj).delete()
                    for idx, img_url in enumerate(images_src):
                        img_src = images_srcset[idx] if idx < len(images_srcset) else None
                        ReviewPhoto.objects.create(
                            review=review_obj,
                            image_url=img_url,
                            image_src=img_src
                        )
                        stats['review_photos_created'] += 1
                        logging.info(f"🖼️ ReviewPhoto yaratildi {username}: image_url={img_url}, image_src={img_src}")
                else:
                    logging.debug(f"🖼️ Sharh uchun rasmlar o'zgarmadi {username}")

                photos_count = ReviewPhoto.objects.filter(review=review_obj).count()
                comment_flag = 1 if comment else 0
                stats['review_stats'].append([
                    username,
                    1 if created else 0,
                    photos_count,
                    len(images_src),
                    comment_flag
                ])

        except IntegrityError as e:
            logging.error(f"❌ Sharh saqlashda IntegrityError {username}: {e}")
            continue
        except Exception as e:
            logging.error(f"❌ Sharh qayta ishlashda xatolik {username}: {e}")
            continue

    # Jadvalni chiqarish
    if stats['review_stats']:
        logging.info("\n📋 To'liq sharhlar statistikasi:")
        print(tabulate(
            stats['review_stats'],
            headers=["Foydalanuvchi", "Yaratildi (1/0)", "Rasmlar soni", "Src rasmlar soni", "Izoh (1/0)"],
            tablefmt="grid"
        ))

    return stats


def parse_product_full_info(html_source, product_id: int) -> dict:
    """
    Mahsulotning to'liq ma'lumotlarini ajratib oladi va DB ga saqlaydi.
    """
    soup = BeautifulSoup(html_source, 'html.parser')
    stats = {
        "title_updated": 0,
        "price_updated": 0,
        "shop_updated": 0,
        "description_updated": 0,
        "specifications_updated": 0,
        "images_count": 0,
        "images_src_count": 0
    }

    try:
        with transaction.atomic():

            # Mahsulotni olish
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                logging.error(f"❌ Mahsulot ID {product_id} topilmadi.")
                return stats

            # Title
            title = None
            blocks = soup.find_all('div', class_='_261_I')
            for block in blocks:
                try:
                    title_elem = block.find('h1', {'data-auto': 'productCardTitle'})
                    title = title_elem.text.strip() if title_elem else None
                except:
                    continue

            if title and title != product.name:
                product.name = title
                stats['title_updated'] = 1
                logging.info(f"✅ Mahsulot nomi yangilandi: {title}")

            # Price
            price = None
            try:
                price_elem = soup.find('div', class_='Hbj6N')
                price_span = price_elem.find('span', {'data-auto': 'snippet-price-current'}).find('span')
                price_text = price_span.text.replace('\u2009', '').replace('\u2006', '')
                price = Decimal(price_text)
            except (AttributeError, ValueError, InvalidOperation):
                logging.warning(
                    f"⚠️ Mahsulot ID {product_id} uchun narx topilmadi yoki noto'g'ri: {price_text if 'price_text' in locals() else 'N/A'}")

            if price and price > 0 and product.price != price:
                product.price = price
                stats['price_updated'] = 1
                logging.info(f"✅ Mahsulot narxi yangilandi: {price}")

            # Shop name
            shop_name = None
            try:
                shop_elem = soup.find('div', {'data-auto': 'shop-info-title'}).find('span')
                shop_name = shop_elem.text.strip() if shop_elem else None
            except:
                pass

            if shop_name and shop_name != product.shop:
                product.shop = shop_name
                stats['shop_updated'] = 1
                logging.info(f"✅ Do'kon nomi yangilandi: {shop_name}")

            # Description
            description = None
            try:
                desc_div = soup.find('div', id='product-description')
                description = desc_div.text.strip() if desc_div else None
                logging.info(f"✅ Tavsif topildi: {description[:50] + '...' if description else 'Yo\'q'}")
            except Exception as e:
                logging.warning(f"⚠️ Tavsifni olishda xatolik: {e}")

            if description and description != product.description:
                product.description = description
                stats['description_updated'] = 1
                logging.info(f"✅ Mahsulot tavsifi yangilandi: {description[:50] + '...' if description else 'Yo\'q'}")

            # Specifications
            # Specifications (yangi usul bilan aria-label bo'yicha)
            specifications = {}
            try:
                specs_div = soup.find('div', attrs={'data-auto': 'specs-list-fullExtended'})
                spec_items = specs_div.find_all('div', class_='_3rW2x _1MOwX _2eMnU') if specs_div else []
                for item in spec_items:
                    try:
                        key = item.find('span', {'data-auto': 'product-spec'}).text.strip()
                        value = item.find('div',
                                          class_='ds-text ds-text_weight_reg ds-text_typography_text ds-text_text_loose ds-text_text_reg').find(
                            'span').text.strip()
                        specifications[key] = value
                    except AttributeError:
                        continue
                logging.info(f"✅ {len(specifications)} ta xususiyat topildi.")
            except Exception as e:
                logging.warning(f"⚠️ Xususiyatlarni olishda xatolik: {e}")

            if specifications and specifications != product.characteristic:
                product.characteristic = specifications
                stats['specifications_updated'] = 1
                logging.info(f"✅ Mahsulot xususiyatlari yangilandi: {len(specifications)} ta xususiyat.")

            # Images
            images = []
            images_src = []
            try:
                ul_block = soup.select_one('div.s8eZq > div > ul')
                if ul_block:
                    li_items = ul_block.find_all('li')
                    for li in li_items:
                        img = li.find('img')
                        if img:
                            src = img.get('src')
                            srcset = img.get('srcset')
                            if src:
                                images.append(src)
                            if srcset:
                                images_src.append(f'srcset="{srcset}"')
            except Exception as e:
                logging.error(f"❌ Rasmlar qayta ishlashda xatolik: {e}")

            stats['images_count'] = len(images)
            stats['images_src_count'] = len(images_src)

            # Mavjud rasmlarni o'chirish va yangilarini qo'shish
            ProductImage.objects.filter(product=product).delete()
            image_objs = [
                ProductImage(
                    product=product,
                    image_url=img_url,
                    image_src=images_src[idx] if idx < len(images_src) else None,
                    is_main=(idx == 0)
                )
                for idx, img_url in enumerate(images)
            ]
            if image_objs:
                ProductImage.objects.bulk_create(image_objs)
                logging.info(f"🖼️ {len(image_objs)} ta mahsulot rasmi qo'shildi.")

            # Mahsulotni saqlash
            product.save()
            logging.info(f"✅ Mahsulot ID {product_id} muvaffaqiyatli yangilandi.")

            # Jadvalni chiqarish
            logging.info("\n📋 Mahsulot haqida batafsil ma'lumot:\n")
            print(tabulate(
                [
                    [product.id, product.name, product.price, product.shop, stats['images_count'],
                     stats['images_src_count']]
                ],
                headers=["ID", "Nomi", "Narxi", "Do'kon", "Rasmlar soni", "Src rasmlar soni"],
                tablefmt="grid"
            ))

    except Exception as e:
        logging.error(f"❌ Mahsulot ID {product_id} qayta ishlashda xatolik: {e}")
        return stats

    return stats


def parse_reviews_main_page(html_content, product_id: int) -> dict:
    """
    Mahsulotning asosiy sahifasidan sharhlarni ajratib oladi va DB ga saqlaydi.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    stats = {
        "reviews_total": 0,
        "reviews_created": 0,
        "review_photos_created": 0,
        "review_stats": []
    }

    reviews = soup.find_all('div', class_='cia-vs', attrs={'data-zone-name': 'product-review'})
    logging.info(f"🔍 Asosiy sahifada {len(reviews)} ta sharh topildi.")

    for review in reviews:
        try:
            username = None
            date = None
            time.sleep(0.1)  # Har bir sharhni qayta ishlashdan oldin qisqa kutish
            with transaction.atomic():
                # Username va Date
                profile_info = review.find('div', class_='ds-trainLine _3gXUj')
                if profile_info:
                    spans = profile_info.find_all('span', class_='ds-text')
                    date = spans[0].text.strip() if len(spans) > 0 else None
                    username = spans[2].text.strip() if len(spans) > 2 else None
                if not username:
                    logging.warning(f"⚠️ Sharh: Foydalanuvchi nomi topilmadi, o'tkazib yuboriladi.")
                    continue

                # Avatar URL
                avatar_img = review.find('img', class_='dmuPF')
                avatar_url = avatar_img['src'] if avatar_img else None

                # Stars
                stars = len(review.find_all('span', class_='_2lch2'))

                # Pros, Cons, Comment
                pros, cons, comment = None, None, None
                text_block = review.find('div', class_='_10YbS')
                if text_block:
                    spans = text_block.find_all('span', class_='ds-text')
                    current_field = None
                    for span in spans:
                        if 'Достоинства:' in span.text:
                            current_field = 'pros'
                            continue
                        elif 'Недостатки:' in span.text:
                            current_field = 'cons'
                            continue
                        elif 'Комментарий:' in span.text:
                            current_field = 'comment'
                            continue
                        if current_field == 'pros':
                            pros = (pros or '') + ' ' + span.text.strip()
                        elif current_field == 'cons':
                            cons = (cons or '') + ' ' + span.text.strip()
                        elif current_field == 'comment':
                            comment = (comment or '') + ' ' + span.text.strip()

                # Sharhni saqlash yoki yangilash
                review_obj, created = Review.objects.get_or_create(
                    pros=pros.strip() if pros else None,
                    cons=cons.strip() if cons else None,
                    comment=comment.strip() if comment else None,
                    stars=stars,
                    user_name=username,
                    defaults={
                        'date': date,
                        'avatar_url': avatar_url,
                        'updated_at': None,
                        'created_at': None,
                        'product_id': product_id
                    }
                )

                if not created:
                    # Mavjud sharhni yangilash
                    update_needed = False
                    if review_obj.date != date:
                        review_obj.date = date
                        update_needed = True
                    if review_obj.avatar_url != avatar_url:
                        review_obj.avatar_url = avatar_url
                        update_needed = True
                    if review_obj.stars != stars:
                        review_obj.stars = stars
                        update_needed = True
                    if review_obj.pros != pros:
                        review_obj.pros = pros.strip() if pros else None
                        update_needed = True
                    if review_obj.cons != cons:
                        review_obj.cons = cons.strip() if cons else None
                        update_needed = True
                    if review_obj.comment != comment:
                        review_obj.comment = comment.strip() if comment else None
                        update_needed = True
                    if update_needed:
                        review_obj.save()
                        logging.info(f"✅ Sharh yangilandi: {username}")

                stats['reviews_total'] += 1
                if created:
                    stats['reviews_created'] += 1
                    logging.info(f"✅ Yangi sharh yaratildi: {username}")

                # Rasmlarni qayta ishlash
                images = review.find_all('img', class_='_1uJEc')
                images_src = [img['src'] for img in images] if images else []
                images_srcset = [img.get('srcset', None) for img in images] if images else []

                existing_photos = ReviewPhoto.objects.filter(review=review_obj).values('image_url', 'image_src')
                existing_data = [(p['image_url'], p['image_src']) for p in existing_photos]
                new_data = [(images_src[i], images_srcset[i]) for i in range(len(images_src))]

                if set(existing_data) != set(new_data):
                    logging.info(
                        f"🖼️ Sharh uchun rasmlar o'zgardi {username}: {len(existing_data)} dan {len(new_data)} ga")
                    ReviewPhoto.objects.filter(review=review_obj).delete()
                    for idx, img_url in enumerate(images_src):
                        img_src = images_srcset[idx] if idx < len(images_srcset) else None
                        ReviewPhoto.objects.create(
                            review=review_obj,
                            image_url=img_url,
                            image_src=img_src
                        )
                        stats['review_photos_created'] += 1
                        logging.info(f"🖼️ ReviewPhoto yaratildi {username}: image_url={img_url}, image_src={img_src}")
                else:
                    logging.debug(f"🖼️ Sharh uchun rasmlar o'zgarmadi {username}")

                photos_count = ReviewPhoto.objects.filter(review=review_obj).count()
                comment_flag = 1 if comment else 0
                stats['review_stats'].append([
                    username,
                    1 if created else 0,
                    photos_count,
                    len(images_src),
                    comment_flag
                ])

        except IntegrityError as e:
            logging.error(f"❌ Sharh saqlashda IntegrityError {username}: {e}")
            continue
        except Exception as e:
            logging.error(f"❌ Sharh qayta ishlashda xatolik {username}: {e}")
            continue

    # Jadvalni chiqarish
    if stats['review_stats']:
        logging.info("\n📋 Asosiy sahifa sharhlari statistikasi:")
        print(tabulate(
            stats['review_stats'],
            headers=["Foydalanuvchi", "Yaratildi (1/0)", "Rasmlar soni", "Src rasmlar soni", "Izoh (1/0)"],
            tablefmt="grid"
        ))

    return stats


############################


class Command(BaseCommand):
    help = 'Create or update products in the database from predefined catalogs'

    def handle(self, *args, **kwargs):
        products_count= len(list(Product.objects.filter(is_processing=False, parse_detail=False).values_list("id", flat=True)))
        logging.info(f"🔗 {products_count} ta mahsulot qayta ishlanish uchun topildi.")

        current_product = None
        try:
            for i in range(products_count):

                product_ids = list(Product.objects.filter(is_processing=False, parse_detail=False).values_list("id", flat=True))

                logging.info(f"📦 Qayta ishlanmagan mahsulotlar soni: {len(product_ids)}")

                if products_count == 0:
                    logging.info("🔚 Barcha mahsulotlar qayta ishlangan.")
                    break
                product_id = random.choice(product_ids)
                product = Product.objects.get(id=product_id)
                logging.info(f"🔗 Mahsulotni qayta ishlash: {product.name} (ID: {product.id})")
                with transaction.atomic():
                    product.is_processing = True
                    product.save(update_fields=['is_processing'])
                    logging.info(f"🔄 Mahsulot {product.name} qayta ishlashga tayyorlandi.------")

                scraper = YandexMarketSingleScraper(product.url, proxy_list)
                html_content, reviews_url = scraper.load_and_parse()

                logging.info(f"🔗 Sharhlar URL: {reviews_url}")

                if html_content:
                    logging.info("✅ HTML kontent muvaffaqiyatli yuklandi.")
                    product_stats = parse_product_full_info(html_content, product.id)
                    logging.info(f"📦 Mahsulot ma'lumotlari saqlandi: {product_stats}")

                    # Asosiy sahifadagi sharhlarni qayta ishlash
                    main_reviews_stats = parse_reviews_main_page(html_content, product.id)
                    logging.info(f"📋 Asosiy sahifa sharhlari saqlandi: {main_reviews_stats}")

                    # To‘liq sharhlar sahifasini qayta ishlash
                    full_reviews_stats = {}
                    if reviews_url:
                        reviews_html = YandexMarketReviewsScraper(reviews_url, proxy_list).run()
                        if reviews_html:
                            # Faqat yangi sharhlarni qayta ishlash uchun filtr
                            existing_reviews = Review.objects.filter(product_id=product.id).values('user_name', 'date')
                            existing_reviews_set = {(r['user_name'], r['date']) for r in existing_reviews}
                            full_reviews_stats = extract_full_reviews(reviews_html, product.id)
                            logging.info("\n📋 To'liq sharhlar statistikasi:")
                            print(tabulate(
                                [[
                                    full_reviews_stats['reviews_total'],
                                    full_reviews_stats['reviews_created'],
                                    full_reviews_stats['review_photos_created']
                                ]],
                                headers=["Jami sharhlar", "Yaratilgan sharhlar", "Yaratilgan rasmlar"],
                                tablefmt="fancy_grid"
                            ))
                            if full_reviews_stats.get('review_stats'):
                                print(tabulate(
                                    full_reviews_stats['review_stats'],
                                    headers=["Foydalanuvchi", "Yaratildi (1/0)", "Rasmlar soni", "Src rasmlar soni",
                                             "Izoh (1/0)"],
                                    tablefmt="fancy_grid"
                                ))

                    product.refresh_from_db()
                    logging.info("\n📦 Mahsulot saqlash natijasi:")
                    print(tabulate(
                        [[product.id, product.name, product.price]],
                        headers=["Mahsulot ID", "Mahsulot nomi", "Narxi"],
                        tablefmt="fancy_grid"
                    ))
                    product.is_processing = False
                    product.parse_detail = True
                    product.save()
                    logging.info(f"✅ Mahsulot {product.name} muvaffaqiyatli qayta ishlandi.")
                else:
                    logging.error("❌ HTML kontentni yuklash muvaffaqiyatsiz tugadi.")

        except KeyboardInterrupt:
            if current_product:
                current_product.is_processing = False
                current_product.save()
                logging.info(f"🛑 Jarayon qo'lda to'xtatildi. is_processing=False o'rnatildi: {current_product.name}")
            else:
                logging.info("🛑 Jarayon qo'lda to'xtatildi, hech qanday mahsulot qayta ishlanmadi.")
