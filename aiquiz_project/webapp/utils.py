import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def parse_manual_test(questions_text: str, answers_text: str) -> Tuple[str, List[Dict]]:
    """
    Parse manual test input from teacher

    Args:
        questions_text: Raw text with questions and options
        answers_text: Raw text with answer keys

    Returns:
        (title, questions_list)
    """

    logger.info("Starting to parse manual test")
    logger.info(f"Questions text length: {len(questions_text)}")
    logger.info(f"Answers text length: {len(answers_text)}")

    # Extract title from first line
    lines = [line.strip() for line in questions_text.strip().split('\n') if line.strip()]
    title = lines[0] if lines else "Untitled Test"

    logger.info(f"Extracted title: {title}")

    # Parse questions
    questions = []
    current_question = None
    question_number = 0

    for i, line in enumerate(lines[1:], 1):
        if not line:
            continue

        logger.debug(f"Processing line {i}: {line[:50]}...")

        # Check if it's a question number (e.g., "1.", "2.", "100.")
        question_match = re.match(r'^(\d+)[\.\)]\s*(.+)', line)
        if question_match:
            # Save previous question if exists
            if current_question and current_question.get('options'):
                logger.info(
                    f"Saving question #{current_question['number']} with {len(current_question['options'])} options")
                questions.append(current_question)

            # Start new question
            question_number = int(question_match.group(1))
            question_text = question_match.group(2).strip()
            current_question = {
                'number': question_number,
                'text': question_text,
                'options': [],
                'correct_option': None
            }
            logger.debug(f"Started new question #{question_number}: {question_text[:30]}...")

        # Check if it's an option (e.g., "A)", "B)", "C)", "D)")
        elif current_question is not None:
            # Match patterns: A) text, A. text, A - text, (A) text
            option_match = re.match(r'^[\(\[]?([A-Z])[\)\.\]\-\:\)]\s*(.+)', line, re.IGNORECASE)
            if option_match:
                option_letter = option_match.group(1).upper()
                option_text = option_match.group(2).strip()
                current_question['options'].append(option_text)
                logger.debug(f"Added option {option_letter}: {option_text[:30]}...")

    # Add last question
    if current_question and current_question.get('options'):
        logger.info(
            f"Saving last question #{current_question['number']} with {len(current_question['options'])} options")
        questions.append(current_question)

    logger.info(f"Total questions parsed: {len(questions)}")

    # Parse answers
    answer_lines = [line.strip() for line in answers_text.strip().split('\n') if line.strip()]
    answer_map = {}

    logger.info("Starting to parse answers")

    for i, line in enumerate(answer_lines[1:], 1):  # Skip first line (title)
        if not line:
            continue

        # Match patterns like:
        # "1. A) Og'riq qoldiruvchi"
        # "1. A"
        # "1) A"
        # "1 A"
        # "1: A"
        answer_match = re.match(r'^(\d+)[\.\)\:\s]+([A-Z])[\)\.\]:]?\s*(.*)$', line, re.IGNORECASE)
        if answer_match:
            q_num = int(answer_match.group(1))
            correct_letter = answer_match.group(2).upper()
            # Convert letter to index (A=0, B=1, C=2, D=3)
            correct_index = ord(correct_letter) - ord('A')
            answer_map[q_num] = correct_index
            logger.debug(f"Question {q_num}: Correct answer is {correct_letter} (index {correct_index})")
        else:
            logger.warning(f"Could not parse answer line: {line}")

    logger.info(f"Total answers parsed: {len(answer_map)}")

    # Match answers to questions
    for question in questions:
        q_num = question['number']
        if q_num in answer_map:
            question['correct_option'] = answer_map[q_num]
            logger.debug(f"Question {q_num}: Set correct option to {answer_map[q_num]}")
        else:
            logger.warning(f"Question {q_num}: No answer found, defaulting to 0")
            question['correct_option'] = 0

    logger.info(f"Successfully parsed {len(questions)} questions with answers")

    return title, questions


def validate_parsed_test(questions: List[Dict]) -> Tuple[bool, str]:
    """
    Validate parsed test data

    Returns:
        (is_valid, error_message)
    """

    if not questions:
        return False, "No questions found. Please check your input format."

    for i, q in enumerate(questions, 1):
        if not q.get('text'):
            return False, f"Question {i} has no text."

        if not q.get('options') or len(q['options']) < 2:
            return False, f"Question {i} must have at least 2 options. Found {len(q.get('options', []))} options."

        if len(q['options']) > 10:
            return False, f"Question {i} has too many options ({len(q['options'])}). Maximum is 10."

        if q.get('correct_option') is None:
            return False, f"Question {i} has no correct answer specified."

        if q['correct_option'] >= len(q['options']) or q['correct_option'] < 0:
            return False, f"Question {i}: Correct answer index ({q['correct_option']}) is out of range. Must be 0-{len(q['options']) - 1}."

    return True, ""


def format_parse_errors(questions: List[Dict]) -> str:
    """
    Format detailed error information for debugging
    """
    errors = []

    for i, q in enumerate(questions, 1):
        q_errors = []

        if not q.get('text'):
            q_errors.append("Missing question text")

        if not q.get('options'):
            q_errors.append("No options found")
        elif len(q['options']) < 2:
            q_errors.append(f"Only {len(q['options'])} option(s) found, need at least 2")

        if q.get('correct_option') is None:
            q_errors.append("No correct answer")
        elif q.get('options') and q['correct_option'] >= len(q['options']):
            q_errors.append(f"Correct answer index {q['correct_option']} is invalid (only {len(q['options'])} options)")

        if q_errors:
            errors.append(f"Question {q.get('number', i)}: {', '.join(q_errors)}")

    return '\n'.join(errors) if errors else "No specific errors found"


# Test function for debugging
def test_parser():
    """Test the parser with sample data"""

    questions_input = """Medical Translation Test: Basic Terms
1. What is the correct translation of "analgesic"?
A) Og'riq qoldiruvchi
B) Yallig'lanishga qarshi
C) Allergen
D) Yuqumli
2. "Hypertension" refers to:
A) Qandli diabet
B) Yuqori qon bosimi
C) Past qon bosimi
D) Yurak urishi pasayishi"""

    answers_input = """Answer Key: Medical Translation
1. A
2. B"""

    print("Testing parser...")
    title, questions = parse_manual_test(questions_input, answers_input)

    print(f"\nTitle: {title}")
    print(f"Questions parsed: {len(questions)}")

    for q in questions:
        print(f"\nQ{q['number']}: {q['text']}")
        for i, opt in enumerate(q['options']):
            marker = " ✓" if i == q['correct_option'] else ""
            print(f"  {chr(65 + i)}) {opt}{marker}")

    is_valid, error = validate_parsed_test(questions)
    print(f"\nValid: {is_valid}")
    if error:
        print(f"Error: {error}")

    if not is_valid:
        print("\nDetailed errors:")
        print(format_parse_errors(questions))


def parse_group_test_qa(qa_text: str) -> Tuple[List[Dict], str]:
    """
    Parse group test questions and answers in Q&A format

    Format:
    Q1: question text here
    A1: answer text here
    Q2: question text here
    A2: answer text here

    Returns: (questions_list, error_message)
    """
    import re

    logger.info("Parsing group test Q&A format")

    lines = qa_text.strip().split('\n')

    questions = {}
    current_q_num = None
    current_type = None  # 'Q' or 'A'
    current_text = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for Q pattern (Q1:, Q2:, etc.)
        q_match = re.match(r'^Q(\d+):\s*(.+)', line, re.IGNORECASE)
        if q_match:
            # Save previous content
            if current_q_num and current_type and current_text:
                text = ' '.join(current_text).strip()
                if current_type == 'Q':
                    questions[current_q_num]['question'] = text
                elif current_type == 'A':
                    questions[current_q_num]['answer'] = text

            # Start new question
            current_q_num = int(q_match.group(1))
            current_type = 'Q'
            current_text = [q_match.group(2)]

            if current_q_num not in questions:
                questions[current_q_num] = {'number': current_q_num}

            continue

        # Check for A pattern (A1:, A2:, etc.)
        a_match = re.match(r'^A(\d+):\s*(.+)', line, re.IGNORECASE)
        if a_match:
            # Save previous content
            if current_q_num and current_type and current_text:
                text = ' '.join(current_text).strip()
                if current_type == 'Q':
                    questions[current_q_num]['question'] = text
                elif current_type == 'A':
                    questions[current_q_num]['answer'] = text

            # Start answer for this question
            answer_num = int(a_match.group(1))
            current_q_num = answer_num
            current_type = 'A'
            current_text = [a_match.group(2)]

            if current_q_num not in questions:
                questions[current_q_num] = {'number': current_q_num}

            continue

        # Continuation of current Q or A
        if current_type:
            current_text.append(line)

    # Save last content
    if current_q_num and current_type and current_text:
        text = ' '.join(current_text).strip()
        if current_type == 'Q':
            questions[current_q_num]['question'] = text
        elif current_type == 'A':
            questions[current_q_num]['answer'] = text

    # Validate
    result = []
    errors = []

    for num in sorted(questions.keys()):
        q_data = questions[num]

        if 'question' not in q_data or not q_data['question']:
            errors.append(f"Q{num}: Missing question text")
            continue

        if 'answer' not in q_data or not q_data['answer']:
            errors.append(f"Q{num}: Missing answer text")
            continue

        result.append({
            'number': num,
            'question_text': q_data['question'],
            'expected_answer': q_data['answer']
        })

    if errors:
        return [], '; '.join(errors)

    if not result:
        return [], "No questions found. Please check format: Q1: question, A1: answer"

    logger.info(f"Parsed {len(result)} group test questions")
    return result, ""


if __name__ == "__main__":
    test_parser()