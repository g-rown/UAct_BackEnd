from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication
from django.contrib.auth.hashers import make_password

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
        fields = ['id', 'username', 'is_student', 'is_admin']


# ---------------------------
# STUDENT PROFILE SERIALIZER
# ---------------------------
class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    hours_remaining = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'phone_number',
            'course', 'year_level', 'section',
            'total_required_hours', 'hours_completed',
            'hours_remaining'
        ]

    def get_hours_remaining(self, obj):
        return obj.total_required_hours - obj.hours_completed


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

# ---------------------------
# PROGRAM APPLICATION SERIALIZER
# ---------------------------
class ProgramApplicationSerializer(serializers.ModelSerializer):
    student = StudentProfileSerializer(read_only=True) 
    program = ProgramSerializer(read_only=True)

    program_id = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(),
        source='program',
        write_only=True
    )

    class Meta:
        model = ProgramApplication
        fields = [
            'id', 'student', 'program', 'program_id', 'status', 'submitted_at',
            'first_name', 'last_name', 'email', 'phone_number', 
            'course', 'year_level', 'emergency_contact_name', 'emergency_contact_phone'
        ]
        read_only_fields = ['status', 'submitted_at']


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
            'status', 'approved', 'application'
        ]
        read_only_fields = ['id', 'application', 'status', 'approved']


# ---------------------------
# 
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
# 
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
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "A user with that username already exists."})
        return data
    
    def create(self, validated_data):
        user_data = {
            'username': validated_data['username'],
            'password': validated_data['password'],
            'first_name': validated_data['first_name'],
            'last_name': validated_data['last_name'],
            'email': validated_data['email'],
        }
        
        profile_data = {
            'year_level': validated_data['year_level'],
            'section': validated_data['section'],
            'phone_number': validated_data['phone_number'],
            'course': validated_data['course'], 
        }

        user_serializer = UserCreationSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        student_profile = StudentProfile.objects.create(
            user=user,
            **profile_data
        )
        
        return user
    