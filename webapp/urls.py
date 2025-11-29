from django.urls import path
from . import views

app_name = 'webapp'

urlpatterns = [
    # Landing & Auth
    path('', views.landing_page, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Teacher - Test Creation Choice
    path('tests/create/', views.create_test_choice, name='create_test'),
    path('tests/create/choice/', views.create_test_choice, name='create_test_choice'),

    # Teacher - AI Test Creation
    path('tests/create/ai/', views.create_test_ai_view, name='create_test_ai'),
    path('tests/confirm/', views.confirm_test_view, name='confirm_test'),
    path('tests/generate/', views.generate_test_view, name='generate_test'),

    # Teacher - Manual Test Creation (NEW)
    path('tests/create/manual/', views.create_test_manual_view, name='create_test_manual'),

    # Teacher - Test Management
    path('tests/', views.test_list_view, name='test_list'),
    path('tests/<int:test_id>/', views.test_detail_view, name='test_detail'),
    path('tests/<int:test_id>/publish/', views.publish_test_view, name='publish_test'),
    path('tests/<int:test_id>/results/', views.test_results_view, name='test_results'),

    # Student - NEW Test Taking Flow
    path('test/<str:token>/', views.take_test_new_view, name='take_test'),

    # Student - History
    path('history/', views.student_history_view, name='student_history'),
]