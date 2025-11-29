from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_admin and self.is_student:
            raise ValueError("A user cannot be both admin and student.")
        super().save(*args, **kwargs)