from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Max, Q
from django.utils import timezone

from .models import (
    User, Test, Question, Assignment,
    StudentAttempt, StudentAnswer, Result
)
from .serializers import (
    UserSerializer, TestSerializer, TestListSerializer,
    QuestionSerializer, QuestionWithoutAnswerSerializer,
    AssignmentSerializer, StudentAttemptSerializer,
    StudentAnswerSerializer, StudentAnswerCreateSerializer,
    LeaderboardEntrySerializer, TestGenerationRequestSerializer,
    TestGenerationResponseSerializer, SubmitAnswerRequestSerializer,
    FinishAttemptResponseSerializer, ResultSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User management"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'telegram_id'

    @action(detail=False, methods=['post'])
    def get_or_create(self, request):
        """Get or create user by telegram_id"""
        telegram_id = request.data.get('telegram_id')
        full_name = request.data.get('full_name')
        username = request.data.get('username')
        role = request.data.get('role', 'student')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user, created = User.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'full_name': full_name or 'Unknown',
                'username': username,
                'role': role
            }
        )

        # Update name if changed
        if not created and full_name:
            user.full_name = full_name
            user.username = username
            user.save()

        serializer = self.get_serializer(user)
        return Response({
            'user': serializer.data,
            'created': created
        })


class TestViewSet(viewsets.ModelViewSet):
    """ViewSet for Test management"""
    queryset = Test.objects.all()
    serializer_class = TestSerializer

    def get_serializer_class(self):
        """Use lightweight serializer for list action"""
        if self.action == 'list':
            return TestListSerializer
        return TestSerializer

    def get_queryset(self):
        """Filter tests by teacher if specified"""
        queryset = Test.objects.all()
        teacher_id = self.request.query_params.get('teacher_id')

        if teacher_id:
            queryset = queryset.filter(teacher__telegram_id=teacher_id)

        return queryset.select_related('teacher').prefetch_related('questions')

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        """
        Step 1: Parse user input and return confirmation parameters

        Payload:
        {
            "teacher_id": 123456789,
            "prompt": "biology test",
            "context": {...}  // Optional: previous params for editing
        }

        Response:
        {
            "topic": "biology",
            "question_count": 10,
            "difficulty": "easy",
            "language": "english",
            "description": "Generate 10 easy biology questions in English",
            "message": "Please confirm to generate test"
        }
        """
        from .llm_service import confirm_test_parameters
        from .serializers import TestConfirmationRequestSerializer, TestConfirmationResponseSerializer

        serializer = TestConfirmationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        teacher_id = data['teacher_id']
        user_input = data.get('prompt', '')
        context = data.get('context')

        if not user_input and not context:
            return Response(
                {'error': 'Either prompt or context is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify teacher exists
        try:
            teacher = User.objects.get(telegram_id=teacher_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Teacher not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Call Flash-8B for confirmation
        try:
            params = confirm_test_parameters(user_input, context)

            response_serializer = TestConfirmationResponseSerializer(data={
                **params,
                'message': 'Please confirm to generate test'
            })
            response_serializer.is_valid(raise_exception=True)

            return Response(response_serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Failed to parse input: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Step 2: Generate test with confirmed parameters

        Payload:
        {
            "teacher_id": 123456789,
            "topic": "biology",
            "question_count": 10,
            "difficulty": "easy",
            "language": "english",
            "description": "Generate 10 easy biology questions in English"
        }

        Response:
        {
            "test_id": 42,
            "title": "Biology Fundamentals Quiz",
            "description": "...",
            "question_count": 10,
            "message": "Test generated successfully!"
        }
        """
        from .llm_service import generate_confirmed_test
        from .serializers import TestGenerationConfirmedRequestSerializer

        serializer = TestGenerationConfirmedRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        teacher_id = data.pop('teacher_id')

        # Get teacher
        try:
            teacher = User.objects.get(telegram_id=teacher_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Teacher not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate test with Flash
        try:
            test = generate_confirmed_test(teacher, data)

            response_serializer = TestGenerationResponseSerializer(data={
                'test_id': test.id,
                'title': test.title,
                'description': test.description,
                'question_count': test.questions.count(),
                'message': 'Test generated successfully!'
            })
            response_serializer.is_valid()

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Failed to generate test: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish a test as an Assignment
        Optional payload:
        {
            "allow_retakes": true,
            "max_attempts": 3,
            "show_results_immediately": true,
            "show_correct_answers": true
        }
        """
        test = self.get_object()

        # Create assignment
        assignment = Assignment.objects.create(
            test=test,
            allow_retakes=request.data.get('allow_retakes', True),
            max_attempts=request.data.get('max_attempts', 3),
            show_results_immediately=request.data.get('show_results_immediately', True),
            show_correct_answers=request.data.get('show_correct_answers', True),
        )

        serializer = AssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get detailed statistics for a test

        Returns:
        {
            "test": {...},
            "total_students": 15,
            "completed_attempts": 12,
            "in_progress_attempts": 3,
            "average_score": 7.2,
            "average_percentage": 72.0,
            "pass_rate": 75.0,
            "passed_count": 9,
            "failed_count": 3,
            "highest_score": 10,
            "lowest_score": 3,
            "top_students": [...]
        }
        """
        test = self.get_object()

        # Get all assignments for this test
        assignments = Assignment.objects.filter(test=test)

        if not assignments.exists():
            return Response({
                'error': 'No assignments found for this test',
                'detail': 'Test has not been published yet'
            }, status=status.HTTP_404_NOT_FOUND)

        # Get all attempts across all assignments
        all_attempts = StudentAttempt.objects.filter(
            assignment__in=assignments
        ).select_related('student', 'assignment')

        # Completed attempts only
        completed_attempts = all_attempts.filter(is_completed=True)
        in_progress_attempts = all_attempts.filter(is_completed=False)

        # Get unique students (best attempt per student)
        from django.db.models import Max
        student_best_scores = {}

        for attempt in completed_attempts:
            student_id = attempt.student.id
            if student_id not in student_best_scores or attempt.auto_score > student_best_scores[student_id]['score']:
                student_best_scores[student_id] = {
                    'student': attempt.student,
                    'attempt': attempt,
                    'score': attempt.auto_score,
                    'total': attempt.total_possible,
                    'percentage': attempt.calculate_percentage(),
                    'finished_at': attempt.finished_at
                }

        unique_students = len(student_best_scores)

        if unique_students == 0:
            return Response({
                'test': TestListSerializer(test).data,
                'total_students': 0,
                'completed_attempts': 0,
                'in_progress_attempts': in_progress_attempts.count(),
                'average_score': 0,
                'average_percentage': 0,
                'pass_rate': 0,
                'passed_count': 0,
                'failed_count': 0,
                'highest_score': 0,
                'lowest_score': 0,
                'top_students': [],
                'in_progress_students': []
            })

        # Calculate statistics
        scores = [s['score'] for s in student_best_scores.values()]
        totals = [s['total'] for s in student_best_scores.values()]
        percentages = [s['percentage'] for s in student_best_scores.values()]

        average_score = sum(scores) / len(scores)
        average_percentage = sum(percentages) / len(percentages)

        # Pass threshold: 60%
        PASS_THRESHOLD = 60.0
        passed = [s for s in student_best_scores.values() if s['percentage'] >= PASS_THRESHOLD]
        failed = [s for s in student_best_scores.values() if s['percentage'] < PASS_THRESHOLD]

        pass_rate = (len(passed) / unique_students) * 100 if unique_students > 0 else 0

        highest_score = max(scores)
        lowest_score = min(scores)

        # Sort by score (descending) and get top 20
        sorted_students = sorted(
            student_best_scores.values(),
            key=lambda x: (-x['score'], x['finished_at'])  # Higher score first, earlier completion as tiebreaker
        )[:20]

        # Format top students
        top_students_data = []
        for rank, student_data in enumerate(sorted_students, 1):
            attempt = student_data['attempt']
            top_students_data.append({
                'rank': rank,
                'student_id': student_data['student'].id,
                'student_name': student_data['student'].full_name,
                'student_username': student_data['student'].username,
                'score': student_data['score'],
                'total': student_data['total'],
                'percentage': student_data['percentage'],
                'passed': student_data['percentage'] >= PASS_THRESHOLD,
                'finished_at': student_data['finished_at'].isoformat() if student_data['finished_at'] else None,
                'attempt_number': attempt.attempt_number
            })

        # In-progress students
        in_progress_students_data = []
        for attempt in in_progress_attempts[:10]:  # Show up to 10
            in_progress_students_data.append({
                'student_name': attempt.student.full_name,
                'started_at': attempt.started_at.isoformat(),
                'current_question': attempt.current_question_index + 1,
                'total_questions': attempt.total_possible
            })

        return Response({
            'test': TestListSerializer(test).data,
            'total_students': unique_students,
            'completed_attempts': completed_attempts.count(),
            'in_progress_attempts': in_progress_attempts.count(),
            'average_score': round(average_score, 2),
            'average_percentage': round(average_percentage, 2),
            'pass_rate': round(pass_rate, 2),
            'pass_threshold': PASS_THRESHOLD,
            'passed_count': len(passed),
            'failed_count': len(failed),
            'highest_score': highest_score,
            'lowest_score': lowest_score,
            'total_possible': totals[0] if totals else 0,
            'top_students': top_students_data,
            'in_progress_students': in_progress_students_data
        })

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """Preview test (for teachers)"""
        test = self.get_object()
        serializer = TestSerializer(test)
        return Response(serializer.data)


class AssignmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Assignment management"""
    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer
    lookup_field = 'access_token'

    def get_queryset(self):
        """Filter by test or active status"""
        queryset = Assignment.objects.all()
        test_id = self.request.query_params.get('test_id')
        is_active = self.request.query_params.get('is_active')

        if test_id:
            queryset = queryset.filter(test_id=test_id)
        if is_active:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.select_related('test', 'test__teacher')

    @action(detail=True, methods=['post'])
    def start_attempt(self, request, access_token=None):
        """
        Start a new attempt for a student
        Payload: {"telegram_id": 123456789}
        """
        assignment = self.get_object()
        telegram_id = request.data.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required', 'detail': 'Missing telegram_id in request body'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create student
        try:
            student = User.objects.get(telegram_id=telegram_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Student not found. Please start the bot first.',
                 'detail': f'No user with telegram_id={telegram_id}'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if student can take the test
        if not assignment.is_active:
            return Response(
                {'error': 'This test is no longer active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check attempt limits
        existing_attempts = StudentAttempt.objects.filter(
            assignment=assignment,
            student=student
        ).count()

        if not assignment.allow_retakes and existing_attempts > 0:
            return Response(
                {'error': 'Retakes are not allowed for this test'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if assignment.max_attempts > 0 and existing_attempts >= assignment.max_attempts:
            return Response(
                {'error': f'Maximum attempts ({assignment.max_attempts}) reached'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate total possible points
        total_points = sum(q.points for q in assignment.test.questions.all())

        # Create new attempt
        attempt = StudentAttempt.objects.create(
            assignment=assignment,
            student=student,
            attempt_number=existing_attempts + 1,
            total_possible=total_points
        )

        # Return first question
        questions = list(assignment.test.questions.all().order_by('order'))
        if not questions:
            return Response(
                {'error': 'This test has no questions'},
                status=status.HTTP_400_BAD_REQUEST
            )

        first_question = QuestionWithoutAnswerSerializer(questions[0]).data

        return Response({
            'attempt_id': attempt.id,
            'total_questions': len(questions),
            'current_question': first_question,
            'question_index': 0
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def leaderboard(self, request, access_token=None):
        """Get leaderboard for this assignment"""
        assignment = self.get_object()

        # Get best attempt for each student
        attempts = StudentAttempt.objects.filter(
            assignment=assignment,
            is_completed=True
        ).select_related('student')

        # Group by student and get their best score
        from django.db.models import Max
        best_attempts = []
        student_best = {}

        for attempt in attempts:
            student_id = attempt.student.id
            if student_id not in student_best or attempt.auto_score > student_best[student_id].auto_score:
                student_best[student_id] = attempt

        best_attempts = list(student_best.values())

        # Sort by score (descending)
        best_attempts.sort(key=lambda x: x.auto_score, reverse=True)

        # Add rank
        for rank, attempt in enumerate(best_attempts, 1):
            attempt.rank = rank

        serializer = LeaderboardEntrySerializer(best_attempts, many=True)
        return Response({
            'assignment': AssignmentSerializer(assignment).data,
            'leaderboard': serializer.data,
            'total_participants': len(best_attempts)
        })


class StudentAttemptViewSet(viewsets.ModelViewSet):
    """ViewSet for StudentAttempt management"""
    queryset = StudentAttempt.objects.all()
    serializer_class = StudentAttemptSerializer

    def get_queryset(self):
        """Filter by student or assignment"""
        queryset = StudentAttempt.objects.all()
        student_telegram_id = self.request.query_params.get('student_telegram_id')
        assignment_id = self.request.query_params.get('assignment_id')

        if student_telegram_id:
            queryset = queryset.filter(student__telegram_id=student_telegram_id)
        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)

        return queryset.select_related('student', 'assignment', 'assignment__test')

    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        """
        Submit an answer for a question
        Payload: {
            "question_id": 123,
            "selected_option": 2
        }
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Submit answer called: attempt_id={pk}, data={request.data}")

        attempt = self.get_object()
        logger.info(f"Attempt found: {attempt.id}, completed={attempt.is_completed}")

        if attempt.is_completed:
            error_msg = {'error': 'This attempt is already completed',
                         'detail': 'Cannot submit answer to completed attempt'}
            logger.error(f"Attempt already completed: {error_msg}")
            return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubmitAnswerRequestSerializer(data=request.data)
        if not serializer.is_valid():
            error_msg = {'error': 'Invalid request data', 'detail': serializer.errors}
            logger.error(f"Validation failed: {error_msg}")
            return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)

        question_id = serializer.validated_data['question_id']
        selected_option = serializer.validated_data.get('selected_option')
        text_answer = serializer.validated_data.get('text_answer')

        logger.info(f"Validated data: question_id={question_id}, selected_option={selected_option}")

        # Get question
        try:
            question = Question.objects.get(
                id=question_id,
                test=attempt.assignment.test
            )
            logger.info(f"Question found: {question.id}")
        except Question.DoesNotExist:
            error_msg = {'error': 'Question not found in this test',
                         'detail': f'Question {question_id} not in test {attempt.assignment.test.id}'}
            logger.error(f"Question not found: {error_msg}")
            return Response(error_msg, status=status.HTTP_404_NOT_FOUND)

        # Create or update answer
        answer, created = StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_option': selected_option,
                'text_answer': text_answer
            }
        )
        answer.auto_grade()

        # Update attempt's current question index
        attempt.current_question_index += 1
        attempt.save()

        # Get next question
        questions = list(attempt.assignment.test.questions.all().order_by('order'))
        if attempt.current_question_index < len(questions):
            next_question = QuestionWithoutAnswerSerializer(
                questions[attempt.current_question_index]
            ).data

            return Response({
                'answer_saved': True,
                'is_correct': answer.is_correct,
                'points_earned': answer.points_earned,
                'next_question': next_question,
                'question_index': attempt.current_question_index,
                'total_questions': len(questions)
            })
        else:
            # No more questions - test is done
            return Response({
                'answer_saved': True,
                'is_correct': answer.is_correct,
                'points_earned': answer.points_earned,
                'test_completed': True,
                'message': 'All questions answered! Call finish endpoint to see results.'
            })

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        """Finish the attempt and calculate final score"""
        attempt = self.get_object()

        if attempt.is_completed:
            return Response(
                {'error': 'This attempt is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate total score
        total_score = sum(
            answer.points_earned
            for answer in attempt.answers.all()
        )

        attempt.auto_score = total_score
        attempt.is_completed = True
        attempt.finished_at = timezone.now()
        attempt.save()

        # Calculate rank
        better_attempts = StudentAttempt.objects.filter(
            assignment=attempt.assignment,
            is_completed=True,
            auto_score__gt=attempt.auto_score
        ).count()
        rank = better_attempts + 1

        # Total students who completed
        total_students = StudentAttempt.objects.filter(
            assignment=attempt.assignment,
            is_completed=True
        ).values('student').distinct().count()

        response_serializer = FinishAttemptResponseSerializer(data={
            'attempt_id': attempt.id,
            'score': attempt.auto_score,
            'total': attempt.total_possible,
            'percentage': attempt.calculate_percentage(),
            'rank': rank,
            'total_students': total_students,
            'message': f'You scored {attempt.auto_score}/{attempt.total_possible}!'
        })
        response_serializer.is_valid()

        return Response(response_serializer.data)

    @action(detail=True, methods=['get'])
    def review(self, request, pk=None):
        """Review attempt with correct answers"""
        attempt = self.get_object()

        if not attempt.is_completed:
            return Response(
                {'error': 'Cannot review incomplete attempt'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not attempt.assignment.show_correct_answers:
            return Response(
                {'error': 'Review is not allowed for this test'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all answers with correct answers
        answers = attempt.answers.all().select_related('question')
        review_data = []

        for answer in answers:
            review_data.append({
                'question': answer.question.question_text,
                'options': answer.question.options,
                'your_answer': answer.selected_option,
                'correct_answer': answer.question.correct_option,
                'is_correct': answer.is_correct,
                'points_earned': answer.points_earned,
                'max_points': answer.question.points
            })

        return Response({
            'attempt': StudentAttemptSerializer(attempt).data,
            'review': review_data
        })


class QuestionViewSet(viewsets.ModelViewSet):
    """ViewSet for Question management"""
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer

    def get_queryset(self):
        """Filter by test"""
        queryset = Question.objects.all()
        test_id = self.request.query_params.get('test_id')

        if test_id:
            queryset = queryset.filter(test_id=test_id)

        return queryset.select_related('test')