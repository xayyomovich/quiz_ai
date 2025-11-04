import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Django API base URL
API_BASE_URL = "http://127.0.0.1:8000/api"


class APIClient:
    """Async client for Django API calls"""

    @staticmethod
    async def _make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to Django API"""
        url = f"{API_BASE_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, params=data) as response:
                        response.raise_for_status()
                        return await response.json()
                elif method.upper() == "POST":
                    async with session.post(url, json=data) as response:
                        response.raise_for_status()
                        return await response.json()
                else:
                    raise ValueError(f"Unsupported method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise Exception(f"Failed to connect to backend: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            raise

    # ============================================
    # USER ENDPOINTS
    # ============================================

    @staticmethod
    async def get_or_create_user(telegram_id: int, full_name: str, username: Optional[str] = None,
                                 role: str = "student") -> Dict:
        """Get or create user"""
        data = {
            "telegram_id": telegram_id,
            "full_name": full_name,
            "username": username,
            "role": role
        }
        return await APIClient._make_request("POST", "/users/get_or_create/", data)

    # ============================================
    # TEST CREATION ENDPOINTS
    # ============================================

    @staticmethod
    async def confirm_test(teacher_id: int, prompt: str, context: Optional[Dict] = None) -> Dict:
        """
        Step 1: Parse and confirm test parameters

        Returns:
        {
            "topic": "biology",
            "question_count": 10,
            "difficulty": "easy",
            "language": "english",
            "description": "Generate 10 easy biology questions in English"
        }
        """
        data = {
            "teacher_id": teacher_id,
            "prompt": prompt
        }
        if context:
            data["context"] = context

        return await APIClient._make_request("POST", "/tests/confirm/", data)

    @staticmethod
    async def generate_test(teacher_id: int, params: Dict) -> Dict:
        """
        Step 2: Generate test with confirmed parameters

        Args:
            params: Output from confirm_test endpoint

        Returns:
        {
            "test_id": 42,
            "title": "Biology Quiz",
            "description": "...",
            "question_count": 10,
            "message": "Test generated successfully!"
        }
        """
        data = {
            "teacher_id": teacher_id,
            **params
        }
        return await APIClient._make_request("POST", "/tests/generate/", data)

    @staticmethod
    async def get_test_preview(test_id: int) -> Dict:
        """Get test preview with all questions"""
        return await APIClient._make_request("GET", f"/tests/{test_id}/preview/")

    @staticmethod
    async def publish_test(test_id: int, settings: Optional[Dict] = None) -> Dict:
        """
        Publish test and get shareable link

        Returns:
        {
            "access_token": "abc123",
            "bot_link": "https://t.me/YourBot?start=test_abc123",
            ...
        }
        """
        data = settings or {}
        return await APIClient._make_request("POST", f"/tests/{test_id}/publish/", data)

    @staticmethod
    async def get_teacher_tests(teacher_id: int) -> Dict:
        """Get list of teacher's tests"""
        return await APIClient._make_request("GET", f"/tests/?teacher_id={teacher_id}")

    @staticmethod
    async def get_test_statistics(test_id: int) -> Dict:
        """
        Get detailed statistics for a test

        Returns:
        {
            "total_students": 15,
            "average_score": 7.2,
            "pass_rate": 75.0,
            "top_students": [...]
        }
        """
        return await APIClient._make_request("GET", f"/tests/{test_id}/statistics/")

    # ============================================
    # STUDENT TEST TAKING ENDPOINTS
    # ============================================

    @staticmethod
    async def start_attempt(access_token: str, telegram_id: int) -> Dict:
        """
        Start a new test attempt

        Returns:
        {
            "attempt_id": 100,
            "current_question": {...},
            "question_index": 0,
            "total_questions": 10
        }
        """
        data = {"telegram_id": telegram_id}
        logger.info(f"Starting attempt: token={access_token}, telegram_id={telegram_id}, data={data}")

        try:
            result = await APIClient._make_request("POST", f"/assignments/{access_token}/start_attempt/", data)
            logger.info(f"Start attempt successful: {result}")
            return result
        except Exception as e:
            logger.error(f"Start attempt failed: {e}")
            raise

    @staticmethod
    async def submit_answer(attempt_id: int, question_id: int, selected_option: int) -> Dict:
        """
        Submit answer for a question

        Returns:
        {
            "answer_saved": true,
            "is_correct": true,
            "points_earned": 1,
            "next_question": {...} or null if finished,
            "test_completed": false
        }
        """
        data = {
            "question_id": question_id,
            "selected_option": selected_option
        }

        logger.info(
            f"Submitting answer: attempt_id={attempt_id}, question_id={question_id}, selected_option={selected_option}, data={data}")

        try:
            result = await APIClient._make_request("POST", f"/attempts/{attempt_id}/submit_answer/", data)
            logger.info(f"Answer submitted successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Submit answer failed: {e}")
            raise

    @staticmethod
    async def finish_attempt(attempt_id: int) -> Dict:
        """
        Finish attempt and get results

        Returns:
        {
            "attempt_id": 100,
            "score": 8,
            "total": 10,
            "percentage": 80.0,
            "rank": 3,
            "total_students": 25
        }
        """
        return await APIClient._make_request("POST", f"/attempts/{attempt_id}/finish/")

    @staticmethod
    async def review_attempt(attempt_id: int) -> Dict:
        """
        Get attempt review with correct answers

        Returns:
        {
            "attempt": {...},
            "review": [
                {
                    "question": "...",
                    "your_answer": 1,
                    "correct_answer": 2,
                    "is_correct": false
                }
            ]
        }
        """
        return await APIClient._make_request("GET", f"/attempts/{attempt_id}/review/")

    # ============================================
    # LEADERBOARD ENDPOINTS
    # ============================================

    @staticmethod
    async def get_leaderboard(access_token: str) -> Dict:
        """
        Get leaderboard for an assignment

        Returns:
        {
            "assignment": {...},
            "leaderboard": [
                {
                    "student_name": "...",
                    "score": 10,
                    "rank": 1
                }
            ]
        }
        """
        return await APIClient._make_request("GET", f"/assignments/{access_token}/leaderboard/")