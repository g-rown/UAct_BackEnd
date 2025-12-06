from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User

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
            'id', 'user',
            'course', 'year_level',
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

    class Meta:
        model = ProgramSubmissions
        fields = '__all__'


# ---------------------------
# SERVICE LOG SERIALIZER
# ---------------------------
class ServiceLogSerializer(serializers.ModelSerializer):
    student = StudentProfileSerializer(read_only=True)
    program = ProgramSerializer(read_only=True)

    class Meta:
        model = ServiceLog
        fields = '__all__'