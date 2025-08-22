from django.contrib import admin

from .models import (
    Category,
    Product, ProductImage,
    Review, ReviewPhoto
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ReviewInline(admin.StackedInline):
    model = Review
    extra = 1


from django.contrib.admin import SimpleListFilter


class SkuExistFilter(SimpleListFilter):
    title = 'SKU mavjudligi'
    parameter_name = 'sku_exists'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'SKU mavjud'),
            ('no', 'SKU yo‘q'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.exclude(sku__isnull=True).exclude(sku__exact='')
        elif value == 'no':
            return queryset.filter(sku__isnull=True) | queryset.filter(sku__exact='')
        return queryset


@admin.action(description="Tanlangan mahsulotlar uchun parse_detail ni False qilish")
def disable_parse_detail(modeladmin, request, queryset):
    queryset.update(parse_detail=False)

@admin.action(description="Tanlangan mahsulotlar uchun is_processing ni False qilish")
def disable_is_processing(modeladmin, request, queryset):
    queryset.update(is_processing=False)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'count', 'name', 'price', 'category', 'product_id', 'sku', 'rating_count', 'updated_at', 'parse_detail',
        'rating', 'created_at',
        'is_processing', 'is_related_parsed')
    list_filter = ('is_processing', 'is_related_parsed', SkuExistFilter, 'parse_detail')
    search_fields = ('name', 'sku', 'url', 'id', 'product_id', 'category__name')
    inlines = [ProductImageInline, ReviewInline]
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)  # Always order by created_at

    def count(self, obj):
        return self.model.objects.filter(id__lte=obj.id).count()

    count.short_description = 'Count'
    actions = [disable_parse_detail,disable_is_processing]


@admin.action(description="Barcha tanlangan kategoriyalarni parsed = False qilish")
def disable_parsed(modeladmin, request, queryset):
    queryset.update(parsed=False)


@admin.action(description="Barcha tanlangan kategoriyalarni parsed = true qilish")
def enabled_parsed(modeladmin, request, queryset):
    queryset.update(parsed=True)


@admin.action(description="Barcha tanlangan kategoriyalarni product_count 0 qilish")
def update_product_count(modeladmin, request, queryset):
    for category in queryset:
        category.product_count = 0
        category.save()


@admin.action(description="Barcha tanlangan kategoriyalarni is_processing False qilish")
def disable_is_processing(modeladmin, request, queryset):
    queryset.update(is_processing=False)


# parent category update to #Электроника
@admin.action(description="Barcha tanlangan kategoriyalarni parent = Электроника qilish")
def update_parent_to_electronics(modeladmin, request, queryset):
    electronics_category = Category.objects.get(name='Электроника')
    queryset.update(parent=electronics_category)


class ParentOrSubcategoryFilter(admin.SimpleListFilter):
    title = 'Tur'
    parameter_name = 'category_type'

    def lookups(self, request, model_admin):
        return [
            ('parent', 'Parent (asosiy)'),
            ('child', 'Subcategory (quyi)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'parent':
            return queryset.filter(parent__isnull=True)
        if self.value() == 'child':
            return queryset.filter(parent__isnull=False)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'url', 'parsed', 'is_processing', 'product_count', 'parent__name', 'category_last_update')
    search_fields = ('name', 'url', 'parent__name')
    list_filter = ('parsed', ParentOrSubcategoryFilter)
    list_editable = ('parsed',)
    actions = [disable_parsed, update_product_count, disable_is_processing, enabled_parsed,
               update_parent_to_electronics]


class ReviewPhotoInline(admin.TabularInline):
    model = ReviewPhoto
    extra = 0

admin.site.register(ReviewPhoto)
from django.db.models import Count


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('count','user_name', 'stars', 'date', 'product', 'created_at', 'updated_at', 'photos_count')
    search_fields = ('user_name', 'product__name', 'comment','pros', 'cons',)
    raw_id_fields = ['product']
    inlines = [ReviewPhotoInline]  # agar inline kerak bo'lsa

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('product').annotate(photos_count=Count('photos'))
        return qs

    def photos_count(self, obj):
        return obj.photos_count
    def count(self, obj):
        return self.model.objects.filter(id__lte=obj.id).count()

    count.short_description = 'Count'
    photos_count.admin_order_field = 'photos_count'
    photos_count.short_description = 'Rasmlar soni'
