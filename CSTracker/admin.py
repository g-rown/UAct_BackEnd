from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . import models

# Register your models here.
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Roles', {'fields': ('is_student', 'is_admin')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Roles', {'fields': ('is_student', 'is_admin')}),
    )

admin.site.register(models.User, CustomUserAdmin)
admin.site.register(models.StudentProfile)
admin.site.register(models.Program)
admin.site.register(models.ProgramSubmissions)
admin.site.register(models.ServiceLog)
admin.site.register(models.ProgramApplication)