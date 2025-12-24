# quizapp/models.py - UPDATED VERSION

from django.db import models
from django.contrib.auth.models import AbstractUser
import secrets
import string


class User(AbstractUser):
    """Extended User model for web app"""
    email = models.EmailField(unique=True, blank=False)

    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='student'
    )

    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)

    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Test(models.Model):
    """Test created by teacher via LLM or manually"""
    TEST_CREATION_METHODS = [
        ('ai', 'AI Generated'),
        ('manual', 'Manual Input'),
    ]

    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    # Creation method
    creation_method = models.CharField(
        max_length=10,
        choices=TEST_CREATION_METHODS,
        default='ai'
    )

    # Store teacher's original prompt and LLM response (for AI tests)
    teacher_prompt = models.TextField(help_text="Original teacher request", blank=True)
    llm_response = models.JSONField(null=True, blank=True, help_text="Raw LLM JSON response")

    # Metadata
    difficulty = models.CharField(max_length=50, null=True, blank=True)
    topic = models.CharField(max_length=255, null=True, blank=True)

    # NEW: Timer field (in minutes, optional)
    timer_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time limit in minutes (leave empty for no limit)"
    )

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
    """Published test that can be shared with students via link"""
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

    def get_web_link(self, domain='localhost:8000'):
        """Generate web link for test"""
        return f"http://{domain}/test/{self.access_token}"

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

    # Current question index (for tracking progress) - NOT USED in new flow
    current_question_index = models.IntegerField(default=0)

    # NEW: Anti-Cheat Fields
    is_terminated = models.BooleanField(default=False, help_text="Test terminated due to cheating")
    termination_reason = models.CharField(max_length=255, blank=True, help_text="Reason for termination")
    terminated_at = models.DateTimeField(null=True, blank=True)
    questions_answered = models.IntegerField(default=0, help_text="Number of questions answered before termination")

    # NEW: Timer Fields
    time_taken_seconds = models.IntegerField(null=True, blank=True, help_text="Time taken to complete in seconds")

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student', '-started_at']),
            models.Index(fields=['assignment', 'is_completed']),
        ]
        unique_together = ['assignment', 'student', 'attempt_number']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.assignment.test.title} (Attempt {self.attempt_number})"

    def calculate_percentage(self):
        """Calculate percentage score"""
        if self.total_possible == 0:
            return 0
        return round((self.auto_score / self.total_possible) * 100, 2)

    def get_status_display(self):
        """Get human-readable status"""
        if self.is_terminated:
            return f"⚠️ Terminated: {self.termination_reason}"
        elif self.is_completed:
            return "✅ Completed"
        else:
            return "🔄 In Progress"


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
        ordering = ['question__order']  # Order by question order
        indexes = [
            models.Index(fields=['attempt', 'question']),
        ]
        unique_together = ['attempt', 'question']

    def __str__(self):
        return f"Answer: {self.question.question_text[:30]}... by {self.attempt.student.get_full_name()}"

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
    """Legacy model - keeping for backward compatibility"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    score = models.IntegerField()
    total = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.test.title}: {self.score}/{self.total}"


# ADD THESE NEW MODELS AT THE END OF quizapp/models.py

class GroupTest(models.Model):
    """Static group test (Group-1, Group-2, etc.)"""
    group_number = models.IntegerField(unique=True, help_text="1-10 for Group-1 to Group-10")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='group_tests')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_tests_created')

    # Access
    access_token = models.CharField(max_length=20, unique=True, db_index=True)

    # Settings
    timer_minutes = models.IntegerField(help_text="Time limit for the test")
    max_group_size = models.IntegerField(default=10, help_text="Maximum students per group")

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group_number']
        unique_together = ['teacher', 'group_number']

    def __str__(self):
        return f"Group-{self.group_number}: {self.test.title}"

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = Assignment.generate_token()
        super().save(*args, **kwargs)

    def get_web_link(self, domain):
        return f"http://{domain}/group-test/{self.access_token}/"


class GroupAttempt(models.Model):
    """One attempt by a group of students"""
    group_test = models.ForeignKey(GroupTest, on_delete=models.CASCADE, related_name='attempts')

    # Status
    is_started = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)

    # Scores
    group_score_percentage = models.FloatField(default=0.0, help_text="Group answer score 0-100%")
    total_possible = models.IntegerField(default=0)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Attempt for {self.group_test} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class GroupMember(models.Model):
    """Students who joined a group attempt"""
    group_attempt = models.ForeignKey(GroupAttempt, on_delete=models.CASCADE, related_name='members')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')

    # Individual score
    individual_score_percentage = models.FloatField(default=0.0, help_text="Individual contribution 0-100%")

    # Status
    has_submitted_all_opinions = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group_attempt', 'student']
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.student.get_full_name()} in {self.group_attempt}"


class IndividualOpinion(models.Model):
    """Each student's individual opinion for a question"""
    group_attempt = models.ForeignKey(GroupAttempt, on_delete=models.CASCADE, related_name='opinions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)

    # Opinion
    opinion_text = models.TextField(help_text="Student's individual thinking")

    # AI Assessment (0-100%)
    score_percentage = models.FloatField(default=0.0, help_text="AI-evaluated quality 0-100%")
    ai_feedback = models.TextField(blank=True, help_text="AI's brief feedback")

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group_attempt', 'question', 'student']
        ordering = ['question__order', 'submitted_at']

    def __str__(self):
        return f"{self.student.get_full_name()}'s opinion on Q{self.question.order + 1}"


class GroupAnswer(models.Model):
    """Final group answer for a question"""
    group_attempt = models.ForeignKey(GroupAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    # Answer - supports BOTH multiple choice AND text
    selected_option = models.IntegerField(default=0, help_text="For MCQ: Group's selected option index")
    text_answer = models.TextField(blank=True, null=True, help_text="For open-ended: Group's text answer")

    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Who clicked submit")

    # Grading
    is_correct = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group_attempt', 'question']
        ordering = ['question__order']

    def __str__(self):
        return f"Group answer for Q{self.question.order + 1}"

    def auto_grade(self):
        """Grade the group answer"""
        if self.question.question_type in ['mcq', 'truefalse']:
            # Multiple choice grading
            if self.selected_option == self.question.correct_option:
                self.is_correct = True
                self.points_earned = self.question.points
            else:
                self.is_correct = False
                self.points_earned = 0
        else:
            # Text-based: AI will grade this later
            self.points_earned = 0
            self.is_correct = False

        self.save()