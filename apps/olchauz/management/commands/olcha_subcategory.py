import time
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from ...models import Category  # model joylashgan app nomini to‘g‘ri qo‘y

class Command(BaseCommand):
    help = "Main catalog, subcatalog va brendlarni Category modeliga yozadi"

    def handle(self, *args, **kwargs):
        driver = webdriver.Chrome()
        driver.get("https://olcha.uz/")

        menu_btn = driver.find_element(By.CLASS_NAME, "bottom-header__menu-btn")
        menu_btn.click()
        time.sleep(3)

        actions = ActionChains(driver)
        main_items = driver.find_elements(By.CLASS_NAME, "menu-catalog__item")

        for i, item in enumerate(main_items):
            try:
                a_tag = item.find_element(By.TAG_NAME, "a")
                main_name = a_tag.text.strip()
                main_href = a_tag.get_attribute("href")
                print(f"\n🟥 Main Catalog: {main_name}")
                print(f"🔗 {main_href}")

                main_cat, _ = Category.objects.get_or_create(name=main_name, url=main_href, parent=None)

                actions.move_to_element(item).perform()
                time.sleep(1)

                content = driver.find_element(By.CLASS_NAME, "menu-catalog__content")
                html = content.get_attribute("innerHTML")
                soup = BeautifulSoup(html, "html.parser")

                subcatalogs = soup.select("div.menu-content__item")

                for sub in subcatalogs:
                    sub_link = sub.find("a", class_="menu-content__item-link")
                    if sub_link:
                        sub_name = sub_link.text.strip()
                        sub_href = sub_link["href"]
                        print(f"   🟦 SubCatalog: {sub_name}")
                        print(f"   🔗 {sub_href}")

                        sub_cat, _ = Category.objects.get_or_create(
                            name=sub_name,
                            url=sub_href,
                            parent=main_cat
                        )

                        sub_items = sub.select("div.menu-content__sub-item > a")
                        for brand in sub_items:
                            brand_name = brand.text.strip()
                            brand_href = brand["href"]
                            print(f"      🟨 Brand: {brand_name}")
                            print(f"      🔗 {brand_href}")

                            Category.objects.get_or_create(
                                name=brand_name,
                                url=brand_href,
                                parent=sub_cat
                            )

            except Exception as e:
                print(f"⚠️ Xatolik: {e}")

        driver.quit()