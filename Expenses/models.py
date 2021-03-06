from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Expense(models.Model):
    amount = models.DecimalField(decimal_places=2, max_digits=20)
    description = models.TextField()
    category = models.CharField(max_length=255)
    date = models.DateField(auto_now=True)
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)

    def __str__(self):
        return self.category

    class Meta:
        ordering = ['-date']

class Category(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

