
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action

from django.db import models 

# Local/App Imports
from .permissions import IsAdminUser, IsAdminOrReadOnlySelf
from .models import (
    User,
    StudentProfile,
    Program, 
    ProgramApplication, 
    ProgramSubmissions
)
from .serializers import (
    LoginSerializer, 
    StudentSignupSerializer, 
    ProgramSerializer,
    ProgramApplicationSerializer,
    ServiceHistorySerializer,
    StudentProfileDetailSerializer, 
    ProgramSubmissionsSerializer,
)


# ---------------------------
# LOGIN VIEW
# ---------------------------
@api_view(['POST'])
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
# SIGNUP VIEW
# ---------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def student_signup(request):
    serializer = StudentSignupSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "message": "User registered successfully",
            "username": user.username,
            "id": user.id,
            "token": token.key 
        }, status=status.HTTP_201_CREATED) 
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# COMMUNITY PROGRAMS VIEW
# ---------------------------
class ProgramViewSet(viewsets.ModelViewSet):
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminUser] 

    def get_queryset(self):
        """
        Admins see all programs. Students only see programs with remaining slots.
        """
        user = self.request.user
        if user.is_admin:
            return Program.objects.all().order_by('date')
        else:
            return Program.objects.filter(slots_taken__lt=models.F('slots')).order_by('date')

# ---------------------------
# PROGRAM APPLICATION VIEW
# ---------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def program_apply(request):
    """
    Handles a student submitting an application for a community program.
    """
    serializer = ProgramApplicationSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        try:
            application = serializer.save()
            
            return Response({
                "message": "Application submitted successfully.",
                "application_id": application.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # Catch unexpected errors during save/slot increment
            print(f"Error during application save: {e}")
            return Response({"detail": "An internal error occurred during submission."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
             
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# SERVICE HISTORY VIEW
# ---------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_history(request):
    user = request.user
    
    if not getattr(user, "is_student", False): 
        return Response({"detail": "Access denied. Only students can view their history."}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    try:
        student_profile = user.student_profile
    except StudentProfile.DoesNotExist:
        return Response({"detail": "Student profile not found for this user."}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    applications = ProgramApplication.objects.filter(
        student=student_profile 
    ).select_related('program').order_by('-submitted_at') 
    
    serializer = ServiceHistorySerializer(applications, many=True)
    
    return Response(serializer.data, status=status.HTTP_200_OK)

class StudentProfileViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileDetailSerializer 
    
    permission_classes = [IsAuthenticated, IsAdminOrReadOnlySelf]

    def get_queryset(self):
        """
        Admins can see all students. Students can only see their own profile.
        """
        user = self.request.user
        if user.is_admin:
            # Admin sees all student profiles
            # Use select_related to fetch the related User object in one query
            return StudentProfile.objects.all().select_related('user')
        else:
            # Student can only see their own profile (which should be a list of one)
            return StudentProfile.objects.filter(user=user).select_related('user')


# ---------------------------
# SERVICE ACCREDITATION
# ---------------------------
class ServiceAccreditationViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceHistorySerializer 
    permission_classes = [IsAuthenticated, IsAdminUser] 
    
    def get_queryset(self):
        queryset = ProgramApplication.objects.all().select_related('program', 'student__user')
        return queryset.order_by('-submitted_at')


# ---------------------------
# PROGRAM SUBMISSIONS VIEW
# ---------------------------
class ProgramSubmissionsViewSet(viewsets.ModelViewSet):
    queryset = ProgramSubmissions.objects.all()
    serializer_class = ProgramSubmissionsSerializer

    def get_queryset(self):
        queryset = self.queryset
        program_id = self.request.query_params.get('program')
        if program_id is not None:
            # Filters submissions by the ProgramApplication's program
            queryset = queryset.filter(application__program__id=program_id)
        return queryset.order_by('-decision_at')


    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        submission = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'Invalid status provided.'}, status=400)


        submission.status = new_status
        submission.save()

        if new_status == 'approved':
            program_hours = submission.application.program.hours
            student_profile = submission.application.student
            
            student_profile.hours_completed += program_hours
            student_profile.save()

        return Response(self.get_serializer(submission).data, status=200)
