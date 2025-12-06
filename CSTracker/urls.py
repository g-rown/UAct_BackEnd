from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    login_user,
    ProgramViewSet,
    StudentProfileViewSet,
    ProgramApplicationViewSet,
    ServiceLogViewSet,
    signup_student
)

router = DefaultRouter()
router.register('programs', ProgramViewSet)
router.register('students', StudentProfileViewSet)
router.register('applications', ProgramApplicationViewSet)
router.register('logs', ServiceLogViewSet)

urlpatterns = [
    path('login/', login_user, name='login'),
    path('register/', signup_student, name='register_student'),
    path('', include(router.urls)),
]

