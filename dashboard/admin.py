from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Organization, User

admin.site.register(Organization)
admin.site.register(User)
