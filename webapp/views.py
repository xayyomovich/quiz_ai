from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Max, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json

from .forms import UserRegistrationForm, UserLoginForm, TestCreationForm, ManualTestCreationForm
from quizapp.models import User, Test, Question, Assignment, StudentAttempt, StudentAnswer
from quizapp.llm_service import confirm_test_parameters, generate_confirmed_test


# Import the parser
import sys
import os

sys.path.append(os.path.dirname(__file__))
from utils import parse_manual_test, validate_parsed_test


# ============================================
# LANDING & AUTH VIEWS
# ============================================

def landing_page(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('webapp:dashboard')
    return render(request, 'landing.html')


def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('webapp:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.get_full_name()}! Your account has been created.')
            return redirect('webapp:dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('webapp:dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                next_url = request.GET.get('next', 'webapp:dashboard')
                return redirect(next_url)
    else:
        form = UserLoginForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('webapp:landing')


# ============================================
# DASHBOARD
# ============================================

@login_required
def dashboard_view(request):
    """Role-based dashboard"""
    user = request.user

    if user.role == 'teacher':
        tests = Test.objects.filter(teacher=user)
        total_tests = tests.count()
        total_questions = Question.objects.filter(test__teacher=user).count()

        assignments = Assignment.objects.filter(test__teacher=user)
        total_students = StudentAttempt.objects.filter(
            assignment__in=assignments
        ).values('student').distinct().count()

        recent_tests = tests.order_by('-created_at')[:5]

        context = {
            'total_tests': total_tests,
            'total_questions': total_questions,
            'total_students': total_students,
            'recent_tests': recent_tests,
        }
        return render(request, 'teacher/dashboard.html', context)

    else:
        attempts = StudentAttempt.objects.filter(
            student=user,
            is_completed=True
        ).select_related('assignment__test')

        total_tests_taken = attempts.count()

        if total_tests_taken > 0:
            avg_percentage = sum(a.calculate_percentage() for a in attempts) / total_tests_taken
        else:
            avg_percentage = 0

        recent_attempts = attempts.order_by('-finished_at')[:5]

        context = {
            'total_tests_taken': total_tests_taken,
            'average_score': round(avg_percentage, 1),
            'recent_attempts': recent_attempts,
        }
        return render(request, 'student/dashboard.html', context)


# ============================================
# TEACHER - TEST CREATION CHOICE
# ============================================

@login_required
def create_test_choice(request):
    """Choose between AI or Manual test creation"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can create tests.')
        return redirect('webapp:dashboard')

    return render(request, 'teacher/create_test_choice.html')


# ============================================
# TEACHER - AI TEST CREATION (EXISTING)
# ============================================

@login_required
def create_test_ai_view(request):
    """Create test with AI"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can create tests.')
        return redirect('webapp:dashboard')

    if request.method == 'POST':
        form = TestCreationForm(request.POST)
        if form.is_valid():
            request.session['test_params'] = {
                'prompt': form.cleaned_data.get('prompt'),
                'topic': form.cleaned_data.get('topic'),
                'question_count': form.cleaned_data.get('question_count'),
                'difficulty': form.cleaned_data.get('difficulty'),
                'language': form.cleaned_data.get('language'),
            }
            return redirect('webapp:confirm_test')
    else:
        form = TestCreationForm()

    return render(request, 'teacher/create_test.html', {'form': form})


@login_required
def confirm_test_view(request):
    """Confirm AI test parameters"""
    if request.user.role != 'teacher':
        return redirect('webapp:dashboard')

    test_params = request.session.get('test_params')
    if not test_params:
        return redirect('webapp:create_test_ai')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirm':
            return redirect('webapp:generate_test')
        elif action == 'edit':
            return redirect('webapp:create_test_ai')

    try:
        prompt = test_params.get('prompt')

        if prompt:
            params = confirm_test_parameters(prompt)
        else:
            params = {
                'topic': test_params['topic'],
                'question_count': test_params['question_count'] or 10,
                'difficulty': test_params['difficulty'] or 'intermediate',
                'language': test_params['language'] or 'english',
                'description': f"Generate {test_params['question_count'] or 10} {test_params['difficulty'] or 'intermediate'} questions about {test_params['topic']} in {test_params['language'] or 'English'}"
            }

        request.session['confirmed_params'] = params

        return render(request, 'teacher/confirm_test.html', {'params': params})

    except Exception as e:
        messages.error(request, f'Error parsing test parameters: {str(e)}')
        return redirect('webapp:create_test_ai')


@login_required
def generate_test_view(request):
    """Generate AI test"""
    if request.user.role != 'teacher':
        return redirect('webapp:dashboard')

    confirmed_params = request.session.get('confirmed_params')
    if not confirmed_params:
        return redirect('webapp:create_test_ai')

    try:
        test = generate_confirmed_test(request.user, confirmed_params)

        del request.session['test_params']
        del request.session['confirmed_params']

        messages.success(request, f'Test "{test.title}" created successfully with {test.questions.count()} questions!')
        return redirect('webapp:test_detail', test_id=test.id)

    except Exception as e:
        messages.error(request, f'Error generating test: {str(e)}')
        return redirect('webapp:create_test_ai')


# ============================================
# TEACHER - MANUAL TEST CREATION (NEW)
# ============================================

@login_required
def create_test_manual_view(request):
    """Create test manually by pasting questions"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can create tests.')
        return redirect('webapp:dashboard')

    if request.method == 'POST':
        form = ManualTestCreationForm(request.POST)
        if form.is_valid():
            try:
                # Parse the input
                questions_text = form.cleaned_data['questions_text']
                answers_text = form.cleaned_data['answers_text']

                title, questions = parse_manual_test(questions_text, answers_text)

                # Validate
                is_valid, error = validate_parsed_test(questions)
                if not is_valid:
                    messages.error(request, f'Validation error: {error}')
                    return render(request, 'teacher/create_test_manual.html', {'form': form})

                # Create test
                test = Test.objects.create(
                    teacher=request.user,
                    title=title,
                    description=f"Manual test with {len(questions)} questions",
                    creation_method='manual',
                    topic=form.cleaned_data.get('topic') or title,
                    difficulty=form.cleaned_data.get('difficulty') or 'intermediate',
                    teacher_prompt=f"Manual input: {len(questions)} questions"
                )

                # Create questions
                for q in questions:
                    Question.objects.create(
                        test=test,
                        question_text=q['text'],
                        question_type='mcq',
                        options=q['options'],
                        correct_option=q['correct_option'],
                        points=1,
                        order=q['number']
                    )

                messages.success(request, f'Test "{test.title}" created with {len(questions)} questions!')
                return redirect('webapp:test_detail', test_id=test.id)

            except Exception as e:
                messages.error(request, f'Error creating test: {str(e)}')
                return render(request, 'teacher/create_test_manual.html', {'form': form})
    else:
        form = ManualTestCreationForm()

    return render(request, 'teacher/create_test_manual.html', {'form': form})


# ============================================
# TEACHER - TEST MANAGEMENT
# ============================================

@login_required
def test_list_view(request):
    """List teacher's tests"""
    if request.user.role != 'teacher':
        return redirect('webapp:dashboard')

    tests = Test.objects.filter(teacher=request.user).annotate(
        question_count=Count('questions')
    ).order_by('-created_at')

    return render(request, 'teacher/test_list.html', {'tests': tests})


@login_required
def test_detail_view(request, test_id):
    """Test detail"""
    test = get_object_or_404(Test, id=test_id)

    if request.user.role == 'teacher' and test.teacher != request.user:
        messages.error(request, 'You do not have permission to view this test.')
        return redirect('webapp:dashboard')

    questions = test.questions.all().order_by('order')
    assignments = test.assignments.all()

    context = {
        'test': test,
        'questions': questions,
        'assignments': assignments,
    }
    return render(request, 'teacher/test_detail.html', context)


@login_required
def publish_test_view(request, test_id):
    """Publish test"""
    test = get_object_or_404(Test, id=test_id, teacher=request.user)

    if request.method == 'POST':
        assignment = Assignment.objects.create(
            test=test,
            allow_retakes=request.POST.get('allow_retakes') == 'on',
            max_attempts=int(request.POST.get('max_attempts', 3)),
            show_results_immediately=request.POST.get('show_results_immediately') == 'on',
            show_correct_answers=request.POST.get('show_correct_answers') == 'on',
        )

        messages.success(request, f'Test published! Share code: {assignment.access_token}')
        return redirect('webapp:test_detail', test_id=test.id)

    return render(request, 'teacher/publish_test.html', {'test': test})


@login_required
def test_results_view(request, test_id):
    """View test results"""
    test = get_object_or_404(Test, id=test_id, teacher=request.user)

    assignments = test.assignments.all()
    attempts = StudentAttempt.objects.filter(
        assignment__in=assignments,
        is_completed=True
    ).select_related('student', 'assignment')

    total_attempts = attempts.count()
    if total_attempts > 0:
        avg_score = sum(a.calculate_percentage() for a in attempts) / total_attempts
        highest_score = max(a.calculate_percentage() for a in attempts)
        lowest_score = min(a.calculate_percentage() for a in attempts)
    else:
        avg_score = highest_score = lowest_score = 0

    student_scores = {}
    for attempt in attempts:
        student_id = attempt.student.id
        percentage = attempt.calculate_percentage()
        if student_id not in student_scores or percentage > student_scores[student_id]['percentage']:
            student_scores[student_id] = {
                'student': attempt.student,
                'attempt': attempt,
                'percentage': percentage,
                'score': attempt.auto_score,
                'total': attempt.total_possible,
            }

    top_students = sorted(student_scores.values(), key=lambda x: x['percentage'], reverse=True)[:20]

    context = {
        'test': test,
        'total_attempts': total_attempts,
        'avg_score': round(avg_score, 1),
        'highest_score': round(highest_score, 1),
        'lowest_score': round(lowest_score, 1),
        'top_students': top_students,
    }
    return render(request, 'teacher/test_results.html', context)


# ============================================
# STUDENT - NEW TEST TAKING FLOW
# ============================================

def take_test_new_view(request, token):
    """NEW: Take test with all questions on one page"""
    assignment = get_object_or_404(Assignment, access_token=token, is_active=True)
    test = assignment.test
    questions = test.questions.all().order_by('order')

    # Check if user has already taken test
    attempt = None
    answers = []
    if request.user.is_authenticated:
        attempt = StudentAttempt.objects.filter(
            assignment=assignment,
            student=request.user
        ).first()

        if attempt:
            answers = StudentAnswer.objects.filter(
                attempt=attempt
            ).select_related('question').order_by('question__order')

    if request.method == 'POST':
        # Handle test submission
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Please login to submit test'})

        # Create or get attempt
        if not attempt:
            existing_attempts = StudentAttempt.objects.filter(
                assignment=assignment,
                student=request.user
            ).count()

            if not assignment.allow_retakes and existing_attempts > 0:
                return JsonResponse({'success': False, 'error': 'Retakes not allowed'})

            if assignment.max_attempts > 0 and existing_attempts >= assignment.max_attempts:
                return JsonResponse({'success': False, 'error': 'Maximum attempts reached'})

            total_points = sum(q.points for q in questions)
            attempt = StudentAttempt.objects.create(
                assignment=assignment,
                student=request.user,
                attempt_number=existing_attempts + 1,
                total_possible=total_points
            )

        # Save all answers
        total_score = 0
        for question in questions:
            selected = request.POST.get(f'question_{question.id}')
            if selected is not None:
                answer, created = StudentAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={'selected_option': int(selected)}
                )
                answer.auto_grade()
                total_score += answer.points_earned

        # Update attempt
        attempt.auto_score = total_score
        attempt.is_completed = True
        attempt.finished_at = timezone.now()
        attempt.save()

        return JsonResponse({'success': True})

    # Calculate stats for results
    correct_count = sum(1 for a in answers if a.is_correct)
    wrong_count = len(answers) - correct_count
    total_points = sum(q.points for q in questions)

    context = {
        'assignment': assignment,
        'test': test,
        'questions': questions,
        'attempt': attempt,
        'answers': answers,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'total_points': total_points,
    }

    return render(request, 'student/take_test_new.html', context)


@login_required
def student_history_view(request):
    """Student test history"""
    if request.user.role != 'student':
        return redirect('webapp:dashboard')

    attempts = StudentAttempt.objects.filter(
        student=request.user,
        is_completed=True
    ).select_related('assignment__test').order_by('-finished_at')

    return render(request, 'student/history.html', {'attempts': attempts})