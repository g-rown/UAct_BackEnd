from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import time


# ---------------------------
#         USER MODEL
# ---------------------------
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_admin and self.is_student:
            raise ValueError("A user cannot be both admin and student.")
        super().save(*args, **kwargs)


# ---------------------------
#     STUDENT PROFILE
# ---------------------------
class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='student_profile'
    )

    course = models.CharField(max_length=100)
    year_level = models.CharField(max_length=10)
    section = models.CharField(max_length=10, blank=True)

    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=15, blank=True)

    total_required_hours = models.IntegerField(default=80)
    hours_completed = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username

    @property
    def hours_remaining(self):
        return self.total_required_hours - self.hours_completed


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

    def __str__(self):
        return self.name

    @property
    def slots_remaining(self):
        return self.slots - self.slots_taken


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

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="submissions"
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="submissions"
    )

    first_name = models.CharField(max_length=100, default="Unknown")
    last_name = models.CharField(max_length=100 , default="Unknown")
    email = models.EmailField(default="unknown@example.com")
    phone_number = models.CharField(max_length=15, default="N/A")

    course = models.CharField(max_length=100, default="Unknown")
    year_level = models.CharField(max_length=10, default="N/A")

    emergency_contact_name = models.CharField(max_length=100, default="Unknown")
    emergency_contact_phone = models.CharField(max_length=15, default="N/A")

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.username} - {self.program.name}"


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

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="service_logs"
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="service_logs"
    )

    course = models.CharField(max_length=100, default="Unknown")
    year_level = models.CharField(max_length=10, default="N/A")
    section = models.CharField(max_length=10, default="N/A")

    hours = models.IntegerField()
    date = models.DateField(auto_now_add=True)

    # NEW FIELDS
    program_date = models.DateField(default=timezone.now)
    time_start = models.TimeField(default=time(0, 0))
    time_end = models.TimeField(default=time(0, 0))

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.user.username} - {self.hours} hrs"



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

    status = models.CharField(
        max_length=50,
        choices=ProgramSubmissions.STATUS_CHOICES,
        default=ProgramSubmissions.PENDING
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    # Application-specific info (not duplicated inside StudentProfile)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)

    course = models.CharField(max_length=100)
    year_level = models.CharField(max_length=10)

    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.student.user.username} - {self.program.name}"
