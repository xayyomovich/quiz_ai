from rest_framework import serializers
from .models import Test, Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'test', 'question_text', 'options', 'correct_option']

    def validate(self, data):
        options = data.get('options', [])
        correct_option = data.get('correct_option')

        if not isinstance(options, list) or len(options) < 2:
            raise serializers.ValidationError("Options must be a list with at least 2 items.")
        if correct_option is None or correct_option >= len(options):
            raise serializers.ValidationError("Correct option index is out of range.")
        return data


class TestSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = ['id', 'title', 'description', 'questions']
