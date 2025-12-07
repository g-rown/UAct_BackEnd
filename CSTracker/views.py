from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated, IsAdminUser # <-- NEW IMPORT
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes # <-- UPDATED IMPORT
from rest_framework.permissions import AllowAny # <-- NEW IMPORT
from rest_framework.exceptions import PermissionDenied, ValidationError # <-- CRITICAL: ValidationError MUST be imported
from django.db import transaction
from rest_framework.authentication import TokenAuthentication
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User, ProgramApplication
from .serializers import (
    ProgramSerializer,
    ProgramApplicationSerializer,
    ServiceLogSerializer,
    StudentProfileSerializer,
    UserSerializer,
    LoginSerializer,
    StudentSignupSerializer
)
from .permissions import IsAdminOrReadOnlySelf

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
# Signup View
# ---------------------------
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def signup_student(request):
    serializer = StudentSignupSerializer(data=request.data)
    
    if serializer.is_valid():
        # This calls StudentSignupSerializer.create() and returns the new User object
        user = serializer.save() 
        
        # --- Generate Token and Customize Response ---
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
            "is_student": user.is_student,
            "token": token.key, 
            "message": "Account created successfully."
        }, status=status.HTTP_201_CREATED)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------------
# PROGRAM VIEWSET
# ---------------------------
class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer

    authentication_classes = [TokenAuthentication] 
    permission_classes = [IsAuthenticated]

# ---------------------------
# STUDENT PROFILE VIEWSET
# ---------------------------
class StudentProfileViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer

    authentication_classes = [TokenAuthentication] 

    permission_classes = [IsAuthenticated, IsAdminOrReadOnlySelf]


    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return StudentProfile.objects.none()

        if user.is_admin:
            return StudentProfile.objects.all()

        return StudentProfile.objects.filter(user=user)
    
    # VITAL FIX FOR DELETION
    def perform_destroy(self, instance):
        """
        Deletes the associated User object, which cascades to delete the StudentProfile
        and all other related records (applications, logs, etc.).
        """
        user_to_delete = instance.user
        user_to_delete.delete()
# ---------------------------
# PROGRAM APPLICATION VIEWSET (FIXED)
# ---------------------------
class ProgramApplicationViewSet(viewsets.ModelViewSet):
    queryset = ProgramApplication.objects.all()
    serializer_class = ProgramApplicationSerializer

    authentication_classes = [TokenAuthentication] 
    permission_classes = [IsAuthenticated]

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

        if not user.is_authenticated:
            return ProgramApplication.objects.none()
        
        if user.is_admin:
            return self.queryset
        return self.queryset.filter(student__user=user)


    @action(detail=True, methods=['POST'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        application = self.get_object()
        latest_submission = application.submissions.order_by('-decision_at').first()
        if latest_submission and latest_submission.status != ProgramSubmissions.PENDING:
            return Response({"message": f"Application is already {latest_submission.get_status_display()}"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Create APPROVED submission record
            ProgramSubmissions.objects.create(
                application=application,
                status=ProgramSubmissions.APPROVED 
            )
            # Create a ServiceLog entry for tracking hours
            ServiceLog.objects.create(
                application=application,
                status=ServiceLog.STATUS_PENDING
            )
        return Response({"message": "Application approved and Service Log created."})

    @action(detail=True, methods=['POST'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        application = self.get_object()
        latest_submission = application.submissions.order_by('-decision_at').first()
        if latest_submission and latest_submission.status != ProgramSubmissions.PENDING:
            return Response({"message": f"Application is already {latest_submission.get_status_display()}"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Create REJECTED submission record
            ProgramSubmissions.objects.create(
                application=application,
                status=ProgramSubmissions.REJECTED
            )

            # Release the slot
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

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

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
