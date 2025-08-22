from datetime import datetime
import json
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from apps.yandex_market.models import Category  # Modelingizni tekshiring

class Command(BaseCommand):
    help = "Yandex HTML dan kategoriyalarni import qiladi"

    def handle(self, *args, **options):

        file_path = "apps/yandex_market/management/commands/category.js"

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                raw_data = json.load(file)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Fayl topilmadi: {file_path}"))
            return
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"JSON xato: {e}"))
            return

        total, created_count = 0, 0

        for data in raw_data.values():
            tree = data.get("widgets", {}).get("@MarketNode/NavigationTree", {})
            for section in tree.values():
                for item in section.get("data", []):
                    name = item.get("name")
                    cat_id = str(item.get("id"))
                    slug = item.get("slug", "")
                    url = f"https://market.yandex.ru/catalog--{slug}/{cat_id}"

                    try:
                        category, created = Category.objects.get_or_create(
                            category_id=cat_id,
                            defaults={
                                "name": name,
                                "slug": slug,
                                "url": url,
                                "category_last_update": datetime.now(),
                            }
                        )
                        if created:
                            created_count += 1
                            self.stdout.write(self.style.SUCCESS(f"Yaratildi: {name}"))
                        else:
                            self.stdout.write(f"Mavjud: {name}")
                    except IntegrityError:
                        category = Category.objects.filter(category_id=cat_id).first()
                        if category:
                            category.name = name
                            category.slug = slug
                            category.url = url
                            category.category_last_update = datetime.now()
                            category.save()
                            self.stdout.write(self.style.WARNING(f"🔁 Yangilandi: {name}"))


                    for sub in item.get("navnodes", []):
                        sub_id = str(sub.get("id"))
                        sub_name = sub.get("name")
                        sub_slug = sub.get("slug", "")
                        sub_url = f"https://market.yandex.ru/catalog--{sub_slug}/{sub_id}"

                        try:
                            subcategory, sub_created = Category.objects.get_or_create(
                                category_id=sub_id,
                                defaults={
                                    "name": sub_name,
                                    "slug": sub_slug,
                                    "url": sub_url,
                                    "parent": category,
                                    "category_last_update": datetime.now(),
                                }
                            )
                        except IntegrityError:
                            subcategory = Category.objects.filter(category_id=sub_id).first()
                            if subcategory:
                                subcategory.name = sub_name
                                subcategory.slug = sub_slug
                                subcategory.url = sub_url
                                subcategory.parent = category
                                subcategory.category_last_update = datetime.now()
                                subcategory.save()
                                self.stdout.write(self.style.WARNING(f"🔁 Sub yangilandi: {sub_name}"))

                    total += 1

        self.stdout.write(self.style.SUCCESS(f"\n✅ Jami kategoriyalar: {total}, Yaratilgan: {created_count}"))