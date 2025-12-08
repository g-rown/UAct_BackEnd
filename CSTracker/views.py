from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework import mixins

from django.db import models 

# Local/App Imports
from .permissions import IsAdminUser, IsAdminOrReadOnlySelf
from .models import (
    User,
    StudentProfile,
    Program, 
    ProgramApplication, 
    ProgramSubmissions,
    ServiceLog,
)
from .serializers import (
    LoginSerializer, 
    StudentSignupSerializer, 
    ProgramSerializer,
    ProgramApplicationSerializer,
    ServiceHistorySerializer,
    StudentProfileDetailSerializer, 
    ProgramSubmissionsSerializer,
    ServiceLogAccreditationSerializer,
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
# SERVICE ACCREDITATION (MODIFIED)
# ---------------------------
# Using ListModelMixin and RetrieveModelMixin for GET, and UpdateModelMixin for PATCH/PUT
class ServiceAccreditationViewSet(mixins.ListModelMixin,
                                 mixins.RetrieveModelMixin,
                                 mixins.UpdateModelMixin,
                                 viewsets.GenericViewSet):
    
    # Change queryset to ServiceLog
    queryset = ServiceLog.objects.all().select_related(
        'application__program', 
        'application__student__user'
    )
    # Change serializer to the new one
    serializer_class = ServiceLogAccreditationSerializer 
    permission_classes = [IsAuthenticated, IsAdminUser]  
    
    def get_queryset(self):
        # Orders logs by submission date of the application
        return self.queryset.order_by('-application__submitted_at')

    # Endpoint for the admin to approve the log
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        log = self.get_object()
        
        # Check if already approved 
        if log.approved:
             return Response({'detail': 'Service log already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. Update the approval status
        # The signal (post_save on ServiceLog) will automatically credit student hours
        log.approved = True
        log.save(update_fields=['approved'])
        
        # 2. Return the updated log data
        # Refresh the instance to get the new status (set by the signal)
        log.refresh_from_db() 
        return Response(self.get_serializer(log).data, status=status.HTTP_200_OK)

# ---------------------------
# PROGRAM SUBMISSIONS VIEW (MODIFIED - REMOVE HOURS LOGIC)
# ---------------------------
class ProgramSubmissionsViewSet(viewsets.ModelViewSet):
    queryset = ProgramSubmissions.objects.all()
    serializer_class = ProgramSubmissionsSerializer
    permission_classes = [IsAuthenticated, IsAdminUser] # Ensure only admin can modify

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
            return Response({'error': 'Invalid status provided.'}, status=status.HTTP_400_BAD_REQUEST)


        # If status is changing, save it. The signal will handle slot management.
        submission.status = new_status
        submission.save()

        # REMOVED: The logic for updating student_profile.hours_completed 
        # This is now correctly handled by the ServiceLog signal when log.approved = True.
        
        return Response(self.get_serializer(submission).data, status=status.HTTP_200_OK)

# ---------------------------
# STUDENT PROGRESS SUMMARY VIEW
# ---------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_progress_summary(request):
    
    user = request.user
   
    try:
        student_profile = user.student_profile
    except StudentProfile.DoesNotExist:
        return Response(
            {"detail": "Student profile not found for this user."},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = StudentProfileDetailSerializer(student_profile)
   
    return Response(serializer.data, status=status.HTTP_200_OK)


