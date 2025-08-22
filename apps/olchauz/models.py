from django.db import models

# Create your models here.
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    url_category = models.URLField(max_length=500, unique=True,db_index=True)  # URL of the category page
    product_count = models.PositiveIntegerField(default=0)  # To track the number of products in this category
    last_parsed = models.DateTimeField(null=True, blank=True)  # To track the last time this category was parsed


    def __str__(self):
        return self.name


class Product(models.Model):
    title = models.CharField(max_length=2550)
    brand = models.CharField(max_length=1000, null=True, blank=True)  # Brand of the product
    sku = models.CharField(max_length=50, unique=True,null=True, blank=True)  # Stock Keeping Unit, unique identifier for the product
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    description = models.TextField(blank=True)
    product_url= models.URLField(max_length=5000, unique=True,db_index=True)  # URL of the product page
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_parsed = models.BooleanField(default=False)  # To track if the product has been parsed

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=5000)
    is_main = models.BooleanField(default=False)  # To mark the main image for the product
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.title} - {'Main' if self.is_main else 'Additional'} Image"


class ProductPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    store = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='UZS')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.store}: {self.price} {self.currency}"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key}: {self.value}"


class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    stars = models.PositiveIntegerField(choices=[(i, f"{i} stars") for i in range(1, 6)])
    count = models.PositiveIntegerField(default=0)  # Number of users giving this star rating
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'stars')

    def __str__(self):
        return f"{self.product.title}: {self.stars} stars ({self.count} votes)"
