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

        # Generate or retrieve the token for the user
        token, created = Token.objects.get_or_create(user=user) # <--- NEW LINE

        return Response({
            "id": user.id,
            "username": user.username,
            "is_admin": getattr(user, "is_admin", False),
            "is_student": getattr(user, "is_student", False),
            "token": token.key # <--- NEW LINE: Send the token to the client
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


# ---------------------------
# PROGRAM APPLICATION VIEWSET (FIXED)
# ---------------------------
class ProgramApplicationViewSet(viewsets.ModelViewSet):
    queryset = ProgramApplication.objects.all()
    serializer_class = ProgramApplicationSerializer
    
    permission_classes = [IsAuthenticated] 

    def perform_create(self, serializer):
        """
        Creates the application, links it to the student, and updates the program slots.
        """
        try:
            student_profile = self.request.user.student_profile
        except StudentProfile.DoesNotExist:
            raise PermissionDenied(detail="The authenticated user is not associated with a Student Profile.")

        with transaction.atomic():
            # A. Save the ProgramApplication instance
            application = serializer.save(student=student_profile)
            
            # B. Retrieve the linked Program object
            program = application.program
            
            # C. Check for availability
            if program.slots_taken >= program.slots:
                # This raises a DRF exception which returns a 400 Bad Request JSON response
                # and forces a rollback of the transaction.
                raise ValidationError({
                    "detail": "This program is currently full and cannot accept new applications."
                })
                
            # D. Update the slots_taken count
            program.slots_taken += 1
            
            # E. Save the updated Program object to the database
            program.save()


    # Approve a program submissions
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        application = self.get_object()
        program = application.program

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=status.HTTP_400_BAD_REQUEST)

        # NOTE: This check should ideally be removed here as slots are taken on *creation*.
        # However, keeping it as a redundant check for safety:
        # if program.slots_taken >= program.slots:
        #     return Response({"message": "No slots remaining"}, status=status.HTTP_400_BAD_REQUEST)

        # Use a transaction for safety when updating multiple records
        with transaction.atomic():
            # Update application status
            application.status = "approved"
            application.save()

            # The slot count was already updated during perform_create. 
            # We don't need to increment it here again.
            
            # If you want to use the 'approve' action to TAKE the slot, 
            # you must REMOVE the slot update from perform_create instead.
            # Assuming slots are taken immediately upon application:
            pass # No slot update needed here.

        return Response({"message": "Application approved!"})

    # Reject a program application
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        application = self.get_object()

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=status.HTTP_400_BAD_REQUEST)

        # If you reject an application, you should free up the slot.
        with transaction.atomic():
            program = application.program
            
            # Update application status
            application.status = "rejected"
            application.save()

            # 🔑 NEW LOGIC: Decrement slots if the application was previously counted (i.e., status was pending/approved)
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

    # Approve a service log and update student hours
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        log = self.get_object()

        if log.approved:
            return Response({"message": "Already approved"}, status=status.HTTP_400_BAD_REQUEST)

        log.approved = True
        log.save()

        # Add hours to student profile
        student = log.student
        student.hours_completed += log.hours
        student.save()

        return Response({"message": "Log approved and student hours updated"})