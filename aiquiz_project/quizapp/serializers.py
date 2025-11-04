from rest_framework import serializers
from .models import User, Test, Question, Assignment, StudentAttempt, StudentAnswer, Result


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = ['id', 'telegram_id', 'username', 'full_name', 'role', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for Question model"""

    class Meta:
        model = Question
        fields = [
            'id', 'test', 'question_text', 'question_type',
            'options', 'correct_option', 'points', 'order'
        ]

    def validate(self, data):
        options = data.get('options', [])
        correct_option = data.get('correct_option')

        # Validate options is a list with at least 2 items
        if not isinstance(options, list) or len(options) < 2:
            raise serializers.ValidationError("Options must be a list with at least 2 items.")

        # Validate correct_option index
        if correct_option is None or correct_option >= len(options) or correct_option < 0:
            raise serializers.ValidationError("Correct option index is out of range.")

        return data


class QuestionWithoutAnswerSerializer(serializers.ModelSerializer):
    """Question serializer WITHOUT correct answer (for students taking test)"""

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'question_type', 'options', 'points', 'order']


class TestSerializer(serializers.ModelSerializer):
    """Full test serializer with questions"""
    questions = QuestionSerializer(many=True, read_only=True)
    teacher_name = serializers.CharField(source='teacher.full_name', read_only=True)
    question_count = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'teacher', 'teacher_name',
            'teacher_prompt', 'llm_response', 'difficulty', 'topic',
            'questions', 'question_count', 'total_points', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'teacher_name']

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_total_points(self, obj):
        return sum(q.points for q in obj.questions.all())


class TestListSerializer(serializers.ModelSerializer):
    """Lightweight test serializer for listings (no questions)"""
    teacher_name = serializers.CharField(source='teacher.full_name', read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'teacher_name',
            'difficulty', 'topic', 'question_count', 'created_at'
        ]

    def get_question_count(self, obj):
        return obj.questions.count()


class AssignmentSerializer(serializers.ModelSerializer):
    """Serializer for Assignment model"""
    test_title = serializers.CharField(source='test.title', read_only=True)
    test_details = TestListSerializer(source='test', read_only=True)
    bot_link = serializers.SerializerMethodField()
    total_attempts = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'test', 'test_title', 'test_details', 'access_token',
            'opens_at', 'closes_at', 'allow_retakes', 'max_attempts',
            'show_results_immediately', 'show_correct_answers',
            'created_at', 'is_active', 'bot_link', 'total_attempts'
        ]
        read_only_fields = ['id', 'access_token', 'created_at']

    def get_bot_link(self, obj):
        # You'll need to set BOT_USERNAME in your settings
        from django.conf import settings
        bot_username = getattr(settings, 'BOT_USERNAME', 'YourBot')
        return obj.get_bot_link(bot_username)

    def get_total_attempts(self, obj):
        return obj.attempts.count()


class StudentAnswerSerializer(serializers.ModelSerializer):
    """Serializer for StudentAnswer"""
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    correct_option = serializers.IntegerField(source='question.correct_option', read_only=True)

    class Meta:
        model = StudentAnswer
        fields = [
            'id', 'attempt', 'question', 'question_text',
            'selected_option', 'text_answer', 'is_correct',
            'points_earned', 'correct_option', 'answered_at'
        ]
        read_only_fields = ['id', 'is_correct', 'points_earned', 'answered_at']


class StudentAnswerCreateSerializer(serializers.ModelSerializer):
    """Serializer for submitting an answer"""

    class Meta:
        model = StudentAnswer
        fields = ['attempt', 'question', 'selected_option', 'text_answer']

    def create(self, validated_data):
        answer = StudentAnswer.objects.create(**validated_data)
        answer.auto_grade()  # Auto-grade on creation
        return answer


class StudentAttemptSerializer(serializers.ModelSerializer):
    """Full attempt serializer with all answers"""
    answers = StudentAnswerSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    test_title = serializers.CharField(source='assignment.test.title', read_only=True)
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = StudentAttempt
        fields = [
            'id', 'assignment', 'student', 'student_name', 'test_title',
            'attempt_number', 'auto_score', 'total_possible', 'percentage',
            'started_at', 'finished_at', 'is_completed',
            'current_question_index', 'answers'
        ]
        read_only_fields = ['id', 'started_at', 'finished_at', 'auto_score']

    def get_percentage(self, obj):
        return obj.calculate_percentage()


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    """Serializer for leaderboard entries"""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_username = serializers.CharField(source='student.username', read_only=True)
    percentage = serializers.SerializerMethodField()
    rank = serializers.IntegerField(read_only=True)  # Will be added in view

    class Meta:
        model = StudentAttempt
        fields = [
            'id', 'student_name', 'student_username', 'attempt_number',
            'auto_score', 'total_possible', 'percentage', 'finished_at', 'rank'
        ]

    def get_percentage(self, obj):
        return obj.calculate_percentage()


class TestGenerationRequestSerializer(serializers.Serializer):
    """Serializer for LLM test generation request"""
    teacher_id = serializers.IntegerField()
    topic = serializers.CharField(max_length=255)
    question_count = serializers.IntegerField(min_value=1, max_value=50, default=10)
    difficulty = serializers.ChoiceField(
        choices=['easy', 'intermediate', 'hard'],
        default='intermediate'
    )
    options_per_question = serializers.IntegerField(min_value=2, max_value=6, default=4)
    language = serializers.ChoiceField(
        choices=['english', 'uzbek', 'russian'],
        default='english'
    )


class TestConfirmationRequestSerializer(serializers.Serializer):
    """Serializer for test confirmation request (Step 1)"""
    teacher_id = serializers.IntegerField()
    prompt = serializers.CharField(max_length=1000, required=False)

    # Optional: For context-aware parsing (editing)
    context = serializers.JSONField(required=False, allow_null=True)


class TestConfirmationResponseSerializer(serializers.Serializer):
    """Serializer for test confirmation response (Step 1)"""
    topic = serializers.CharField()
    question_count = serializers.IntegerField()
    difficulty = serializers.ChoiceField(choices=['easy', 'intermediate', 'hard'])
    language = serializers.ChoiceField(choices=['english', 'uzbek', 'russian'])
    description = serializers.CharField()
    message = serializers.CharField(default="Please confirm to generate test")


class TestGenerationConfirmedRequestSerializer(serializers.Serializer):
    """Serializer for generating test with confirmed params (Step 2)"""
    teacher_id = serializers.IntegerField()
    topic = serializers.CharField(max_length=255)
    question_count = serializers.IntegerField(min_value=1, max_value=50)
    difficulty = serializers.ChoiceField(choices=['easy', 'intermediate', 'hard'])
    language = serializers.ChoiceField(choices=['english', 'uzbek', 'russian'])
    description = serializers.CharField(max_length=500)


class TestGenerationResponseSerializer(serializers.Serializer):
    """Serializer for LLM test generation response"""
    test_id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    question_count = serializers.IntegerField()
    message = serializers.CharField()


class SubmitAnswerRequestSerializer(serializers.Serializer):
    """Serializer for submitting a single answer during test"""
    # attempt_id = serializers.IntegerField()
    question_id = serializers.IntegerField()
    selected_option = serializers.IntegerField(min_value=0, required=False)
    text_answer = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        # At least one answer type must be provided
        if 'selected_option' not in data and not data.get('text_answer'):
            raise serializers.ValidationError(
                "Either selected_option or text_answer must be provided"
            )
        return data


class FinishAttemptResponseSerializer(serializers.Serializer):
    """Response after finishing an attempt"""
    attempt_id = serializers.IntegerField()
    score = serializers.IntegerField()
    total = serializers.IntegerField()
    percentage = serializers.FloatField()
    rank = serializers.IntegerField()
    total_students = serializers.IntegerField()
    message = serializers.CharField()


class ResultSerializer(serializers.ModelSerializer):
    """Legacy Result serializer"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    test_title = serializers.CharField(source='test.title', read_only=True)

    class Meta:
        model = Result
        fields = ['id', 'user', 'user_name', 'test', 'test_title', 'score', 'total', 'created_at']
        read_only_fields = ['id', 'created_at']