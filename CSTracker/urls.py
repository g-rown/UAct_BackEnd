from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views 

router = DefaultRouter()
router.register(r'programs', views.ProgramViewSet, basename='program') 
router.register(r'students', views.StudentProfileViewSet, basename='student')
router.register(
    r'accreditation', 
    views.ServiceAccreditationViewSet, 
    basename='accreditation'
)

urlpatterns = [
   
    path('login/', views.login_user, name='login_user'),
    path('signup/', views.student_signup, name='student_signup'),
    path('applications/', views.program_apply, name='program_apply'),
    path('service-history/', views.service_history, name='service_history'),
    path('', include(router.urls)), 
]