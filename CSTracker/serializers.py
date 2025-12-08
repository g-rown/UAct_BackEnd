from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password


from django.db import models

from .models import User, StudentProfile, Program, ProgramApplication, ProgramSubmissions


# ---------------------------
# LOGIN SERIALIZER
# ---------------------------
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


    def validate(self, data):
        user = authenticate(username=data.get('username'), password=data.get('password'))
        if user:
            return user
        raise serializers.ValidationError("Invalid Credentials")




# ---------------------------
# STUDENT SIGNUP SERIALIZER
# ---------------------------
class StudentSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    course = serializers.CharField(max_length=10)
    year_level = serializers.CharField(max_length=10)
    section = serializers.CharField(max_length=10)
    phone_number = serializers.CharField(max_length=15)


    def validate_email(self, value):
        # Check if the email is already in use
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value


    def validate_username(self, value):
        # Check if the username is already in use
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


    def create(self, validated_data):
       
        user_fields = [ 'username', 'password', 'first_name', 'last_name', 'email' ]
        profile_fields = [ 'course', 'year_level', 'section', 'phone_number' ]
        user_data = {k: validated_data.pop(k) for k in user_fields}
        profile_data = {k: validated_data.pop(k) for k in profile_fields}


        # 1. Create the User without password hash
        user = User.objects.create(
            username=user_data['username'],
            email=user_data['email'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            is_student=True,
            is_admin=False,
        )
        # 2. Set password and save
        user.set_password(user_data['password'])
        user.save()


        # 3. Use the get/create method on the profile manager to update in one step
        #    The 'user.studentprofile' method you used is excellent, but we can
        #    make the update explicit.
       
        # Access the profile created by the signal
        profile = user.student_profile
       
        # Assign and save fields in one step using the **profile_data shortcut
        # This is slightly cleaner than the loop/setattr
        for field, value in profile_data.items():
            setattr(profile, field, value)
           
        profile.save() # Saves all changes to the profile


        return user


# ---------------------------
# PROGRAMS SERIALIZER
# ---------------------------
class ProgramSerializer(serializers.ModelSerializer):
    slots_remaining = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = Program
        fields = [
            'id', 'name', 'description', 'location', 'facilitator',
            'date', 'time_start', 'time_end', 'hours',
            'slots', 'slots_taken', 'slots_remaining'
        ]
        read_only_fields = ['slots_remaining', 'slots_taken']




    def get_slots_remaining(self, obj):
        return obj.slots - obj.slots_taken




# ---------------------------
# PROGRAM APPLICATION SERIALIZER
# ---------------------------
class ProgramApplicationSerializer(serializers.ModelSerializer):
    program_id = serializers.IntegerField(write_only=True)


    class Meta:
        model = ProgramApplication
        fields = [
            'id',
            'program_id',
            'emergency_contact_name',
            'emergency_contact_phone',
            'submitted_at'
        ]
        read_only_fields = ['submitted_at', 'id']
       
    def validate_program_id(self, value):
        """Check if the program exists, has slots, and the student hasn't already applied."""
        try:
            program = Program.objects.get(pk=value)
        except Program.DoesNotExist:
            raise serializers.ValidationError("Program not found.")
           
        if program.slots_remaining <= 0:
            raise serializers.ValidationError("This program is fully booked.")
           
        # Get the authenticated user's profile from the context
        request = self.context.get('request', None)
        if request and request.user.is_authenticated:
            try:
                student_profile = request.user.student_profile
            except StudentProfile.DoesNotExist:
                raise serializers.ValidationError("User is not associated with a student profile.")
               
            # Check for duplicate application
            if ProgramApplication.objects.filter(student=student_profile, program=program).exists():
                raise serializers.ValidationError("You have already applied to this program.")
           
        return value
       
    def create(self, validated_data):
        # 1. Get the authenticated student profile
        user = self.context['request'].user
        student_profile = user.student_profile
           
        # 2. Get the program object using the validated ID
        program_id = validated_data.pop('program_id')
        program = Program.objects.get(pk=program_id)
       
        # 3. Create the ProgramApplication instance
        application = ProgramApplication.objects.create(
            student=student_profile,
            program=program,
            **validated_data
        )
       
        # 4. Atomically increment the slots_taken count on the Program model
        program.slots_taken = models.F('slots_taken') + 1
        program.save(update_fields=['slots_taken'])
        program.refresh_from_db() # Refresh the instance to show the updated value
       
        return application

# CSTracker/serializers.py (Add this section)

# ---------------------------
# NESTED PROGRAM DETAIL SERIALIZER
# ---------------------------
class ProgramDetailSerializer(serializers.ModelSerializer):
    """Serializer for nested program details."""
    class Meta:
        model = Program
        # Include necessary display fields for the student's history
        fields = ('id', 'name', 'location', 'date', 'time_start', 'time_end', 'hours')

# CSTracker/serializers.py (Add this section)

# ---------------------------
# SERVICE HISTORY SERIALIZER
# ---------------------------
class ServiceHistorySerializer(serializers.ModelSerializer):
    """
    Serializer to display a student's service application history.
    It fetches the status from the latest related ProgramSubmissions record.
    """
    
    # Use the nested serializer for the 'program' field
    program = ProgramDetailSerializer(read_only=True)
    
    # 1. Use the SerializerMethodField to dynamically fetch the status
    current_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ProgramApplication
        # 2. Correct the 'fields' list: 
        #    - Remove 'status' (the non-existent field)
        #    - Add 'current_status' (the new SerializerMethodField)
        fields = [
            'id', 
            'program', 
            'emergency_contact_name',
            'emergency_contact_phone',
            'current_status', # <-- Use the SerializerMethodField name
            'submitted_at',
        ]
        read_only_fields = fields

    # 3. Define the method to fetch the latest status
    def get_current_status(self, obj):
        """
        Retrieves the status from the LATEST related ProgramSubmissions object.
        """
        # Note: 'submissions' is the related_name from the ProgramSubmissions model
        # obj is the ProgramApplication instance
        
        # We order by decision_at descending to get the most recent submission.
        latest_submission = obj.submissions.order_by('-decision_at').first()
        
        if latest_submission:
            # Returns the status (e.g., "approved", "pending")
            return latest_submission.status
        
        # Fallback if no submission record exists for this application
        return 'UNKNOWN'