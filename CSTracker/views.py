from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated

from django.db import models 

# Local/App Imports
from .permissions import IsAdminUser
from .models import Program
from .serializers import (
    LoginSerializer, 
    StudentSignupSerializer, 
    ProgramSerializer,
    ProgramApplicationSerializer
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

