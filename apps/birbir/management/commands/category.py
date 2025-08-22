import json
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from ...models import Category





class Command(BaseCommand):
    help = 'Kategoriyalar va subkategoriyalarni to‘liq URL bilan JSON formatda chiqaradi va mavjud bo‘lsa yangilaydi'

    def handle(self, *args, **kwargs):
        # base_url = "https://birbir.uz"
        # categories_data = [
        #     {"name": "Barcha kategoriyalarni ko'rish", "url": f"{base_url}/uz/toshkent/cat", "subcategories": []},
        #     {"name": "Elektronika", "url": f"{base_url}/uz/toshkent/elektronika", "subcategories": [
        #         {"name": "Barchasi", "url": f"{base_url}/uz/toshkent/cat/elektronika"},
        #         {"name": "Telefonlar va aloqa", "url": f"{base_url}/uz/toshkent/cat/telefonlar"},
        #         {"name": "Audio va video", "url": f"{base_url}/uz/toshkent/cat/audio-va-video"},
        #         {"name": "Kompyuter texnikasi", "url": f"{base_url}/uz/toshkent/cat/kompyuter-texnikasi"},
        #         {"name": "Noutbuklar", "url": f"{base_url}/uz/toshkent/cat/noutbuklar"},
        #         {"name": "O'yinlar, pristavkalar va dasturlar", "url": f"{base_url}/uz/toshkent/cat/oyinlar-pristavkalar-va-dasturlar"},
        #         {"name": "Ish stoli kompyuter", "url": f"{base_url}/uz/toshkent/cat/ish-stoli-kompyuterlari"},
        #         {"name": "Fotosurat uskunalari", "url": f"{base_url}/uz/toshkent/cat/fotosurat-uskunalari"},
        #         {"name": "Planshetlar va elektron kitoblar", "url": f"{base_url}/uz/toshkent/cat/planshetlar-va-elektron-kitoblar"},
        #         {"name": "Ofis jihozlari va sarf materiallari", "url": f"{base_url}/uz/toshkent/cat/ofis-jihozlari-va-sarf-materiallari"},
        #         {"name": "Raqamli tarkib va dasturiy ta'minot", "url": f"{base_url}/uz/toshkent/cat/raqamli-tarkib-va-dasturiy-taminot"},
        #     ]},
        #     {"name": "Maishiy texnika", "url": f"{base_url}/uz/toshkent/maishiy-texnika", "subcategories": []},
        #     {"name": "Mebel va interyer", "url": f"{base_url}/uz/toshkent/mebel-va-interyer", "subcategories": []},
        #     {"name": "Go'zallik va salomatlik", "url": f"{base_url}/uz/toshkent/gozallik-va-salomatlik", "subcategories": []},
        #     {"name": "Kiyim va poyabzallar", "url": f"{base_url}/uz/toshkent/kiyim-va-poyabzallar", "subcategories": []},
        #     {"name": "Zargarlik buyumlari / Aksessuarlar", "url": f"{base_url}/uz/toshkent/zargarlik-buyumlari-aksessuarlar", "subcategories": []},
        #     {"name": "Bolalar uchun", "url": f"{base_url}/uz/toshkent/bolalar-uchun", "subcategories": []},
        #     {"name": "Qurilish va ta'mirlash", "url": f"{base_url}/uz/toshkent/qurilish-va-tamirlash", "subcategories": []},
        #     {"name": "O'simliklar", "url": f"{base_url}/uz/toshkent/osimliklar", "subcategories": []},
        #     {"name": "Transport", "url": f"{base_url}/uz/toshkent/transport", "subcategories": []},
        #     {"name": "Xizmatlar", "url": f"{base_url}/uz/toshkent/xizmatlar", "subcategories": []},
        #     {"name": "Ko'chmas mulk", "url": f"{base_url}/uz/toshkent/kochmas-mulk", "subcategories": []},
        #     {"name": "Biznes", "url": f"{base_url}/uz/toshkent/biznes", "subcategories": []},
        #     {"name": "Ish", "url": f"{base_url}/uz/toshkent/ish", "subcategories": []},
        #     {"name": "Hayvonlar", "url": f"{base_url}/uz/toshkent/hayvonlar", "subcategories": []},
        #     {"name": "Mahsulotlar", "url": f"{base_url}/uz/toshkent/mahsulotlar", "subcategories": []},
        #     {"name": "Xobbi va sport", "url": f"{base_url}/uz/toshkent/xobbi-va-sport", "subcategories": []},
        #     {"name": "Kanselyariya tovarlari", "url": f"{base_url}/uz/toshkent/kanselyariya-tovarlari", "subcategories": []},
        # ]
        #
        # # Bazaga yozish yoki yangilash
        # for cat in categories_data:
        #     category, created = Category.objects.get_or_create(
        #         name=cat["name"],
        #         defaults={"slug": slugify(cat["name"]), "url": cat["url"]}
        #     )
        #     if not created:
        #         # Agar mavjud bo'lsa, yangilash
        #         category.slug = slugify(cat["name"])
        #         category.url = cat["url"]
        #         category.save()
        #
        #     for subcat in cat.get("subcategories", []):
        #         subcategory, sub_created = Category.objects.get_or_create(
        #             name=subcat["name"],
        #             defaults={"slug": slugify(subcat["name"]), "url": subcat["url"], "parent": category}
        #         )
        #         if not sub_created:
        #             # Agar mavjud bo'lsa, yangilash
        #             subcategory.slug = slugify(subcat["name"])
        #             subcategory.url = subcat["url"]
        #             subcategory.parent = category
        #             subcategory.save()
        #
        # # JSON chiqarish
        # categories = Category.objects.all()
        # data = [
        #     {
        #         "id": cat.id,
        #         "name": cat.name,
        #         "slug": cat.slug,
        #         "url": cat.url,
        #         "subcategories": [
        #             {"id": sub.id, "name": sub.name, "slug": sub.slug, "url": sub.url}
        #             for sub in Category.objects.filter(parent=cat)
        #         ]
        #     }
        #     for cat in categories if not cat.parent
        # ]
        #
        # self.stdout.write(self.style.SUCCESS('Kategoriyalar JSON formatda categories.json faylga yozildi va yangilandi'))

        CAT = [
            1000473,
            1000488,
            1000489,
            1000492,
            1000496,
            1000503,
            1000516,
            1000498,
            1000512,
            1000514,
            1000501,
            1000509,
            1000505,
            1000491,
            1000507,
            1000510,
            1000508
        ]


        for category in CAT:
            category_instance, created = Category.objects.get_or_create(
                category_id=category,
                defaults={
                    'name': f'Category {category}',
                    'slug': slugify(f'Category {category}'),
                    'url': f'/uz/toshkent/cat/{slugify(f"Category {category}")}'
                }
            )
            if not created:
                # Agar mavjud bo'lsa, yangilash
                category_instance.name = f'Category {category}'
                category_instance.slug = slugify(f'Category {category}')
                category_instance.url = f'/uz/toshkent/cat/{slugify(f"Category {category}")}'
                category_instance.save()