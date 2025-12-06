from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated # <-- NEW IMPORT
from rest_framework.exceptions import PermissionDenied, NotAuthenticated # <-- NEW IMPORT
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.decorators import api_view, authentication_classes, permission_classes # <-- UPDATED IMPORT
from rest_framework.permissions import AllowAny # <-- NEW IMPORT
from rest_framework.exceptions import PermissionDenied, ValidationError # <-- CRITICAL: ValidationError MUST be imported
from django.db import transaction

from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication
from .serializers import (
    ProgramSerializer,
    ProgramApplicationSerializer,
    ServiceLogSerializer,
    StudentProfileSerializer,
    UserSerializer,
    LoginSerializer
)

# ---------------------------
# LOGIN VIEW
# ---------------------------
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data

        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "id": user.id,
            "username": user.username,
            "is_admin": getattr(user, "is_admin", False),
            "is_student": getattr(user, "is_student", False),
            "token": token.key 
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# PROGRAM VIEWSET
# ---------------------------
class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer


# ---------------------------
# STUDENT PROFILE VIEWSET
# ---------------------------
class StudentProfileViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return self.queryset
        return self.queryset.filter(student__user=user)


# ---------------------------
# PROGRAM APPLICATION VIEWSET (FIXED)
# ---------------------------
class ProgramApplicationViewSet(viewsets.ModelViewSet):
    queryset = ProgramApplication.objects.all()
    serializer_class = ProgramApplicationSerializer

    def perform_create(self, serializer):
        try:
            student_profile = self.request.user.student_profile
        except StudentProfile.DoesNotExist:
            raise PermissionDenied("User has no associated Student Profile.")

        program = serializer.validated_data['program']

        if program.slots_taken >= program.slots:
            raise ValidationError({"detail": "Program is full."})

        with transaction.atomic():
            application = serializer.save(student=student_profile)
            program.slots_taken += 1
            program.save()

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return self.queryset
        return self.queryset.filter(student__user=user)


    # Approve action
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        application = self.get_object()

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=400)

        application.status = "approved"
        application.save()
        return Response({"message": "Application approved!"})

    # Reject action
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        application = self.get_object()

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=400)

        with transaction.atomic():
            application.status = "rejected"
            application.save()

            program = application.program
            if program.slots_taken > 0:
                program.slots_taken -= 1
                program.save()

        return Response({"message": "Application rejected! Slot freed."})


# ---------------------------
# SERVICE LOG VIEWSET
# ---------------------------
class ServiceLogViewSet(viewsets.ModelViewSet):
    queryset = ServiceLog.objects.all()
    serializer_class = ServiceLogSerializer

    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        log = self.get_object()

        if log.approved:
            return Response({"message": "Already approved"}, status=400)

        with transaction.atomic():
            log.approved = True
            log.save()

            student = log.application.student
            student.hours_completed += log.application.program.hours
            student.save()

        return Response({"message": "Log approved and student hours updated"})
