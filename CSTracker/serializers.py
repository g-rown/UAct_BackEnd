from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication

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
