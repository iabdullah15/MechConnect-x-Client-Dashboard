from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (("MASTER","MASTER"), ("CLIENT","CLIENT"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="CLIENT")
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL)

    def is_master(self):
        # Allow actual masters and superusers (optionally staff) to act as master
        return self.role == "MASTER" or self.is_superuser  # or add: or self.is_staff

