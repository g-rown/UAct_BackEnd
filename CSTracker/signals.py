from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
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
# Auto-increase hours_completed ONLY when ServiceLog is approved by admin
# ----------------------------------------
@receiver(post_save, sender=ServiceLog)
def update_hours_completed(sender, instance, created, **kwargs):
    # Only count hours when admin approves the service log
    if instance.approved:
        student_profile = instance.student
        # Add the number of hours from this record
        student_profile.hours_completed += instance.hours
        student_profile.save()


# ----------------------------------------
# Prevent duplicate ProgramSubmissions for same student + program
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
# Auto-create ProgramSubmission when ProgramApplication is created
# ----------------------------------------
@receiver(post_save, sender=ProgramApplication)
def create_submission_from_application(sender, instance, created, **kwargs):
    if created:
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
# Sync ProgramSubmission.status → ProgramApplication.status
# ----------------------------------------
@receiver(post_save, sender=ProgramSubmissions)
def sync_submission_to_application(sender, instance, **kwargs):
    try:
        app = ProgramApplication.objects.get(
            student=instance.student,
            program=instance.program
        )
        if app.status != instance.status:
            app.status = instance.status
            app.save(update_fields=['status'])
    except ProgramApplication.DoesNotExist:
        pass


# ----------------------------------------
# Auto-create ServiceLog when submission is approved
# With automatic program schedule + status
# ----------------------------------------
@receiver(post_save, sender=ProgramSubmissions)
def create_service_log_on_approval(sender, instance, created, **kwargs):

    if instance.status == ProgramSubmissions.APPROVED:

        # Prevent duplicates
        if ServiceLog.objects.filter(
            student=instance.student,
            program=instance.program
        ).exists():
            return

        program = instance.program
        today = timezone.now().date()

        # Determine log status automatically
        if today < program.date:
            log_status = ServiceLog.STATUS_PENDING
        elif today == program.date:
            log_status = ServiceLog.STATUS_ONGOING
        else:
            log_status = ServiceLog.STATUS_COMPLETED

        # Create ServiceLog with program date & schedule
        ServiceLog.objects.create(
            student=instance.student,
            program=program,
            course=instance.course,
            year_level=instance.year_level,
            section=instance.student.section or "N/A",
            hours=program.hours,         
            approved=False,  # Admin still approves it

            # NEW FIELDS
            program_date=program.date,
            time_start=program.time_start,
            time_end=program.time_end,
            status=log_status,
        )
