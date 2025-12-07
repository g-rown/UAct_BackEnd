from rest_framework import permissions

# --------------------------------------------------
# 1. PERMISSION FOR PROGRAM VIEWSET (Read by all auth users, Write by Admin)
# --------------------------------------------------
class IsAdminUser(permissions.BasePermission):
    """
    Custom permission for Program management:
    1. Authenticated users (Students/Admins) can READ (list/retrieve).
    2. Only Admin users can WRITE (create/update/delete).
    """
    def has_permission(self, request, view):
        # Must be authenticated to access any part of this viewset
        if not request.user.is_authenticated:
            return False
            
        # Allow read requests (GET, HEAD, OPTIONS) for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Allow write/delete requests (POST, PUT, PATCH, DELETE) only for Admins
        return request.user.is_admin

# --------------------------------------------------
# 2. PERMISSION FOR STUDENT PROFILE VIEWSET (Admin or Owner access)
# --------------------------------------------------
class IsAdminOrReadOnlySelf(permissions.BasePermission):
    """
    Custom permission for StudentProfile access:
    - Admin: Full CRUD access.
    - Owner (Student): Full CRUD access on their own profile.
    - Others: No access (filtered by get_queryset).
    """

    def has_permission(self, request, view):
        # Only allow authenticated users to proceed to object-level check
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # 1. Admins always have full permission
        if request.user.is_admin:
            return True
            
        # 2. Check if the authenticated user is the owner of the profile (obj is the StudentProfile instance)
        is_owner = (obj.user == request.user)

        if request.method in permissions.SAFE_METHODS:
            # Read permissions (GET, HEAD, OPTIONS) are allowed if the user is the owner.
            # (Note: The get_queryset method in StudentProfileViewSet already filters this list).
            return is_owner 
        
        # 3. Write permissions (PUT, PATCH, DELETE) are only allowed if the user is the owner
        return is_owner

# --------------------------------------------------
# 3. SIMPLE ADMIN-ONLY PERMISSION
# --------------------------------------------------
class IsAdminUserOnly(permissions.BasePermission):
    """
    Allows access only to authenticated Admin users. 
    Ideal for views like ProgramSubmissionViewSet or ServiceLog approval.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin