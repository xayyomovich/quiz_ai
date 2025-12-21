from django.contrib import admin
from .models import User, Test, Question, Assignment, StudentAttempt, StudentAnswer, Result


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'first_name', 'last_name', 'role', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'username']
    list_filter = ['role', 'created_at', 'email_verified']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'teacher', 'difficulty', 'topic', 'created_at']
    search_fields = ['title', 'topic', 'teacher__email', 'teacher__first_name', 'teacher__last_name']
    list_filter = ['difficulty', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'test', 'question_text_short', 'question_type', 'points', 'order']
    search_fields = ['question_text']
    list_filter = ['test', 'question_type']
    ordering = ['test', 'order']

    def question_text_short(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text

    question_text_short.short_description = 'Question'


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'test', 'access_token', 'is_active', 'allow_retakes', 'max_attempts', 'created_at']
    search_fields = ['access_token', 'test__title']
    list_filter = ['is_active', 'allow_retakes', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['access_token', 'created_at']


@admin.register(StudentAttempt)
class StudentAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'student_name', 'assignment', 'attempt_number', 'auto_score', 'total_possible', 'percentage',
                    'is_completed', 'started_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'assignment__test__title']
    list_filter = ['is_completed', 'started_at']
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'finished_at']

    def student_name(self, obj):
        return obj.student.get_full_name()

    student_name.short_description = 'Student'

    def percentage(self, obj):
        return f"{obj.calculate_percentage()}%"

    percentage.short_description = 'Score %'


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'attempt', 'question_short', 'selected_option', 'is_correct', 'points_earned', 'answered_at']
    search_fields = ['attempt__student__email', 'question__question_text']
    list_filter = ['is_correct', 'answered_at']
    ordering = ['-answered_at']
    readonly_fields = ['answered_at']

    def question_short(self, obj):
        return obj.question.question_text[:30] + "..." if len(
            obj.question.question_text) > 30 else obj.question.question_text

    question_short.short_description = 'Question'


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_name', 'test', 'score', 'total', 'percentage', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'test__title']
    list_filter = ['created_at']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def user_name(self, obj):
        return obj.user.get_full_name()

    user_name.short_description = 'User'

    def percentage(self, obj):
        return f"{round((obj.score / obj.total) * 100, 2)}%" if obj.total > 0 else "0%"

    percentage.short_description = 'Score %'