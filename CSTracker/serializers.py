from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication
from .models import Program # Import Program model explicitly if needed elsewhere, but it's listed above

# ---------------------------
# LOGIN SERIALIZER
# (No changes)
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
# USER SERIALIZER
# (No changes)
# ---------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_student', 'is_admin']


# ---------------------------
# STUDENT PROFILE SERIALIZER
# (No changes)
# ---------------------------
class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    hours_remaining = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user',
            'course', 'year_level',
            'total_required_hours', 'hours_completed',
            'hours_remaining'
        ]

    def get_hours_remaining(self, obj):
        return obj.total_required_hours - obj.hours_completed


# ---------------------------
# PROGRAM SERIALIZER
# (No changes)
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
# PROGRAM APPLICATION SERIALIZER (FIXED)
# ---------------------------
class ProgramApplicationSerializer(serializers.ModelSerializer):
    # For GET requests (READ): show the full nested student object
    # For POST requests (WRITE): The field is read_only, as the ViewSet will set the student automatically
    student = StudentProfileSerializer(read_only=True) 
    
    # For POST requests (WRITE): This allows the client to submit the ID of the program
    # For GET requests (READ): This will display the ID of the program.
    # To show nested Program data on GET, you'll need a separate read serializer or a custom field.
    # For simplicity and the fix, we revert to the default ModelSerializer behavior for 'program' 
    # but ensure 'student' is read-only since it's set by the view.
    # Alternatively, you can explicitly define the Program as read-only for nested data, but then
    # the client MUST submit a program_id, which requires more complex handling.
    
    # *** Easiest Fix: Let ModelSerializer handle it, but keep student read-only as the view sets it. ***
    # We will let the view handle both student and other fields on creation.
    
    # To display nested data on GET requests and accept IDs on POST:
    program_id = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(),
        source='program',
        write_only=True # Only accepts data on write, but doesn't show in the read output
    )
    program = ProgramSerializer(read_only=True) # Shows nested data on read, ignores on write

    class Meta:
        model = ProgramApplication
        # We list all fields, including the foreign key fields, and the newly added 'program_id'
        fields = [
            'id', 'student', 'program', 'program_id', 'status', 'submitted_at',
            'first_name', 'last_name', 'email', 'phone_number', 
            'course', 'year_level', 'emergency_contact_name', 'emergency_contact_phone'
        ]
        read_only_fields = ['status', 'submitted_at'] # status is set by default, submitted_at is auto_now_add

# ---------------------------
# SERVICE LOG SERIALIZER
# (No changes)
# ---------------------------
class ServiceLogSerializer(serializers.ModelSerializer):
    student = StudentProfileSerializer(read_only=True)
    program = ProgramSerializer(read_only=True)

    class Meta:
        model = ServiceLog
        fields = '__all__'