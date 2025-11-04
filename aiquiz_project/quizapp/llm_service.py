import json
import logging
import google.generativeai as genai
from django.conf import settings
from .models import Test, Question

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


class TwoModelTestGenerator:
    """
    Two-model approach:
    1. Flash-8B for confirmation (cheap, fast parsing)
    2. Flash for generation (quality test creation)
    """

    def __init__(self):
        # Model 1: Cheap and fast for parsing/confirmation
        self.confirmation_model = genai.GenerativeModel(
            settings.GEMINI_CONFIRMATION_MODEL
        )

        # Model 2: Quality model for test generation
        self.generation_model = genai.GenerativeModel(
            settings.GEMINI_GENERATION_MODEL
        )

        # Fallback: Use generation model if confirmation fails
        self.fallback_to_generation_model = True

    def parse_and_confirm(self, user_input, context=None):
        """
        Use Flash-8B to parse user input and build confirmation

        Args:
            user_input (str): Raw teacher input ("biology test", "15 questions", etc.)
            context (dict): Optional previous parameters for context-aware parsing

        Returns:
            dict: {
                "topic": str,
                "question_count": int,
                "difficulty": str,
                "language": str,
                "description": str  # Grammatically correct confirmation text
            }
        """

        # Build prompt
        prompt = self._build_confirmation_prompt(user_input, context)

        try:
            # Call Flash-8B (cheap model)
            response = self.confirmation_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,  # Low temperature for consistent parsing
                    top_p=0.95,
                    max_output_tokens=512,  # Don't need much for parsing
                )
            )

            # Parse response
            result = self._parse_confirmation_response(response.text)
            logger.info(f"Flash-8B parsed: {result}")
            return result

        except Exception as e:
            logger.error(f"Flash-8B failed: {e}")

            # Fallback to Flash if enabled
            if self.fallback_to_generation_model:
                logger.info("Falling back to Flash for confirmation")
                try:
                    response = self.generation_model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.3,
                            top_p=0.95,
                            max_output_tokens=512,
                        )
                    )
                    result = self._parse_confirmation_response(response.text)
                    logger.info(f"Flash (fallback) parsed: {result}")
                    return result
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    raise Exception(f"Both models failed: {e}, {fallback_error}")
            else:
                raise

    def _build_confirmation_prompt(self, user_input, context=None):
        """Build prompt for confirmation model"""

        if context:
            # Context-aware parsing (user is modifying previous request)
            prompt = f"""You are an intelligent parameter extraction assistant.

                CONTEXT - Previous request:
                {json.dumps(context, indent=2)}
                
                USER NOW SAYS:
                "{user_input}"
                
                YOUR TASK:
                Determine if the user is:
                1. Modifying the previous request (e.g., "make it 15", "hard difficulty")
                2. Providing a complete new request (e.g., "Generate 20 physics questions")
                
                Then return the FINAL parameters incorporating their change.
                
                PARAMETER RULES:
                - topic: The subject (required, extract from input)
                - question_count: Number 1-50 (default: 10)
                - difficulty: "easy" | "intermediate" | "hard" (default: "easy")
                - language: Auto-detect from input text (default: "english")
                  * If text has Cyrillic (а-я): "russian"
                  * If text has Uzbek words (o'zbek, savol, test, oson): "uzbek"
                  * Otherwise: "english"
                
                Then build a grammatically correct description based on the language:
                
                ENGLISH: "Generate [count] [difficulty] [topic] questions in English"
                UZBEK: "O'zbek tilida [topic] bo'yicha [count] ta [difficulty_uzbek] savol yaratish"
                  (difficulty: easy=oson, intermediate=o'rta, hard=qiyin)
                RUSSIAN: "Создать [count] [difficulty_russian] вопросов по теме [topic] на русском языке"
                  (difficulty: easy=простой, intermediate=средний, hard=сложный)
                
                Return ONLY this JSON (no markdown, no code blocks):
                {{
                  "topic": "extracted topic",
                  "question_count": 10,
                  "difficulty": "easy",
                  "language": "english",
                  "description": "Generate 10 easy [topic] questions in English"
            }}"""

        else:

            # Fresh parsing (first input)
            prompt = f"""You are an intelligent parameter extraction assistant.

                USER REQUEST:
                "{user_input}"
                
                YOUR TASK:
                Parse this request and extract test parameters intelligently.
                
                PARAMETER RULES:
                - topic: The subject (required, extract anything related to the test subject)
                - question_count: Look for numbers (default: 10, range: 1-50)
                - difficulty: Look for keywords (default: "easy")
                  * easy: "easy", "simple", "basic", "beginner", "oson", "простой"
                  * intermediate: "intermediate", "medium", "normal", "o'rta", "средний"
                  * hard: "hard", "difficult", "advanced", "qiyin", "сложный"
                - language: Auto-detect from input text (default: "english")
                  * If text has Cyrillic characters (а-я, А-Я): "russian"
                  * If text has Uzbek words (o'zbek, savol, test, oson, qiyin): "uzbek"
                  * Otherwise: "english"
                
                Then build a grammatically correct description:
                
                ENGLISH format:
                "Generate [count] [difficulty] [topic] questions in English"
                Example: "Generate 10 easy biology questions in English"
                
                UZBEK format:
                "O'zbek tilida [topic] bo'yicha [count] ta [difficulty] savol yaratish"
                Example: "O'zbek tilida biologiya bo'yicha 10 ta oson savol yaratish"
                (Translate difficulty: easy=oson, intermediate=o'rta, hard=qiyin)
                
                RUSSIAN format:
                "Создать [count] [difficulty] вопросов по теме [topic] на русском языке"
                Example: "Создать 10 простой вопросов по теме биология на русском языке"
                (Translate difficulty: easy=простой, intermediate=средний, hard=сложный)
                
                Return ONLY this JSON (no markdown, no ```json blocks):
                {{
                  "topic": "extracted topic",
                  "question_count": 10,
                  "difficulty": "easy",
                  "language": "english",
                  "description": "Generate 10 easy [topic] questions in English"
                }}"""

        return prompt

    def _parse_confirmation_response(self, response_text):
        """Parse and validate confirmation response"""

        # Clean response
        text = response_text.strip()

        # Remove markdown code blocks if present
        text = text.replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {e}\nResponse: {text}")

        # Validate required fields
        required = ['topic', 'question_count', 'difficulty', 'language', 'description']
        missing = [f for f in required if f not in data]
        if missing:
            raise Exception(f"Missing required fields: {missing}")

        # Validate values
        if not isinstance(data['question_count'], int) or not (1 <= data['question_count'] <= 50):
            raise Exception(f"Invalid question_count: {data['question_count']}")

        if data['difficulty'] not in ['easy', 'intermediate', 'hard']:
            raise Exception(f"Invalid difficulty: {data['difficulty']}")

        if data['language'] not in ['english', 'uzbek', 'russian']:
            raise Exception(f"Invalid language: {data['language']}")

        return data

    def generate_test(self, teacher, confirmed_params):
        """
        Use Flash to generate actual test with confirmed parameters

        Args:
            teacher (User): Teacher user object
            confirmed_params (dict): Parameters from confirmation step

        Returns:
            Test: Created test object with questions
        """

        # Build generation prompt
        prompt = self._build_generation_prompt(confirmed_params)

        # Try generation (with retries)
        max_retries = settings.LLM_MAX_RETRIES
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Generating test (attempt {attempt + 1}/{max_retries})")

                response = self.generation_model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,  # Balanced creativity
                        max_output_tokens=8192,
                    )
                )

                # Parse and validate
                test_data = self._parse_generation_response(
                    response.text,
                    confirmed_params['question_count']
                )

                # Save to database
                test = self._save_test_to_database(teacher, confirmed_params, test_data)

                logger.info(f"Test generated successfully: {test.id}")
                return test

            except Exception as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                last_error = e
                if attempt < max_retries - 1:
                    continue

        # All retries failed
        raise Exception(f"Failed to generate test after {max_retries} attempts: {last_error}")

    def _build_generation_prompt(self, params):
        """Build prompt for generation model"""

        language_instructions = {
            'english': 'Write ALL text (title, description, questions, options) in English.',
            'uzbek': "O'zbek tilida BARCHA matnlarni yozing (sarlavha, tavsif, savollar, variantlar).",
            'russian': 'Пишите ВЕСЬ текст (заголовок, описание, вопросы, варианты) на русском языке.'
        }

        difficulty_guidelines = {
            'easy': 'Basic recall and recognition. Questions should test fundamental knowledge. Make correct answers fairly obvious. Suitable for beginners.',
            'intermediate': 'Require understanding and application of concepts. Students should need to think and analyze. Mix of recall and comprehension questions.',
            'hard': 'Demand analysis, synthesis, and evaluation. Combine multiple concepts. Require deep understanding. Challenge even advanced students.'
        }

        prompt = f"""You are an expert educational test creator and assessment specialist.

            TASK:
            {params['description']}
            
            EXACT SPECIFICATIONS:
            - Topic: {params['topic']}
            - Number of Questions: {params['question_count']} (GENERATE EXACTLY THIS MANY)
            - Difficulty Level: {params['difficulty'].upper()}
            - Language: {params['language'].upper()}
            
            LANGUAGE INSTRUCTION:
            {language_instructions[params['language']]}
            
            DIFFICULTY GUIDELINES:
            {difficulty_guidelines[params['difficulty']]}
            
            QUALITY REQUIREMENTS:
            1. Questions must be factually accurate and educational
            2. Each question must have exactly 4 options (A, B, C, D)
            3. Make distractors (wrong answers) plausible but clearly incorrect
            4. Ensure all options are similar length and format
            5. Avoid "all of the above" or "none of the above" options
            6. No ambiguous or trick questions
            7. Vary question phrasing to avoid repetition
            8. Test real understanding, not just memorization
            
            OUTPUT STRUCTURE (JSON only, no markdown):
            {{
              "title": "Descriptive test title in {params['language']}",
              "description": "Brief 1-2 sentence description in {params['language']}",
              "questions": [
                {{
                  "question_text": "Clear, complete question in {params['language']}",
                  "options": ["Option A", "Option B", "Option C", "Option D"],
                  "correct_option": 0,
                  "question_type": "mcq",
                  "points": 1
                }}
              ]
            }}
            
            CRITICAL RULES:
            - Generate EXACTLY {params['question_count']} questions
            - ALL text must be in {params['language']}
            - Return ONLY valid JSON (no markdown, no code blocks, no extra text)
            - Ensure correct_option is valid index (0-3)
            - Make questions relevant to: {params['topic']}
            - Follow {params['difficulty']} difficulty level strictly
            
            BEGIN GENERATION:"""

        return prompt

    def _parse_generation_response(self, response_text, expected_count):
        """Parse and validate generation response"""

        # Clean response
        text = response_text.strip()
        text = text.replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON: {e}")

        # Validate structure
        if 'questions' not in data:
            raise Exception("Missing 'questions' field")

        questions = data['questions']

        # Validate question count
        if len(questions) != expected_count:
            raise Exception(f"Expected {expected_count} questions, got {len(questions)}")

        # Validate each question
        for i, q in enumerate(questions):
            if 'question_text' not in q or not q['question_text']:
                raise Exception(f"Question {i + 1}: Missing question_text")

            if 'options' not in q or not isinstance(q['options'], list):
                raise Exception(f"Question {i + 1}: Missing or invalid options")

            if len(q['options']) != 4:
                raise Exception(f"Question {i + 1}: Must have exactly 4 options, got {len(q['options'])}")

            if 'correct_option' not in q:
                raise Exception(f"Question {i + 1}: Missing correct_option")

            if not isinstance(q['correct_option'], int) or not (0 <= q['correct_option'] <= 3):
                raise Exception(f"Question {i + 1}: Invalid correct_option (must be 0-3)")

        return data

    def _save_test_to_database(self, teacher, params, test_data):
        """Save generated test to database"""

        # Create Test
        test = Test.objects.create(
            teacher=teacher,
            title=test_data.get('title', f"Test: {params['topic']}"),
            description=test_data.get('description', ''),
            teacher_prompt=params['description'],  # Store the confirmation description
            llm_response=test_data,  # Store full LLM response
            difficulty=params['difficulty'],
            topic=params['topic']
        )

        # Create Questions
        for i, q_data in enumerate(test_data['questions']):
            Question.objects.create(
                test=test,
                question_text=q_data['question_text'],
                question_type=q_data.get('question_type', 'mcq'),
                options=q_data['options'],
                correct_option=q_data['correct_option'],
                points=q_data.get('points', 1),
                order=i
            )

        return test


# Convenience functions
def confirm_test_parameters(user_input, context=None):
    """
    Parse user input and return confirmation parameters

    Args:
        user_input (str): Teacher's raw input
        context (dict): Optional previous parameters

    Returns:
        dict: Parsed parameters with confirmation description
    """
    generator = TwoModelTestGenerator()
    return generator.parse_and_confirm(user_input, context)


def generate_confirmed_test(teacher, confirmed_params):
    """
    Generate test with confirmed parameters

    Args:
        teacher (User): Teacher object
        confirmed_params (dict): Parameters from confirmation step

    Returns:
        Test: Created test object
    """
    generator = TwoModelTestGenerator()
    return generator.generate_test(teacher, confirmed_params)