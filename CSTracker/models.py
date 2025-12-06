from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import time


# ---------------------------
#         USER MODEL
# ---------------------------
class User(AbstractUser):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    is_student = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_admin and self.is_student:
            raise ValueError("A user cannot be both admin and student.")
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return self.full_name


# ---------------------------
#     STUDENT PROFILE
# ---------------------------
class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='student_profile'
    )

    course = models.CharField(max_length=10)
    year_level = models.CharField(max_length=10)
    section = models.CharField(max_length=10, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)

    total_required_hours = models.IntegerField(default=80)
    hours_completed = models.IntegerField(default=0)

    @property
    def CYS(self):
        return f"{self.course}{self.year_level}{self.section}"

    @property
    def hours_remaining(self):
        return self.total_required_hours - self.hours_completed
    
    def __str__(self):
        return f"{ self.user.full_name} - {self.CYS}"


# ---------------------------
#          PROGRAM
# ---------------------------
class Program(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    facilitator = models.CharField(max_length=255, blank=True)

    date = models.DateField(default=timezone.now)
    time_start = models.TimeField(default=time(0, 0))
    time_end = models.TimeField(default=time(0, 0))

    hours = models.IntegerField() 

    slots = models.IntegerField()
    slots_taken = models.IntegerField(default=0)

    @property
    def slots_remaining(self):
        return self.slots - self.slots_taken
    
    
    def __str__(self):
        return f"{self.name} - {self.slots_remaining} slots left"

# ---------------------------
#     PROGRAM APPLICATION
# ---------------------------
# This is the detailed application form.
class ProgramApplication(models.Model):
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE,
        related_name="applications"
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE,
        related_name="applications"
    )

    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=15)

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.full_name} - {self.program.name}"

# ---------------------------
#    PROGRAM SUBMISSION
# ---------------------------
class ProgramSubmissions(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    application = models.ForeignKey(
        ProgramApplication, on_delete=models.CASCADE, related_name="submissions"
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=PENDING)
    decision_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application.student.user.full_name} - {self.application.program.name}"


# ---------------------------
#       SERVICE LOG
# ---------------------------
class ServiceLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
    ]

    application = models.ForeignKey(
        ProgramApplication, on_delete=models.CASCADE, related_name="service_logs"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.application.student.user.username} - {self.application.program.hours} hours - {self.status}"




