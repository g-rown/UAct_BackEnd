from rest_framework import permissions

class IsAdminOrReadOnlySelf(permissions.BasePermission):
    """
    Custom permission to allow:
    1. Admins: Full access (R/W/D) to all objects and list/create views.
    2. Students (Owner): Read (GET) and Update (PUT/PATCH) access to their own profile.
    3. All Others: Denied.
    """

    def has_permission(self, request, view):
        # Allow access to list/create (GET/POST on /profiles/) only for Admins
        if request.user.is_admin:
            return True
        
        # Deny list/create access to students and unauthenticated users
        # Detail views (GET/PUT/PATCH/DELETE on /profiles/1/) proceed to has_object_permission
        # but only if the user is authenticated.
        return request.user.is_authenticated and view.detail 

    def has_object_permission(self, request, view, obj):
        # 1. Admins have full access to all objects
        if request.user.is_admin:
            return True

        # Check if the authenticated user is the object's owner
        is_owner = obj.user == request.user
        
        # 2. Owners (Students) have Read and Update access
        if is_owner and request.method in (permissions.SAFE_METHODS + ('PUT', 'PATCH')):
            return True
        
        # 3. All others (including a Student trying a DELETE or a Student accessing another profile): Denied
        return False