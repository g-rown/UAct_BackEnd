# views.py (START OF FILE)

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action

from django.db import models 

# Local/App Imports
from .permissions import IsAdminUser, IsAdminOrReadOnlySelf # ⭐️ Merge permissions
from .models import (
    Program, 
    ProgramApplication, 
    StudentProfile, # ⭐️ Add StudentProfile model import
    ProgramSubmissions,
)
from .serializers import (
    LoginSerializer, 
    StudentSignupSerializer, 
    ProgramSerializer,
    ProgramApplicationSerializer,
    ServiceHistorySerializer,
    # ⭐️ Add the detail serializer here (the one that actually exists)
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
    """
    Provides CRUD operations for Program model.
    Read-only for students, Full CRUD for admin users.
    """
    serializer_class = ProgramSerializer
    # Applies IsAuthenticated universally, and IsAdminUser for POST/PUT/DELETE
    permission_classes = [IsAuthenticated, IsAdminUser] 

    def get_queryset(self):
        """
        Admins see all programs. Students only see programs with remaining slots.
        """
        user = self.request.user
        if user.is_admin:
            # Admin sees all programs
            return Program.objects.all().order_by('date')
        else:
            # Student sees only programs with remaining slots
            # This is the logic of your old program_list view
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
    # The `context={'request': request}` is CRITICAL for the serializer to access the authenticated user.
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
# CSTracker/views.py

# ---------------------------
# SERVICE HISTORY VIEW (IMPLEMENTED)
# ---------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_history(request):
    """
    Fetches the list of program applications for the currently authenticated student.
    """
    user = request.user
    
    # Check if the user is a student (use 'False' as default for safety)
    if not getattr(user, "is_student", False): 
        return Response({"detail": "Access denied. Only students can view their history."}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    # Ensure the user has a student_profile to query against
    try:
        student_profile = user.student_profile
    except StudentProfile.DoesNotExist:
        return Response({"detail": "Student profile not found for this user."}, 
                        status=status.HTTP_404_NOT_FOUND)

    # 1. Fetch the applications for the logged-in student.
    # We use select_related('program') to avoid the N+1 query problem by fetching 
    # the related Program object in the same query.
    applications = ProgramApplication.objects.filter(
        student=student_profile # Filter by the StudentProfile instance
    ).select_related('program').order_by('-submitted_at') 
    
    # 2. Serialize the data using the new ServiceHistorySerializer.
    serializer = ServiceHistorySerializer(applications, many=True)
    
    # 3. Return the data.
    return Response(serializer.data, status=status.HTTP_200_OK)

class StudentProfileViewSet(viewsets.ModelViewSet):
    """
    Provides CRUD operations for StudentProfile model.
    List/Create/Delete for Admin. Read/Update for Admin or Owner.
    """
    queryset = StudentProfile.objects.all()
    # You need a serializer that includes User fields for display (e.g., first_name, email)
    # Let's assume you create a StudentProfileDetailSerializer for this, 
    # as the list view needs to display related User data.
    serializer_class = StudentProfileDetailSerializer 
    
    # 2. PERMISSION FOR STUDENT PROFILE VIEWSET (Admin or Owner access)
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
# SERVICE ACCREDITATION/ADMIN VIEW
# ---------------------------
class ServiceAccreditationViewSet(viewsets.ModelViewSet):
    """
    Provides list of applications for Admin accreditation (approval/rejection).
    Only Admins can access this view.
    """
    # ⭐️ Assuming ServiceHistorySerializer can handle all fields needed for review
    serializer_class = ServiceHistorySerializer 
    
    # 🛑 Set Permissions: Only Admin users can perform these actions
    permission_classes = [IsAuthenticated, IsAdminUser] 
    
    def get_queryset(self):
        """
        Admins/Facilitators see all program applications, possibly filtered by 'Pending' status.
        """
        # 1. Start with all applications
        queryset = ProgramApplication.objects.all().select_related('program', 'student__user')
        
        # 2. You might want to filter only PENDING logs by default:
        # (Assuming your ProgramApplication model has a 'status' field like 'PENDING')
        # queryset = queryset.filter(status='PENDING') 
        
        # 3. Order the results
        return queryset.order_by('-submitted_at')

    # You would also add a 'perform_update' method here 
    # to handle the approval/rejection logic.
    # e.g., def perform_update(self, serializer): ...

# ---------------------------
# PROGRAM SUBMISSIONS VIEW
# ---------------------------

class ProgramSubmissionsViewSet(viewsets.ModelViewSet):
    queryset = ProgramSubmissions.objects.all()
    serializer_class = ProgramSubmissionsSerializer
    # Permission classes (e.g., IsAdminUser) should be set here 
    # to restrict access to only those who can review submissions.

    def get_queryset(self):
        """
        Optionally restricts the returned submissions to a given program ID,
        which is what your React Native frontend is doing: 
        `?program=programId`
        """
        queryset = self.queryset
        program_id = self.request.query_params.get('program')
        if program_id is not None:
            # Filters submissions by the ProgramApplication's program
            queryset = queryset.filter(application__program__id=program_id)
        return queryset.order_by('-decision_at')


    # This method corresponds to your frontend's POST request for status updates:
    # `${API_BASE_URL}/programsubmissions/${submissionId}/update_status/`
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        submission = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'Invalid status provided.'}, status=400)

        # 1. Update the status
        submission.status = new_status
        submission.save()

        # 2. (Optional but recommended): Handle hours update if approved
        if new_status == 'approved':
            # Get the program's hours and the student profile
            program_hours = submission.application.program.hours
            student_profile = submission.application.student
            
            # Update hours_completed and save the student profile
            student_profile.hours_completed += program_hours
            student_profile.save()

        return Response(self.get_serializer(submission).data, status=200)