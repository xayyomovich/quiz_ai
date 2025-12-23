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
from collections import defaultdict

from .forms import UserRegistrationForm, UserLoginForm, TestCreationForm, ManualTestCreationForm, \
    CreateGroupTestDirectForm
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
    """Role-based dashboard - UPDATED for students"""
    user = request.user

    if user.role == 'teacher':
        # Teacher dashboard (existing code)
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
        # UPDATED STUDENT DASHBOARD
        attempts = StudentAttempt.objects.filter(
            student=user,
            is_completed=True
        ).select_related('assignment__test')

        total_tests_taken = attempts.count()

        if total_tests_taken > 0:
            # Calculate stats
            percentages = [a.calculate_percentage() for a in attempts]
            average_score = round(sum(percentages) / len(percentages), 1)
            highest_score = round(max(percentages), 1)

            # Tests passed (>=60%)
            tests_passed = sum(1 for p in percentages if p >= 60)

            # Perfect scores (100%)
            perfect_scores = sum(1 for p in percentages if p == 100)

            # Improvement trend (last 5 vs first 5)
            if total_tests_taken >= 10:
                first_5_avg = sum(percentages[:5]) / 5
                last_5_avg = sum(percentages[-5:]) / 5
                improvement_trend = round(last_5_avg - first_5_avg, 1)
            else:
                improvement_trend = 0

            # Overall rank
            all_students = StudentAttempt.objects.filter(
                is_completed=True
            ).values('student').annotate(
                avg_score=Avg('auto_score') * 100.0 / Avg('total_possible')
            ).order_by('-avg_score')

            student_ranks = {s['student']: idx + 1 for idx, s in enumerate(all_students)}
            overall_rank = student_ranks.get(user.id, total_tests_taken)
            total_students = len(all_students)

        else:
            average_score = 0
            highest_score = 0
            tests_passed = 0
            perfect_scores = 0
            improvement_trend = 0
            overall_rank = 0
            total_students = 0

        recent_attempts = attempts.order_by('-finished_at')[:5]

        context = {
            'total_tests_taken': total_tests_taken,
            'average_score': average_score,
            'highest_score': highest_score,
            'tests_passed': tests_passed,
            'perfect_scores': perfect_scores,
            'improvement_trend': improvement_trend,
            'overall_rank': overall_rank,
            'total_students': total_students,
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
                    teacher_prompt=f"Manual input: {len(questions)} questions",
                    timer_minutes=form.cleaned_data.get('timer_minutes')  # NEW: Save timer
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

                timer_info = f" ({test.timer_minutes} min timer)" if test.timer_minutes else ""
                messages.success(request, f'Test "{test.title}" created with {len(questions)} questions{timer_info}!')
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
    """List teacher's tests (both regular and group tests)"""
    if request.user.role != 'teacher':
        return redirect('webapp:dashboard')

    # Regular tests
    tests = Test.objects.filter(teacher=request.user).annotate(
        question_count=Count('questions')
    ).order_by('-created_at')

    # Group tests
    group_tests = GroupTest.objects.filter(teacher=request.user).select_related('test').order_by('group_number')

    context = {
        'tests': tests,
        'group_tests': group_tests,
    }
    return render(request, 'teacher/test_list.html', context)


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
    """Publish test - simplified version"""
    test = get_object_or_404(Test, id=test_id, teacher=request.user)

    # Check if already published
    existing_assignment = Assignment.objects.filter(test=test).first()

    if request.method == 'POST':
        if existing_assignment:
            messages.warning(request, 'This test is already published!')
            return redirect('webapp:test_detail', test_id=test.id)

        # Create assignment with default settings
        assignment = Assignment.objects.create(
            test=test,
            allow_retakes=False,  # Only one attempt allowed
            max_attempts=1,  # Maximum 1 attempt
            show_results_immediately=True,
            show_correct_answers=True,
        )

        messages.success(request, 'Test published successfully!')
        return redirect('webapp:test_detail', test_id=test.id)

    context = {
        'test': test,
        'existing_assignment': existing_assignment,
    }
    return render(request, 'teacher/publish_test.html', context)


@login_required
def test_results_view(request, test_id):
    """Complete teacher results view with analysis"""
    test = get_object_or_404(Test, id=test_id, teacher=request.user)

    assignments = test.assignments.all()

    if not assignments.exists():
        # No assignments yet - test not published
        context = {
            'test': test,
            'stats': {
                'total_students': 0,
                'avg_percentage': 0,
                'highest_percentage': 0,
                'pass_rate': 0,
                'terminated_count': 0,
            },
            'student_results': [],
            'student_results_json': '[]',
            'question_stats': None,
        }
        return render(request, 'teacher/test_results.html', context)

    # Get all completed attempts
    attempts = StudentAttempt.objects.filter(
        assignment__in=assignments,
        is_completed=True
    ).select_related('student', 'assignment').prefetch_related('answers__question')

    # Calculate statistics
    total_students = attempts.values('student').distinct().count()
    terminated_count = attempts.filter(is_terminated=True).count()

    if total_students == 0:
        context = {
            'test': test,
            'stats': {
                'total_students': 0,
                'avg_percentage': 0,
                'highest_percentage': 0,
                'pass_rate': 0,
                'terminated_count': 0,
            },
            'student_results': [],
            'student_results_json': '[]',
            'question_stats': None,
        }
        return render(request, 'teacher/test_results.html', context)

    # Get best attempt per student
    student_best = {}
    for attempt in attempts:
        student_id = attempt.student.id
        percentage = attempt.calculate_percentage()

        if student_id not in student_best or percentage > student_best[student_id]['percentage']:
            student_best[student_id] = {
                'id': attempt.id,
                'student': attempt.student,
                'attempt': attempt,
                'percentage': percentage,
                'score': attempt.auto_score,
                'total': attempt.total_possible,
                'passed': percentage >= 60,  # Pass threshold
            }

    # Calculate stats
    percentages = [s['percentage'] for s in student_best.values()]
    avg_percentage = round(sum(percentages) / len(percentages), 1) if percentages else 0
    highest_percentage = round(max(percentages), 1) if percentages else 0

    passed_count = sum(1 for s in student_best.values() if s['passed'])
    pass_rate = round((passed_count / total_students) * 100, 1) if total_students > 0 else 0

    # Sort students by score (descending)
    sorted_students = sorted(
        student_best.values(),
        key=lambda x: (-x['percentage'], x['attempt'].finished_at)
    )

    # Prepare student results for template
    student_results = []
    for student_data in sorted_students:
        attempt = student_data['attempt']
        student = student_data['student']

        # Get all answers
        answers = StudentAnswer.objects.filter(
            attempt=attempt
        ).select_related('question').order_by('question__order')

        correct_count = sum(1 for a in answers if a.is_correct)
        wrong_count = len(answers) - correct_count

        # Prepare answers detail
        answers_detail = []
        for answer in answers:
            answers_detail.append({
                'question_text': answer.question.question_text,
                'selected': answer.selected_option,
                'selected_letter': 'ABCDEFGHIJ'[answer.selected_option] if answer.selected_option is not None else '?',
                'correct': answer.question.correct_option,
                'correct_letter': 'ABCDEFGHIJ'[answer.question.correct_option],
                'is_correct': answer.is_correct,
            })

        student_results.append({
            'id': attempt.id,
            'name': student.get_full_name(),
            'email': student.email,
            'score': attempt.auto_score,
            'total': attempt.total_possible,
            'percentage': round(student_data['percentage'], 1),
            'passed': student_data['passed'],
            'is_terminated': attempt.is_terminated,
            'termination_reason': attempt.termination_reason or '',
            'questions_answered': attempt.questions_answered,
            'time_taken': attempt.time_taken_seconds,
            'finished_at': attempt.finished_at.isoformat() if attempt.finished_at else None,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'answers': answers_detail,
        })

    # Question-by-Question Analysis
    questions = test.questions.all().order_by('order')
    question_stats_data = defaultdict(lambda: {'correct': 0, 'total': 0})

    for attempt in attempts:
        for answer in attempt.answers.all():
            q_id = answer.question.id
            question_stats_data[q_id]['total'] += 1
            if answer.is_correct:
                question_stats_data[q_id]['correct'] += 1

    # Find hardest and easiest questions
    question_analysis = []
    for question in questions:
        stats = question_stats_data[question.id]
        if stats['total'] > 0:
            correct_percent = round((stats['correct'] / stats['total']) * 100, 1)
            question_analysis.append({
                'id': question.id,
                'number': question.order + 1,
                'text': question.question_text,
                'correct_percent': correct_percent,
            })

    question_analysis.sort(key=lambda x: x['correct_percent'])

    question_stats = {
        'hardest': question_analysis[:3] if len(question_analysis) >= 3 else question_analysis,
        'easiest': question_analysis[-3:][::-1] if len(question_analysis) >= 3 else question_analysis[::-1],
    } if question_analysis else None

    # Convert to JSON for Alpine.js
    student_results_json = json.dumps(student_results)

    context = {
        'test': test,
        'stats': {
            'total_students': total_students,
            'avg_percentage': avg_percentage,
            'highest_percentage': highest_percentage,
            'pass_rate': pass_rate,
            'terminated_count': terminated_count,
        },
        'student_results': student_results,
        'student_results_json': student_results_json,
        'question_stats': question_stats,
    }

    return render(request, 'teacher/test_results.html', context)


# ============================================
# STUDENT - NEW TEST TAKING FLOW
# ============================================

def take_test_new_view(request, token):
    """Complete test taking with timer, anti-cheat, and results - FIXED"""
    assignment = get_object_or_404(Assignment, access_token=token, is_active=True)
    test = assignment.test
    questions = test.questions.all().order_by('order')

    # Check if user is authenticated
    if not request.user.is_authenticated:
        request.session['test_redirect'] = request.path
        messages.info(request, 'Please login to take the test.')
        return redirect('webapp:login')

    # Get existing attempt
    attempt = StudentAttempt.objects.filter(
        assignment=assignment,
        student=request.user
    ).order_by('-started_at').first()  # Get latest attempt

    # Prepare results data
    answers_list = []
    results_json = '[]'
    correct_count = 0
    wrong_count = 0

    if attempt and attempt.is_completed:
        # Get all answers for this attempt
        answers_list = StudentAnswer.objects.filter(
            attempt=attempt
        ).select_related('question').order_by('question__order')

        # Prepare results for JavaScript
        results_data = []
        for answer in answers_list:
            results_data.append({
                'selected': answer.selected_option,
                'correct': answer.question.correct_option,
                'is_correct': answer.is_correct
            })
            if answer.is_correct:
                correct_count += 1
            else:
                wrong_count += 1

        results_json = json.dumps(results_data)

    # Handle POST (test submission)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Please login'})

        # Check if termination
        is_terminated = request.POST.get('terminated') == 'true'
        termination_reason = request.POST.get('reason', '')

        # Create or get attempt
        if not attempt or attempt.is_completed:
            # Check if retakes allowed
            existing_attempts = StudentAttempt.objects.filter(
                assignment=assignment,
                student=request.user
            ).count()

            if not assignment.allow_retakes and existing_attempts > 0:
                return JsonResponse(
                    {'success': False, 'error': 'Retakes not allowed. You can only take this test once.'})

            if assignment.max_attempts > 0 and existing_attempts >= assignment.max_attempts:
                return JsonResponse(
                    {'success': False, 'error': f'Maximum attempts ({assignment.max_attempts}) reached.'})

            total_points = sum(q.points for q in questions)
            attempt = StudentAttempt.objects.create(
                assignment=assignment,
                student=request.user,
                attempt_number=existing_attempts + 1,
                total_possible=total_points
            )

        # Save all answers
        total_score = 0
        questions_answered = 0

        for question in questions:
            selected = request.POST.get(f'question_{question.id}')
            if selected is not None:
                questions_answered += 1
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
        attempt.questions_answered = questions_answered

        # Handle time taken
        time_taken = request.POST.get('time_taken')
        if time_taken:
            attempt.time_taken_seconds = int(time_taken)

        # Handle termination
        if is_terminated:
            attempt.is_terminated = True
            attempt.termination_reason = termination_reason
            attempt.terminated_at = timezone.now()
            # Recalculate total_possible based on answered questions
            attempt.total_possible = questions_answered

        attempt.save()

        # Prepare response
        results_data = []
        correct = 0
        wrong = 0

        for answer in attempt.answers.all().order_by('question__order'):
            results_data.append({
                'selected': answer.selected_option,
                'correct': answer.question.correct_option,
                'is_correct': answer.is_correct
            })
            if answer.is_correct:
                correct += 1
            else:
                wrong += 1

        return JsonResponse({
            'success': True,
            'score': attempt.auto_score,
            'total': attempt.total_possible,
            'percentage': attempt.calculate_percentage(),
            'correct_count': correct,
            'wrong_count': wrong,
            'results': results_data,
            'time_taken': attempt.time_taken_seconds
        })

    # Handle AJAX answer save
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and '/save/' in request.path:
        question_id = request.POST.get('question_id')
        selected_option = request.POST.get('selected_option')

        if attempt and question_id and selected_option is not None:
            try:
                question = Question.objects.get(id=question_id, test=test)
                answer, created = StudentAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={'selected_option': int(selected_option)}
                )
                return JsonResponse({'success': True})
            except Question.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Question not found'})

        return JsonResponse({'success': False, 'error': 'Invalid data'})

    # Calculate stats
    total_points = sum(q.points for q in questions)

    context = {
        'assignment': assignment,
        'test': test,
        'questions': questions,
        'attempt': attempt,
        'answers': answers_list,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'total_points': total_points,
        'results_json': results_json,
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


@login_required
def student_rankings_view(request):
    """Student rankings and leaderboard page"""
    if request.user.role != 'student':
        return redirect('webapp:dashboard')

    user = request.user

    # Get all completed attempts
    all_attempts = StudentAttempt.objects.filter(
        is_completed=True
    ).select_related('student', 'assignment__test')

    # Calculate student averages
    student_stats = defaultdict(lambda: {'scores': [], 'tests': 0, 'best': 0})

    for attempt in all_attempts:
        student_id = attempt.student.id
        percentage = attempt.calculate_percentage()
        student_stats[student_id]['scores'].append(percentage)
        student_stats[student_id]['tests'] += 1
        student_stats[student_id]['best'] = max(student_stats[student_id]['best'], percentage)
        student_stats[student_id]['name'] = attempt.student.get_full_name()

    # Calculate averages and create leaderboard
    leaderboard_data = []
    for student_id, stats in student_stats.items():
        if stats['tests'] > 0:
            avg = round(sum(stats['scores']) / len(stats['scores']), 1)
            leaderboard_data.append({
                'student_id': student_id,
                'name': stats['name'],
                'average': avg,
                'tests_taken': stats['tests'],
                'best': round(stats['best'], 1),
                'is_you': student_id == user.id
            })

    # Sort by average score (descending)
    leaderboard_data.sort(key=lambda x: x['average'], reverse=True)

    # Get user's stats
    user_stats = next((s for s in leaderboard_data if s['is_you']), None)
    your_rank = next((idx + 1 for idx, s in enumerate(leaderboard_data) if s['is_you']), 0)

    # Get recent test rankings
    user_attempts = StudentAttempt.objects.filter(
        student=user,
        is_completed=True
    ).select_related('assignment__test').order_by('-finished_at')[:5]

    recent_test_rankings = []
    for attempt in user_attempts:
        # Get all attempts for this test
        test_attempts = StudentAttempt.objects.filter(
            assignment=attempt.assignment,
            is_completed=True
        ).values('student').annotate(
            best_score=Max('auto_score')
        ).order_by('-best_score')

        # Find user's rank
        rank = next((idx + 1 for idx, ta in enumerate(test_attempts)
                     if ta['student'] == user.id), 0)

        recent_test_rankings.append({
            'test_name': attempt.assignment.test.title,
            'percentage': round(attempt.calculate_percentage(), 1),
            'rank': rank,
            'total': test_attempts.count(),
            'date': attempt.finished_at
        })

    context = {
        'leaderboard': leaderboard_data[:20],  # Top 20
        'your_rank': your_rank,
        'your_average': user_stats['average'] if user_stats else 0,
        'your_best': user_stats['best'] if user_stats else 0,
        'tests_taken': user_stats['tests_taken'] if user_stats else 0,
        'total_students': len(leaderboard_data),
        'recent_test_rankings': recent_test_rankings,
    }

    return render(request, 'student/rankings.html', context)


@login_required
def student_progress_view(request):
    """Student progress report - Coming soon placeholder"""
    if request.user.role != 'student':
        return redirect('webapp:dashboard')

    # For now, redirect to dashboard
    # TODO: Create detailed progress report page
    messages.info(request, 'Progress report feature coming soon!')
    return redirect('webapp:dashboard')


@login_required
def delete_test_view(request, test_id):
    """Delete a test (teacher only)"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can delete tests.')
        return redirect('webapp:dashboard')

    test = get_object_or_404(Test, id=test_id, teacher=request.user)

    if request.method == 'POST':
        test_title = test.title
        test.delete()  # Django will cascade delete related objects automatically
        messages.success(request, f'Test "{test_title}" has been deleted successfully.')
        return redirect('webapp:dashboard')  # Changed from test_list to dashboard

    # If GET request (shouldn't happen), redirect to dashboard
    return redirect('webapp:dashboard')


# ============================================
# GROUP TEST VIEWS (ADD BEFORE THE LAST LINE)
# ============================================

from quizapp.models import GroupTest, GroupAttempt, GroupMember, IndividualOpinion, GroupAnswer
from .forms import GroupTestCreationForm


@login_required
def create_group_test_view(request):
    """Create a group test with open-ended discussion questions"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can create group tests.')
        return redirect('webapp:dashboard')

    if request.method == 'POST':
        form = CreateGroupTestDirectForm(data=request.POST)
        if form.is_valid():
            try:
                # Extract data
                group_number = int(form.cleaned_data['group_number'])
                title = form.cleaned_data['title']
                qa_text = form.cleaned_data['questions_and_answers']
                timer_minutes = form.cleaned_data['timer_minutes']
                max_group_size = form.cleaned_data['max_group_size']

                # Check if group exists
                existing = GroupTest.objects.filter(
                    teacher=request.user,
                    group_number=group_number
                ).first()

                if existing:
                    messages.error(request,
                                   f'Group-{group_number} already exists! Delete it first or choose another number.')
                    return render(request, 'teacher/create_group_test_simple.html', {'form': form})

                # Parse Q&A format
                from webapp.utils import parse_group_test_qa

                questions, error = parse_group_test_qa(qa_text)

                if error:
                    messages.error(request, f'Parse error: {error}')
                    return render(request, 'teacher/create_group_test_simple.html', {'form': form})

                # Create Test
                test = Test.objects.create(
                    teacher=request.user,
                    title=title,
                    description=f"Group discussion test with {len(questions)} open-ended questions",
                    creation_method='manual',
                    topic=title,
                    difficulty='intermediate',
                    teacher_prompt=f"Group test: {len(questions)} discussion questions"
                )

                # Create Questions (store expected answer in options[0])
                for q in questions:
                    Question.objects.create(
                        test=test,
                        question_text=q['question_text'],
                        question_type='text',  # Mark as text-based
                        options=[q['expected_answer']],  # Store expected answer
                        correct_option=0,  # Always 0 for text questions
                        points=10,  # Higher points for discussion questions
                        order=q['number'] - 1
                    )

                # Create GroupTest
                group_test = GroupTest.objects.create(
                    group_number=group_number,
                    test=test,
                    teacher=request.user,
                    timer_minutes=timer_minutes,
                    max_group_size=max_group_size
                )

                messages.success(request, f'Group-{group_number} created with {len(questions)} discussion questions!')
                return redirect('webapp:group_test_detail', group_test_id=group_test.id)

            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error: {str(e)}')
                return render(request, 'teacher/create_group_test_simple.html', {'form': form})
    else:
        form = CreateGroupTestDirectForm()

    return render(request, 'teacher/create_group_test_simple.html', {'form': form})


@login_required
def group_test_detail_view(request, group_test_id):
    """View group test details (teacher only)"""
    group_test = get_object_or_404(GroupTest, id=group_test_id, teacher=request.user)

    # Get attempts for this group test
    attempts = GroupAttempt.objects.filter(
        group_test=group_test,
        is_completed=True
    ).prefetch_related('members', 'answers', 'opinions')

    context = {
        'group_test': group_test,
        'attempts': attempts,
    }
    return render(request, 'teacher/group_test_detail.html', context)


@login_required
def delete_group_test_view(request, group_test_id):
    """Delete a group test (teacher only)"""
    if request.user.role != 'teacher':
        messages.error(request, 'Only teachers can delete group tests.')
        return redirect('webapp:dashboard')

    group_test = get_object_or_404(GroupTest, id=group_test_id, teacher=request.user)

    if request.method == 'POST':
        group_number = group_test.group_number
        group_test.delete()
        messages.success(request, f'Group-{group_number} has been deleted successfully.')
        return redirect('webapp:test_list')

    return redirect('webapp:test_list')


@login_required
def group_test_results_view(request, group_test_id):
    """View results for a group test (teacher only)"""
    group_test = get_object_or_404(GroupTest, id=group_test_id, teacher=request.user)

    # Get all completed attempts
    attempts = GroupAttempt.objects.filter(
        group_test=group_test,
        is_completed=True
    ).prefetch_related('members', 'answers')

    # Prepare results data
    results_data = []
    for attempt in attempts:
        members_data = []
        for member in attempt.members.all():
            members_data.append({
                'name': member.student.get_full_name(),
                'email': member.student.email,
                'individual_score': round(member.individual_score_percentage, 1),
            })

        results_data.append({
            'id': attempt.id,
            'date': attempt.finished_at,
            'group_score': round(attempt.group_score_percentage, 1),
            'members': members_data,
            'time_taken': attempt.time_taken_seconds,
        })

    context = {
        'group_test': group_test,
        'results': results_data,
    }
    return render(request, 'teacher/group_test_results.html', context)


# ============================================
# STUDENT - GROUP TEST TAKING
# ============================================

def take_group_test_view(request, token):
    """
    Group test flow:
    1. Join waiting room
    2. Start test
    3. Take test
    4. See results
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Group test accessed with token: {token}")

    # Get group test
    try:
        group_test = GroupTest.objects.get(access_token=token, is_active=True)
        logger.info(f"Found group test: {group_test}")
    except GroupTest.DoesNotExist:
        messages.error(request, 'Group test not found or inactive.')
        return redirect('webapp:landing')

    # Check authentication
    if not request.user.is_authenticated:
        request.session['test_redirect'] = request.path
        messages.info(request, 'Please login to join the group test.')
        return redirect('webapp:login')

    # Get or create current attempt (only one active attempt at a time)
    current_attempt = GroupAttempt.objects.filter(
        group_test=group_test,
        is_completed=False
    ).first()

    if not current_attempt:
        # Create new attempt
        total_points = sum(q.points for q in group_test.test.questions.all())
        current_attempt = GroupAttempt.objects.create(
            group_test=group_test,
            total_possible=total_points
        )
        logger.info(f"Created new attempt: {current_attempt.id}")

    # Check if student already joined
    member, created = GroupMember.objects.get_or_create(
        group_attempt=current_attempt,
        student=request.user
    )

    if created:
        logger.info(f"Student joined: {request.user.get_full_name()}")

    # Check group size limit
    current_size = current_attempt.members.count()
    if created and current_size > group_test.max_group_size:
        member.delete()
        messages.error(request, f'Group is full! Maximum {group_test.max_group_size} students allowed.')
        return redirect('webapp:dashboard')

    # Get all members
    all_members = current_attempt.members.select_related('student').all()

    # ============================================
    # HANDLE POST REQUESTS
    # ============================================
    if request.method == 'POST':
        action = request.POST.get('action')
        logger.info(f"POST action: {action}")

        # START TEST
        if action == 'start_test' and not current_attempt.is_started:
            current_attempt.is_started = True
            current_attempt.started_at = timezone.now()
            current_attempt.save()
            logger.info("Test started!")
            messages.success(request, 'Test started! Good luck!')
            return redirect('webapp:take_group_test', token=token)

        # SUBMIT OPINION
        elif action == 'submit_opinion':
            question_id = request.POST.get('question_id')
            opinion_text = request.POST.get('opinion_text', '').strip()

            if question_id and opinion_text:
                question = get_object_or_404(Question, id=question_id, test=group_test.test)

                # Save or update opinion
                opinion, created = IndividualOpinion.objects.update_or_create(
                    group_attempt=current_attempt,
                    question=question,
                    student=request.user,
                    defaults={'opinion_text': opinion_text}
                )

                # Check if all opinions submitted
                total_questions = group_test.test.questions.count()
                user_opinions = IndividualOpinion.objects.filter(
                    group_attempt=current_attempt,
                    student=request.user
                ).count()

                if user_opinions == total_questions:
                    member.has_submitted_all_opinions = True
                    member.save()

                messages.success(request, 'Opinion saved!')
                return redirect('webapp:take_group_test', token=token)

        # SUBMIT GROUP ANSWER
        elif action == 'submit_group_answer':
            question_id = request.POST.get('question_id')
            text_answer = request.POST.get('text_answer', '').strip()

            if question_id and text_answer:
                question = get_object_or_404(Question, id=question_id, test=group_test.test)

                # Check if already answered
                existing = GroupAnswer.objects.filter(
                    group_attempt=current_attempt,
                    question=question
                ).first()

                if existing:
                    messages.warning(request, 'This question has already been answered by your group!')
                else:
                    # Save group answer (TEXT-BASED)
                    group_answer = GroupAnswer.objects.create(
                        group_attempt=current_attempt,
                        question=question,
                        selected_option=0,  # Not used for text
                        submitted_by=request.user
                    )
                    # Store text answer
                    group_answer.text_answer = text_answer
                    group_answer.save()

                    messages.success(request, 'Group answer submitted!')

                return redirect('webapp:take_group_test', token=token)

        # FINISH TEST
        elif action == 'finish_test':
            logger.info("Finishing test and grading...")

            # Grade everything
            from quizapp.llm_service import grade_group_test
            grade_group_test(current_attempt)

            current_attempt.is_completed = True
            current_attempt.finished_at = timezone.now()

            # Calculate time taken
            if current_attempt.started_at:
                time_taken = (current_attempt.finished_at - current_attempt.started_at).total_seconds()
                current_attempt.time_taken_seconds = int(time_taken)

            current_attempt.save()

            messages.success(request, 'Test completed! View your results below.')
            return redirect('webapp:take_group_test', token=token)

    # ============================================
    # HANDLE GET REQUESTS (SHOW PAGES)
    # ============================================
    questions = group_test.test.questions.all().order_by('order')

    # STATE 1: WAITING ROOM (not started yet)
    if not current_attempt.is_started:
        logger.info("Showing waiting room")
        context = {
            'group_test': group_test,
            'attempt': current_attempt,
            'members': all_members,
            'current_size': current_size,
        }
        return render(request, 'student/group_test_waiting.html', context)

    # STATE 2: TAKING TEST (started but not completed)
    elif not current_attempt.is_completed:
        logger.info("Showing test page")

        # Get user's opinions
        user_opinions = {}
        for opinion in IndividualOpinion.objects.filter(
                group_attempt=current_attempt,
                student=request.user
        ).select_related('question'):
            user_opinions[opinion.question.id] = opinion.opinion_text

        # Get group answers
        group_answers = {}
        for answer in GroupAnswer.objects.filter(
                group_attempt=current_attempt
        ).select_related('question', 'submitted_by'):
            group_answers[answer.question.id] = {
                'text': answer.text_answer,
                'submitted_by': answer.submitted_by.get_full_name()
            }

        # Calculate timer
        time_remaining = None
        if current_attempt.started_at and group_test.timer_minutes:
            elapsed = (timezone.now() - current_attempt.started_at).total_seconds()
            total_seconds = group_test.timer_minutes * 60
            time_remaining = max(0, int(total_seconds - elapsed))

        context = {
            'group_test': group_test,
            'attempt': current_attempt,
            'members': all_members,
            'questions': questions,
            'user_opinions': user_opinions,
            'group_answers': group_answers,
            'time_remaining': time_remaining,
        }
        return render(request, 'student/take_group_test.html', context)

    # STATE 3: RESULTS (completed)
    else:
        logger.info("Showing results page")

        # Get member's scores
        member = GroupMember.objects.get(
            group_attempt=current_attempt,
            student=request.user
        )

        # Get all members' scores
        all_scores = []
        for m in all_members:
            all_scores.append({
                'name': m.student.get_full_name(),
                'individual_score': round(m.individual_score_percentage, 1),
                'is_you': m.student == request.user
            })

        # Sort by score
        all_scores.sort(key=lambda x: x['individual_score'], reverse=True)

        context = {
            'group_test': group_test,
            'attempt': current_attempt,
            'member': member,
            'all_scores': all_scores,
            'group_score': round(current_attempt.group_score_percentage, 1),
        }
        return render(request, 'student/group_test_results.html', context)