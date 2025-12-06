# signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    User, StudentProfile, ServiceLog,
    ProgramSubmissions, ProgramApplication, Program
)

# ----------------------------------------
# StudentProfile Creation on User Creation
# ----------------------------------------
@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    if created and instance.is_student:
        StudentProfile.objects.create(user=instance)


# ----------------------------------------
# Prevent Duplicate Applications
# ----------------------------------------
@receiver(pre_save, sender=ProgramApplication)
def prevent_duplicate_application(sender, instance, **kwargs):
    qs = ProgramApplication.objects.filter(
        student=instance.student,
        program=instance.program
    )
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise ValueError("You already applied for this program.")


# ----------------------------------------
# Create ProgramSubmission and ServiceLog on Application Creation
# ----------------------------------------
@receiver(post_save, sender=ProgramApplication)
def create_submission_and_log_from_application(sender, instance, created, **kwargs):

        ProgramSubmissions.objects.create(
            application=instance,
            status=ProgramSubmissions.PENDING
        )

        ServiceLog.objects.create(
            application=instance,
            status=ServiceLog.STATUS_PENDING,
            approved=False
        )


# ----------------------------------------
# Approval Workflow (ProgramSubmissions -> ServiceLog -> Student Hours/Slots)
# ----------------------------------------
@receiver(post_save, sender=ProgramSubmissions)
def update_on_approval(sender, instance, **kwargs):
    
    if instance.status != ProgramSubmissions.APPROVED:
        return

    application = instance.application
    program = application.program
    
    log = ServiceLog.objects.filter(application=application).first()
    
    if not log or log.approved:
        return 

    log.approved = True
    log.status = ServiceLog.STATUS_COMPLETED 
    log.save(update_fields=['approved', 'status']) 
    
    if program.slots_taken < program.slots:
        program.slots_taken += 1
        program.save(update_fields=['slots_taken'])


# ----------------------------------------
# 4. Student Hours Update 
# ----------------------------------------
@receiver(post_save, sender=ServiceLog)
def update_hours_completed(sender, instance, **kwargs):
    if instance.approved:
        student_profile = instance.application.student
        
        student_profile.hours_completed += instance.application.program.hours
        student_profile.save(update_fields=['hours_completed'])