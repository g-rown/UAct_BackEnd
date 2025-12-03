from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from .models import Program, ProgramSubmissions, ServiceLog, StudentProfile, User
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
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data
        return Response({
            "id": user.id,
            "username": user.username,
            "is_admin": getattr(user, "is_admin", False),
            "is_student": getattr(user, "is_student", False)
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
# PROGRAM APPLICATION VIEWSET
# ---------------------------
class ProgramApplicationViewSet(viewsets.ModelViewSet):
    queryset = ProgramSubmissions.objects.all()
    serializer_class = ProgramApplicationSerializer

    # Approve a program submissions
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        application = self.get_object()
        program = application.program

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=status.HTTP_400_BAD_REQUEST)

        if program.slots_taken >= program.slots:
            return Response({"message": "No slots remaining"}, status=status.HTTP_400_BAD_REQUEST)

        # Update application status
        application.status = "approved"
        application.save()

        # Update program slot count
        program.slots_taken += 1
        program.save()

        return Response({"message": "Application approved!"})

    # Reject a program application
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        application = self.get_object()

        if application.status != "pending":
            return Response({"message": "Already processed"}, status=status.HTTP_400_BAD_REQUEST)

        application.status = "rejected"
        application.save()

        return Response({"message": "Application rejected!"})


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