from django.contrib import admin
from .models import Product, Category, ProductImage, ProductPrice, ProductSpecification


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ['image_url', 'is_main']
    readonly_fields = ['image_url']


class ProductPriceInline(admin.TabularInline):
    model = ProductPrice
    extra = 0
    fields = ['store', 'price', 'currency', 'address']
    readonly_fields = ['store', 'price', 'currency', 'address']


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0
    fields = ['key', 'value']
    readonly_fields = ['key', 'value']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title','is_parsed', 'product_url', 'category','updated_at','created_at']
    search_fields = ['title', 'product_url']
    list_filter = ['is_parsed']
    inlines = [ProductImageInline, ProductPriceInline, ProductSpecificationInline]
    readonly_fields = ['product_url']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'url_category', 'parent_category','last_parsed']
    search_fields = ['name', 'url_category']
    list_filter = ['last_parsed']