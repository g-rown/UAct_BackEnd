from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import (
    User, StudentProfile, ServiceLog,
    ProgramSubmissions, ProgramApplication
)

# ----------------------------------------
# Auto-create StudentProfile when a User is created
# ----------------------------------------
@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    if created and instance.is_student:
        StudentProfile.objects.create(user=instance)


# ----------------------------------------
# Auto-increase hours_completed when ServiceLog is approved
# ----------------------------------------
@receiver(post_save, sender=ServiceLog)
def update_hours_completed(sender, instance, created, **kwargs):
    if created and instance.approved:
        student_profile = instance.student
        student_profile.hours_completed += instance.hours
        student_profile.save()


# ----------------------------------------
# Prevent duplicate ProgramSubmissions
# ----------------------------------------
@receiver(pre_save, sender=ProgramSubmissions)
def prevent_duplicate_submission(sender, instance, **kwargs):
    qs = ProgramSubmissions.objects.filter(
        student=instance.student,
        program=instance.program
    )
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise ValueError("This student has already submitted for this program.")


# ----------------------------------------
# Auto-create ProgramSubmission from ProgramApplication
# ----------------------------------------
@receiver(post_save, sender=ProgramApplication)
def create_submission_from_application(sender, instance, created, **kwargs):
    if created:
        # Create ProgramSubmission and copy all fields from the application
        ProgramSubmissions.objects.create(
            student=instance.student,
            program=instance.program,
            first_name=instance.first_name,
            last_name=instance.last_name,
            email=instance.email,
            phone_number=instance.phone_number,
            course=instance.course,
            year_level=instance.year_level,
            emergency_contact_name=instance.emergency_contact_name,
            emergency_contact_phone=instance.emergency_contact_phone,
            status=instance.status,
        )


# ----------------------------------------
# Sync ProgramSubmission status → ProgramApplication
# ----------------------------------------
@receiver(post_save, sender=ProgramSubmissions)
def sync_submission_to_application(sender, instance, **kwargs):
    try:
        # Find the related application
        app = ProgramApplication.objects.get(
            student=instance.student,
            program=instance.program
        )
        # Update application status if different
        if app.status != instance.status:
            app.status = instance.status
            app.save(update_fields=['status'])
    except ProgramApplication.DoesNotExist:
        # It's possible there is no application (ignore)
        pass
