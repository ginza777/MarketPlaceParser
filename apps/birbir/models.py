import json
import time
import urllib.parse

from django.db import models
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def get_access_token_from_birbir():
    print("[+] ChromeOptions sozlanmoqda...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')

    print("[+] Brauzer ishga tushirilmoqda...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print("[+] Saytga kirilmoqda: https://birbir.uz/")
        driver.get('https://birbir.uz/')
        time.sleep(5)  # sahifa to‘liq yuklanishi uchun kutamiz

        print("[+] Cookie'lar olinmoqda...")
        cookies = driver.get_cookies()
        print(f"[+] {len(cookies)} ta cookie topildi.")

        for cookie in cookies:
            if cookie['name'] == 'session':
                print("[+] 'session' nomli cookie topildi.")
                session_value = cookie['value']
                print("[*] Session cookie qiymati:", session_value)

                decoded = urllib.parse.unquote(session_value)
                if decoded.startswith('j:'):
                    decoded = decoded[2:]
                try:
                    data = json.loads(decoded)
                    access_token = data.get("accessToken")
                    if access_token:
                        print("[+] accessToken topildi!")
                        return str("Bearer " + access_token)
                    else:
                        print("[!] accessToken mavjud emas.")
                        return None
                except Exception as e:
                    print("[!] JSON parse xatolik:", e)
                    return None
        print("[!] 'session' cookie topilmadi.")
        return None

    finally:
        driver.quit()
        print("[+] Brauzer yopildi.")


class SiteToken(models.Model):
    token = models.TextField(unique=True, null=True, blank=True)

    def refreshtoken(self):
        new_token = get_access_token_from_birbir()
        if new_token:  # faqat yangi token mavjud bo‘lsa yangilansin
            self.token = new_token
            self.save()
            return True
        return False

    def __str__(self):
        return self.token


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    url = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)
    category_id = models.BigIntegerField(unique=True, null=True, blank=True)
    is_processing = models.BooleanField(default=False)
    product_count = models.PositiveIntegerField(default=0)  # To track the number of products in this category
    updated_at = models.DateTimeField(auto_now=True)
    parsed = models.BooleanField(default=False)  # Indicates if the category has been parsed

    def __str__(self):
        return self.name


class Seller(models.Model):
    uuid = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    registered_date = models.DateField(null=True, blank=True)
    last_access_date = models.DateField(null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    business = models.BooleanField(default=False)
    offer_total_count = models.IntegerField(default=0)
    offer_active_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class Photo(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='photos')
    photo_id = models.BigIntegerField(unique=True)
    uuid = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    width = models.IntegerField()
    height = models.IntegerField()
    crop_url_template = models.URLField(max_length=500)

    def __str__(self):
        return f"Photo {self.photo_id} for {self.product.title}"


class Product(models.Model):
    product_id = models.BigIntegerField(unique=True, db_index=True)  # JSON'dagi "id"
    slug = models.SlugField(max_length=200)
    title = models.CharField(max_length=2000)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='UZS')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    region = models.CharField(max_length=100, null=True, blank=True)  # JSON'dagi "region"
    full_address = models.CharField(max_length=1500, null=True, blank=True)
    published_at = models.BigIntegerField(null=True)  # Unix timestamp
    url = models.URLField(max_length=3500, null=True, blank=True)  # JSON'dagi "webUri"
    business = models.BooleanField(default=False)
    courier_delivery = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    parsed_at = models.DateTimeField(auto_now=True)
    is_parsed = models.BooleanField(default=False)
    type = models.CharField(max_length=450, null=True, blank=True)  # JSON'dagi "type"
    status = models.CharField(max_length=150, null=True, blank=True)  # JSON'dagi "status"
    developer = models.CharField(max_length=100, null=True, blank=True)  # JSON'dagi "developer"
    phone = models.CharField(max_length=20, null=True, blank=True)  # JSON'dagi "phone"
    telegram = models.CharField(max_length=100, null=True, blank=True)  # JSON'dagi "telegram"

    def __str__(self):
        return self.title
