from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, TestViewSet, QuestionViewSet,
    AssignmentViewSet, StudentAttemptViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'tests', TestViewSet, basename='test')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'assignments', AssignmentViewSet, basename='assignment')
router.register(r'attempts', StudentAttemptViewSet, basename='attempt')

urlpatterns = [
    path('', include(router.urls)),
]