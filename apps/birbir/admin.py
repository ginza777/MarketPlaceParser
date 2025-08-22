from django.contrib import admin

# Register your models here.


from .models import Category, Seller, Photo, Product,SiteToken

@admin.action(description="Barcha tanlangan kategoriyalarni parsed = False qilish")
def disable_parsed(modeladmin, request, queryset):
    queryset.update(parsed=False)


@admin.action(description="Barcha tanlangan kategoriyalarni product_count 0 qilish")
def update_product_count(modeladmin, request, queryset):
    for category in queryset:
        category.product_count = 0
        category.save()

@admin.action(description="Barcha tanlangan kategoriyalarni is_processing False qilish")
def disable_is_processing(modeladmin, request, queryset):
    queryset.update(is_processing=False)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'url', 'parent', 'product_count', 'is_processing', 'parsed', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('created_at',)
    actions= [disable_parsed, update_product_count, disable_is_processing]


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = (
    'uuid', 'name', 'registered_date', 'last_access_date', 'business', 'offer_total_count', 'offer_active_count')
    search_fields = ('name', 'uuid')
    list_filter = ('business', 'registered_date', 'last_access_date')


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('product', 'photo_id', 'uuid', 'file_size', 'width', 'height')
    search_fields = ('product__title', 'uuid')
    list_filter = ('product',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'slug', 'is_parsed', 'price', 'category', 'phone', 'created_at')
    search_fields = ('title', 'slug', 'product_id')
    list_filter = ('is_parsed', 'status', 'category')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(SiteToken)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('token',)
    search_fields = ('token',)
