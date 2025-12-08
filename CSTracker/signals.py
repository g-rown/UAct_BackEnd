# signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models # Import F for atomic updates

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
    if created:
        # 1. Create initial ProgramSubmission (always PENDING)
        ProgramSubmissions.objects.create(
            application=instance,
            status=ProgramSubmissions.PENDING
        )

        # 2. Create initial ServiceLog
        log = ServiceLog(
            application=instance,
            approved=False # Default to False, admin will check this later
        )
        
        # Set the ServiceLog status based on the Program's date 
        log.status = log.get_program_status() 
        log.save()


# ----------------------------------------
# ProgramSubmissions updates ServiceLog status and Program slots
# ----------------------------------------
@receiver(post_save, sender=ProgramSubmissions)
def update_on_submission_decision(sender, instance, created, **kwargs):
    if created:
        return

    application = instance.application
    program = application.program
    log = ServiceLog.objects.filter(application=application).first()
    
    if not log:
        return 

    # --- 1. SET THE ServiceLog.submission_accepted STATUS ---
    
    if instance.status == ProgramSubmissions.APPROVED:
        # If approved, set the submission flag to True
        log.submission_accepted = True 
        
        # Atomically reserve the slot upon application approval
        if program.slots_remaining > 0:
            Program.objects.filter(pk=program.pk).update(
                slots_taken=models.F('slots_taken') + 1
            )
             
    elif instance.status == ProgramSubmissions.REJECTED:
        # If rejected, set the submission flag to False
        log.submission_accepted = False
        
        # Optional: You might need logic here to release a slot if the submission was PREVIOUSLY approved
        
    else:
        # PENDING status (log.submission_accepted is already False by default/previous state)
        # We don't need to save or proceed with other actions on PENDING
        return 
        
    # --- 2. UPDATE ServiceLog DATE STATUS (Always run on decision) ---
    new_log_status = log.get_program_status()
    if log.status != new_log_status:
        log.status = new_log_status

    # Save the ServiceLog to update both the status and the new submission_accepted flag
    log.save(update_fields=['status', 'submission_accepted'])


# ----------------------------------------
# Student Hours Update (Triggered ONLY by ServiceLog approved=True)
# ----------------------------------------
@receiver(post_save, sender=ServiceLog)
def update_hours_completed(sender, instance, created, **kwargs):
    # Only proceed if the 'approved' field has been set to True and it's not the initial creation
    # For a robust check, you'd typically need a tracker, but this simplified version works if 
    # the admin only calls save() on the log when explicitly approving it.
    if instance.approved and not created: 
        
        student_profile = instance.application.student
        program_hours = instance.application.program.hours
        
        # 1. Increment the student's completed hours
        student_profile.hours_completed += program_hours
        student_profile.save(update_fields=['hours_completed'])
        
        # 2. Ensure ServiceLog status reflects the completion status
        final_status = instance.get_program_status()
        if instance.status != final_status:
            instance.status = final_status
            instance.save(update_fields=['status'])