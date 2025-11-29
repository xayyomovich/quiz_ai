#!/usr/bin/env python
"""
Test script for Two-Model LLM service
Tests both Flash-8B (confirmation) and Flash (generation)
Run: python test_llm.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiquiz_project.settings')
django.setup()

from quizapp.models import User, Test
from quizapp.llm_service import confirm_test_parameters, generate_confirmed_test


def test_confirmation():
    """Test Flash-8B confirmation (Step 1)"""
    print("\n" + "=" * 60)
    print("TEST 1: Confirmation with Flash-8B")
    print("=" * 60)

    test_inputs = [
        "biology test",
        "15 intermediate physics questions",
        "Create 20 hard math questions in Uzbek",
        "математика 10 вопросов",  # Russian
    ]

    for user_input in test_inputs:
        print(f"\n📝 Input: '{user_input}'")
        print("Processing with Flash-8B...")

        try:
            params = confirm_test_parameters(user_input)
            print(f"\n✅ Parsed successfully!")
            print(f"   Topic: {params['topic']}")
            print(f"   Count: {params['question_count']}")
            print(f"   Difficulty: {params['difficulty']}")
            print(f"   Language: {params['language']}")
            print(f"   Description: '{params['description']}'")
        except Exception as e:
            print(f"\n❌ Error: {e}")


def test_context_aware_editing():
    """Test context-aware parsing (editing flow)"""
    print("\n" + "=" * 60)
    print("TEST 2: Context-Aware Editing (Chat Style)")
    print("=" * 60)

    # Initial request
    print("\n📝 Teacher: 'biology test'")
    params = confirm_test_parameters("biology test")
    print(f"✅ Bot: '{params['description']}'")

    # Edit 1: Change count
    print("\n📝 Teacher: 'make it 15 questions'")
    params = confirm_test_parameters("make it 15 questions", context=params)
    print(f"✅ Bot: '{params['description']}'")

    # Edit 2: Change difficulty
    print("\n📝 Teacher: 'hard difficulty please'")
    params = confirm_test_parameters("hard difficulty please", context=params)
    print(f"✅ Bot: '{params['description']}'")

    # Edit 3: Change language
    print("\n📝 Teacher: 'in Uzbek'")
    params = confirm_test_parameters("in Uzbek", context=params)
    print(f"✅ Bot: '{params['description']}'")

    print(f"\n📋 Final parameters:")
    print(f"   Topic: {params['topic']}")
    print(f"   Count: {params['question_count']}")
    print(f"   Difficulty: {params['difficulty']}")
    print(f"   Language: {params['language']}")


def test_full_generation():
    """Test full flow: Confirmation + Generation"""
    print("\n" + "=" * 60)
    print("TEST 3: Full Generation Flow (Flash-8B → Flash)")
    print("=" * 60)

    # Create or get test teacher
    teacher, created = User.objects.get_or_create(
        telegram_id=999999999,
        defaults={
            'full_name': 'Test Teacher',
            'role': 'teacher'
        }
    )
    print(f"\n👤 Teacher: {teacher.full_name} (ID: {teacher.telegram_id})")

    # Step 1: Confirmation
    user_input = "Create 3 easy questions about basic mathematics"
    print(f"\n📝 Step 1 - Confirmation:")
    print(f"   Input: '{user_input}'")
    print("   Processing with Flash-8B...")

    try:
        params = confirm_test_parameters(user_input)
        print(f"\n✅ Confirmation ready:")
        print(f"   Description: '{params['description']}'")
        print(f"   Parameters: {params['question_count']} {params['difficulty']} questions")

        # Step 2: Generation
        print(f"\n📝 Step 2 - Generation:")
        print(f"   Calling Flash to generate test...")
        print(f"   (This may take 5-10 seconds)")

        test = generate_confirmed_test(teacher, params)

        print(f"\n✅ Test generated successfully!")
        print(f"   ID: {test.id}")
        print(f"   Title: {test.title}")
        print(f"   Description: {test.description}")
        print(f"   Questions: {test.questions.count()}")
        print(f"   Topic: {test.topic}")
        print(f"   Difficulty: {test.difficulty}")

        # Show questions
        print(f"\n📋 Generated Questions:")
        for i, question in enumerate(test.questions.all(), 1):
            print(f"\n   Q{i}: {question.question_text}")
            print(f"   Options:")
            for j, opt in enumerate(question.options):
                marker = "✓" if j == question.correct_option else " "
                print(f"      {j}. {opt} {marker}")
            print(f"   Points: {question.points}")

        return test

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_multilanguage():
    """Test multi-language support"""
    print("\n" + "=" * 60)
    print("TEST 4: Multi-Language Support")
    print("=" * 60)

    languages = [
        ("English", "5 easy biology questions"),
        ("Uzbek", "biologiya haqida 5 ta oson savol"),
        ("Russian", "5 простых вопросов по биологии"),
    ]

    for lang_name, user_input in languages:
        print(f"\n🌐 Testing {lang_name}:")
        print(f"   Input: '{user_input}'")

        try:
            params = confirm_test_parameters(user_input)
            print(f"   ✅ Detected language: {params['language']}")
            print(f"   Description: '{params['description']}'")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n" + "=" * 60)
    print("TEST 5: Edge Cases & Error Handling")
    print("=" * 60)

    edge_cases = [
        ("Minimal input", "test"),
        ("Only topic", "physics"),
        ("Only number", "15"),
        ("Very specific", "Generate exactly 25 hard chemistry questions about organic compounds in English"),
        ("Mixed language", "создать biology test"),
    ]

    for case_name, user_input in edge_cases:
        print(f"\n🧪 {case_name}:")
        print(f"   Input: '{user_input}'")

        try:
            params = confirm_test_parameters(user_input)
            print(f"   ✅ Success: {params['description']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 TWO-MODEL LLM SERVICE TEST SUITE")
    print("   Model 1: Gemini Flash-8B (Confirmation)")
    print("   Model 2: Gemini Flash (Generation)")
    print("=" * 60)

    # Check API key
    from django.conf import settings
    if not settings.GEMINI_API_KEY:
        print("\n❌ ERROR: GEMINI_API_KEY not found in .env file!")
        print("   Please add your Gemini API key to .env")
        return

    print(f"\n✅ Gemini API Key found: {settings.GEMINI_API_KEY[:10]}...")
    print(f"✅ Confirmation Model: {settings.GEMINI_CONFIRMATION_MODEL}")
    print(f"✅ Generation Model: {settings.GEMINI_GENERATION_MODEL}")

    # Run tests
    try:
        test_confirmation()

        print("\n" + "-" * 60)
        input("\nPress Enter to test context-aware editing...")
        test_context_aware_editing()

        print("\n" + "-" * 60)
        input("\nPress Enter to test multi-language support...")
        test_multilanguage()

        print("\n" + "-" * 60)
        input("\nPress Enter to test edge cases...")
        test_edge_cases()

        print("\n" + "-" * 60)
        choice = input("\nTest full generation? (calls both models, y/n): ")
        if choice.lower() == 'y':
            test_full_generation()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ Test suite completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
# !/usr/bin/env python
"""
Test script for LLM service
Run: python test_llm.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiquiz_project.settings')
django.setup()

from quizapp.models import User, Test
from quizapp.llm_service import LLMTestGenerator


def test_natural_language():
    """Test natural language input parsing"""
    print("\n" + "=" * 60)
    print("TEST 1: Natural Language Input Parsing")
    print("=" * 60)

    generator = LLMTestGenerator()

    test_inputs = [
        "Create 5 questions about Python programming, easy level",
        "Make 10 hard questions on photosynthesis in Uzbek",
        "15 intermediate biology questions in Russian",
        "Present Perfect Tense quiz, 8 questions",
    ]

    for input_text in test_inputs:
        print(f"\nInput: {input_text}")
        params = generator.parse_teacher_input(input_text)
        print(f"Parsed: {params}")


def test_generation():
    """Test actual test generation with Gemini"""
    print("\n" + "=" * 60)
    print("TEST 2: Full Test Generation")
    print("=" * 60)

    # Create or get test teacher
    teacher, created = User.objects.get_or_create(
        telegram_id=999999999,
        defaults={
            'full_name': 'Test Teacher',
            'role': 'teacher'
        }
    )
    print(f"\nTeacher: {teacher.full_name} (ID: {teacher.telegram_id})")

    # Test with natural language
    prompt = "Create 3 easy questions about basic mathematics in English"
    print(f"\nPrompt: {prompt}")
    print("Generating test... (this may take 5-10 seconds)")

    try:
        from quizapp.llm_service import generate_test_with_llm
        test = generate_test_with_llm(teacher, prompt)

        print(f"\n✅ Test generated successfully!")
        print(f"   ID: {test.id}")
        print(f"   Title: {test.title}")
        print(f"   Description: {test.description}")
        print(f"   Questions: {test.questions.count()}")
        print(f"   Topic: {test.topic}")
        print(f"   Difficulty: {test.difficulty}")

        # Show questions
        print("\n📋 Generated Questions:")
        for i, question in enumerate(test.questions.all(), 1):
            print(f"\n   Q{i}: {question.question_text}")
            print(f"   Options: {question.options}")
            print(f"   Correct: Option {question.correct_option} - {question.options[question.correct_option]}")
            print(f"   Points: {question.points}")

        return test

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_structured_input():
    """Test structured parameter input"""
    print("\n" + "=" * 60)
    print("TEST 3: Structured Input Generation")
    print("=" * 60)

    teacher, _ = User.objects.get_or_create(
        telegram_id=999999999,
        defaults={'full_name': 'Test Teacher', 'role': 'teacher'}
    )

    params = {
        'topic': 'World War II',
        'question_count': 3,
        'difficulty': 'intermediate',
        'language': 'english',
        'options_per_question': 4
    }

    print(f"\nParameters: {params}")
    print("Generating test...")

    try:
        from quizapp.llm_service import generate_test_with_llm
        test = generate_test_with_llm(teacher, params)

        print(f"\n✅ Test generated successfully!")
        print(f"   Title: {test.title}")
        print(f"   Questions: {test.questions.count()}")

        return test

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return None


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 LLM SERVICE TEST SUITE")
    print("=" * 60)

    # Check API key
    from django.conf import settings
    if not settings.GEMINI_API_KEY:
        print("\n❌ ERROR: GEMINI_API_KEY not found in .env file!")
        print("   Please add your Gemini API key to .env")
        return

    print(f"\n✅ Gemini API Key found: {settings.GEMINI_API_KEY[:10]}...")

    # Run tests
    test_natural_language()

    print("\n" + "-" * 60)
    input("\nPress Enter to test actual generation (will call Gemini API)...")

    test = test_generation()

    if test:
        print("\n" + "-" * 60)
        choice = input("\nTest structured input too? (y/n): ")
        if choice.lower() == 'y':
            test_structured_input()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()