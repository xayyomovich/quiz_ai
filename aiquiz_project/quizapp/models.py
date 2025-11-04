from django.db import models
import uuid
import secrets
import string


class User(models.Model):
    """User model for both teachers and students"""
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(
        max_length=10,
        choices=[('student', 'Student'), ('teacher', 'Teacher')],
        default='student'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class Test(models.Model):
    """Test created by teacher via LLM"""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    # Store teacher's original prompt and LLM response for auditability
    teacher_prompt = models.TextField(help_text="Original teacher request")
    llm_response = models.JSONField(null=True, blank=True, help_text="Raw LLM JSON response")

    # Metadata
    difficulty = models.CharField(max_length=50, null=True, blank=True)
    topic = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', '-created_at']),
        ]

    def __str__(self):
        return self.title


class Question(models.Model):
    """Questions belonging to a test"""
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('truefalse', 'True/False'),
    ]

    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='mcq')

    # Options stored as JSON array: ["Option A", "Option B", "Option C", "Option D"]
    options = models.JSONField()

    # Index of correct answer (0-based)
    correct_option = models.IntegerField()

    # Points for this question
    points = models.IntegerField(default=1)

    # Order in the test
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['test', 'order']),
        ]

    def __str__(self):
        return f"{self.test.title}: {self.question_text[:50]}..."


class Assignment(models.Model):
    """Published test that can be shared with students via link/QR"""
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='assignments')

    # Unique token for sharing (e.g., "abc123xyz")
    access_token = models.CharField(max_length=20, unique=True, db_index=True)

    # Optional: time-based access control
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)

    # Allow retakes
    allow_retakes = models.BooleanField(default=True)
    max_attempts = models.IntegerField(default=3, help_text="0 means unlimited")

    # Show results immediately or not
    show_results_immediately = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['access_token']),
            models.Index(fields=['test', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = self.generate_token()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token(length=8):
        """Generate a random alphanumeric token"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    def get_bot_link(self, bot_username):
        """Generate deep link for Telegram bot"""
        return f"https://t.me/{bot_username}?start=test_{self.access_token}"

    def __str__(self):
        return f"Assignment: {self.test.title} ({self.access_token})"


class StudentAttempt(models.Model):
    """Individual attempt by a student on an assignment"""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts')

    attempt_number = models.IntegerField(default=1)

    # Scores
    auto_score = models.IntegerField(default=0, help_text="Auto-graded score")
    total_possible = models.IntegerField(default=0, help_text="Total possible points")

    # Status
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    # Current question index (for tracking progress)
    current_question_index = models.IntegerField(default=0)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student', '-started_at']),
            models.Index(fields=['assignment', 'is_completed']),
        ]
        unique_together = ['assignment', 'student', 'attempt_number']

    def __str__(self):
        return f"{self.student.full_name} - {self.assignment.test.title} (Attempt {self.attempt_number})"

    def calculate_percentage(self):
        """Calculate percentage score"""
        if self.total_possible == 0:
            return 0
        return round((self.auto_score / self.total_possible) * 100, 2)


class StudentAnswer(models.Model):
    """Individual answer submitted by student"""
    attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    # Student's selected option index (for MCQ)
    selected_option = models.IntegerField(null=True, blank=True)

    # For future: text answers
    text_answer = models.TextField(null=True, blank=True)

    # Grading
    is_correct = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['answered_at']
        indexes = [
            models.Index(fields=['attempt', 'question']),
        ]
        unique_together = ['attempt', 'question']

    def __str__(self):
        return f"Answer: {self.question.question_text[:30]}... by {self.attempt.student.full_name}"

    def auto_grade(self):
        """Automatically grade the answer for MCQ"""
        if self.question.question_type in ['mcq', 'truefalse']:
            if self.selected_option == self.question.correct_option:
                self.is_correct = True
                self.points_earned = self.question.points
            else:
                self.is_correct = False
                self.points_earned = 0
            self.save()


class Result(models.Model):
    """Legacy model - keeping for backward compatibility, but StudentAttempt is preferred"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    score = models.IntegerField()
    total = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.test.title}: {self.score}/{self.total}"