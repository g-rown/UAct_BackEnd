from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication
from django.contrib.auth.hashers import make_password
from django.db import transaction

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
# USER SERIALIZER
# ---------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_student', 'is_admin']


# ---------------------------
# STUDENT PROFILE SERIALIZER <--- NEWLY ADDED SERIALIZER
# ---------------------------
class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'course', 'year_level', 'section', 'phone_number', 
            'total_hours', 'is_active'
        ]
        read_only_fields = ['total_hours']

# ---------------------------
# PROGRAM SERIALIZER
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

# -----------------------------------
# PROGRAM APPLICATION SERIALIZER 
# -----------------------------------
class ProgramApplicationSerializer(serializers.ModelSerializer):
    # Read-only nested serializers for displaying data
    # THIS LINE NOW WORKS!
    student = StudentProfileSerializer(read_only=True) 
    program = ProgramSerializer(read_only=True)

    # Status field fetched from the related ProgramSubmissions model
    status = serializers.SerializerMethodField(read_only=True)

    # Write-only field for creating the application (required during POST)
    program_id = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(),
        source='program',
        write_only=True
    )

    class Meta:
        model = ProgramApplication
        fields = [
            'id', 'student', 'program', 'program_id', 
            'emergency_contact_name', 'emergency_contact_phone', 
            'submitted_at', 'status'
        ]
        read_only_fields = ['submitted_at', 'status']

    # Method to get the status from the related ProgramSubmissions object
    def get_status(self, obj):
        # We assume the status is determined by the most recent ProgramSubmission
        latest_submission = obj.submissions.order_by('-decision_at').first()
        return latest_submission.get_status_display() if latest_submission else "No Submission Yet"


# ---------------------------
# SERVICE LOG SERIALIZER
# ---------------------------
class ServiceLogSerializer(serializers.ModelSerializer):
    student_full_name = serializers.CharField(source='application.student.user.full_name', read_only=True)
    program_name = serializers.CharField(source='application.program.name', read_only=True)
    program_hours = serializers.IntegerField(source='application.program.hours', read_only=True)

    class Meta:
        model = ServiceLog
        fields = [
            'id', 'application', 'student_full_name', 'program_name', 'program_hours',
            'status', 'approved',
        ]
        read_only_fields = ['id', 'status', 'approved']


# ---------------------------
# USER CREATION SERIALIZER
# ---------------------------
class UserCreationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            password=make_password(validated_data['password']),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            is_student=True
        )
        return user


# ---------------------------
# SIGNUP SERIALIZER (REVISED)
# ---------------------------
class StudentSignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()

    course = serializers.CharField(max_length=10)
    year_level = serializers.CharField(max_length=10)
    section = serializers.CharField(max_length=10)
    phone_number = serializers.CharField(max_length=15)

    def validate(self, data):
        # Prevent duplicate username
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "This username is already taken."})

        # Prevent duplicate email
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        return data

    @transaction.atomic
    def create(self, validated_data):

        # STEP 1: Split validated data
        user_data = {
            "username": validated_data["username"],
            "email": validated_data["email"],
            "password": validated_data["password"],
            "first_name": validated_data["first_name"],
            "last_name": validated_data["last_name"],
        }

        profile_data = {
            "course": validated_data["course"],
            "year_level": validated_data["year_level"],
            "section": validated_data["section"],
            "phone_number": validated_data["phone_number"],
        }

        # STEP 2: Create User
        user_serializer = UserCreationSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        # STEP 3: Prevent duplicate StudentProfile
        if StudentProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("Student profile already exists for this user")

        # STEP 4: Create StudentProfile
        StudentProfile.objects.create(
            user=user,
            **profile_data,
        )

        return user