from django.db import models


from django.db import models

class Category(models.Model):
    TYPE_CHOICES = [
        ('dprice', 'Discount Price'),
        ('aprice', 'Actual Price'),
        ('rating', 'Rating'),
        ('', 'Default'),
    ]

    name = models.CharField(max_length=255)
    url = models.URLField(unique=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    category_id = models.CharField(max_length=100, unique=True, db_index=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children',default=101)
    category_last_update = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    product_count = models.PositiveIntegerField(default=0)
    last_parsed = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    parsed = models.BooleanField(default=False)
    is_processing = models.BooleanField(default=False)

    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='',
        blank=True
    )

    vendor_id = models.CharField(max_length=100, null=True, blank=True)

    @property
    def all_urls(self):
        base_urls = [
            f"{self.url}?how=dprice",
            f"{self.url}?how=aprice",
            f"{self.url}?how=rating",
            self.url
        ]

        if self.vendor_id:
            return [
                f"{self.url}&how=dprice&vendorId={self.vendor_id}",
                f"{self.url}&how=aprice&vendorId={self.vendor_id}",
                f"{self.url}&how=rating&vendorId={self.vendor_id}",
                f"{self.url}&vendorId={self.vendor_id}",
            ]

        return base_urls
class Product(models.Model):
    name = models.TextField(db_index=True)  # Product name, indexed for faster search
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='RUB')  # Currency of the product price
    rating = models.FloatField(null=True, blank=True, default=0.0)  # Yulduzcha
    rating_count = models.PositiveIntegerField(null=True, blank=True, default=0)  # Review count
    delivery_date = models.CharField(max_length=2550, null=True, blank=True)  # Delivery date as a string
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True,db_index=True, related_name='products')  # Foreign key to Category model
    brand = models.CharField(max_length=2550, null=True, blank=True)  # Delivery date as a string
    shop = models.CharField(max_length=2550, null=True, blank=True)  # Delivery date as a string
    sku = models.CharField(max_length=1000, null=True, blank=True, db_index=True)  # SKU for the product
    product_id = models.CharField(max_length=1000, db_index=True, null=True, blank=True)  # Unique product identifier
    url = models.TextField( db_index=True, null=True, blank=True)  # Product URL
    is_parsed = models.BooleanField(default=False,db_index=True)
    parse_detail = models.BooleanField(default=False,db_index=True)  # To indicate if the product details have been parsed
    description = models.TextField(blank=True, null=True)  # To store product description
    characteristic = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=False,db_index=True)  # To indicate if the product is currently being processed
    is_related_parsed = models.BooleanField(default=False,db_index=True)  # To indicate if related products have been parsed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_id

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images',db_index=True)
    image_url = models.URLField()
    image_src = models.TextField(null=True, blank=True)  # To store the image source URL
    is_main = models.BooleanField(default=False)  # To mark the main image for the product
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewPhoto(models.Model):
    review = models.ForeignKey('Review', on_delete=models.CASCADE,db_index=True, related_name='photos')
    image_url = models.URLField(null=True, blank=True)
    image_src = models.TextField(null=True, blank=True)  # To store the image source URL


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews',db_index=True)
    date = models.CharField(max_length=255, null=True, blank=True,db_index=True)  # Date of the review as a string
    user_name = models.CharField(max_length=255, null=True, blank=True,db_index=True)  # User's name who wrote the review
    avatar_url = models.URLField(null=True, blank=True)
    stars = models.PositiveSmallIntegerField(null=True, blank=True)  # Number of stars given in the review
    pros = models.TextField(blank=True, null=True,db_index=True)  # Pros of the product as mentioned in the review
    cons = models.TextField(blank=True, null=True,db_index=True)  # Cons of the product as mentioned in the review
    comment = models.TextField(blank=True, null=True,db_index=True)  # Full text of the review
    updated_at = models.DateTimeField(auto_now=True,blank=True, null=True)  # Last update time of the review
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)  # Creation time of the review

    def __str__(self):
        return f"{self.user_name} - {self.stars}⭐"


