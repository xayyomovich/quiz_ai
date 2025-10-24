from django.db import models

class User(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=[('student', 'Student'), ('teacher', 'Teacher')], default='student')
    created_at = models.DateTimeField(auto_now_add=True)

class Test(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField()
    correct_option = models.IntegerField()  # index of correct answer (0–3)

    def __str__(self):
        return f"{self.test.title}: {self.question_text[:50]}"

class Result(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    score = models.IntegerField()
    total = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
