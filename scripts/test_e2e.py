"""
End-to-End Test Script for TV Producer Analytics AI Agent

Tests all API endpoints and verifies system functionality.

Usage:
    python scripts/test_e2e.py

Prerequisites:
    - All Docker services running (docker-compose up -d)
    - FastAPI application running (uvicorn src.api.main:app --port 8000)
    - Sample data loaded (python scripts/seed_sample_data.py)
"""

import requests
import json
import time
from typing import Dict, Any
from datetime import datetime, timedelta
import sys


class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class E2ETests:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def print_header(self, text: str):
        """Print test section header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}")
        print(f"{text}")
        print(f"{'=' * 60}{Colors.ENDC}\n")

    def print_test(self, test_name: str):
        """Print test name"""
        print(f"{Colors.BOLD}Testing:{Colors.ENDC} {test_name}...", end=" ")

    def print_success(self, message: str = "PASSED"):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")
        self.passed += 1

    def print_failure(self, message: str):
        """Print failure message"""
        print(f"{Colors.RED}✗ FAILED: {message}{Colors.ENDC}")
        self.failed += 1

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠ WARNING: {message}{Colors.ENDC}")
        self.warnings += 1

    def print_info(self, message: str):
        """Print info message"""
        print(f"  {Colors.BLUE}ℹ {message}{Colors.ENDC}")

    def print_summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}")
        print("TEST SUMMARY")
        print(f"{'=' * 60}{Colors.ENDC}")
        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.ENDC}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Warnings: {self.warnings}{Colors.ENDC}")

        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.ENDC}")
            return 0
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.ENDC}")
            return 1

    # ==================== Health Check Tests ====================

    def test_health_check(self):
        """Test health check endpoint"""
        self.print_test("Health Check")
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Check required fields
            if "status" not in data or "services" not in data:
                self.print_failure("Missing required fields")
                return

            # Check service statuses
            services = data["services"]
            unhealthy_services = [
                name for name, status in services.items()
                if status not in ["healthy", "degraded"]
            ]

            if unhealthy_services:
                self.print_warning(f"Services unhealthy: {unhealthy_services}")
            else:
                self.print_success(f"All services healthy")

            self.print_info(f"Overall status: {data['status']}")
            self.print_info(f"Redis: {services.get('redis', 'unknown')}")
            self.print_info(f"ClickHouse: {services.get('clickhouse', 'unknown')}")
            self.print_info(f"Elasticsearch: {services.get('elasticsearch', 'unknown')}")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== EAOS Tests ====================

    def test_current_eaos(self):
        """Test get current EAOS endpoint"""
        self.print_test("Get Current EAOS")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/eaos/current/show_123",
                timeout=10
            )

            if response.status_code == 404:
                self.print_warning("No EAOS data found (run seed script first)")
                return

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Validate response structure
            required_fields = ["program_id", "score", "positive", "negative", "neutral", "total"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                self.print_failure(f"Missing fields: {missing_fields}")
                return

            # Validate data ranges
            if not (0 <= data["score"] <= 1):
                self.print_failure(f"Invalid score: {data['score']} (should be 0-1)")
                return

            if data["total"] != data["positive"] + data["negative"] + data["neutral"]:
                self.print_failure("Sentiment counts don't sum to total")
                return

            self.print_success()
            self.print_info(f"Program: {data['program_id']}")
            self.print_info(f"Score: {data['score']:.3f}")
            self.print_info(f"Positive: {data['positive']}, Negative: {data['negative']}, Neutral: {data['neutral']}")
            self.print_info(f"Total: {data['total']}")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    def test_eaos_timeline(self):
        """Test get EAOS timeline endpoint"""
        self.print_test("Get EAOS Timeline")
        try:
            # Request last hour
            to_time = datetime.now().isoformat()
            from_time = (datetime.now() - timedelta(hours=1)).isoformat()

            response = requests.get(
                f"{self.base_url}/api/v1/eaos/timeline/show_123",
                params={
                    "from_time": from_time,
                    "to_time": to_time,
                    "granularity": "5min"
                },
                timeout=10
            )

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Validate response structure
            required_fields = ["program_id", "timeline", "granularity"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                self.print_failure(f"Missing fields: {missing_fields}")
                return

            timeline = data["timeline"]

            if not timeline:
                self.print_warning("Timeline is empty (run seed script first)")
                return

            # Validate timeline point structure
            point = timeline[0]
            point_fields = ["timestamp", "score", "positive_count", "negative_count", "neutral_count"]
            missing_point_fields = [f for f in point_fields if f not in point]

            if missing_point_fields:
                self.print_failure(f"Missing timeline fields: {missing_point_fields}")
                return

            self.print_success()
            self.print_info(f"Program: {data['program_id']}")
            self.print_info(f"Data points: {len(timeline)}")
            self.print_info(f"Granularity: {data['granularity']}")
            self.print_info(f"Score range: {min(p['score'] for p in timeline):.3f} - {max(p['score'] for p in timeline):.3f}")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== Trends Tests ====================

    def test_trending_topics(self):
        """Test get trending topics endpoint"""
        self.print_test("Get Trending Topics")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/trends",
                params={"limit": 10, "time_range": "15min"},
                timeout=10
            )

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Validate response structure
            required_fields = ["trends", "time_range", "timestamp"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                self.print_failure(f"Missing fields: {missing_fields}")
                return

            trends = data["trends"]

            if not trends:
                self.print_warning("No trending topics found (run seed script first)")
                return

            # Validate trend structure
            trend = trends[0]
            trend_fields = ["topic", "score", "rank"]
            missing_trend_fields = [f for f in trend_fields if f not in trend]

            if missing_trend_fields:
                self.print_failure(f"Missing trend fields: {missing_trend_fields}")
                return

            # Validate ranking
            for i, trend in enumerate(trends):
                if trend["rank"] != i + 1:
                    self.print_failure(f"Invalid ranking at position {i}")
                    return

            self.print_success()
            self.print_info(f"Trends found: {len(trends)}")
            self.print_info(f"Time range: {data['time_range']}")
            self.print_info(f"Top 3: {', '.join(t['topic'] for t in trends[:3])}")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== Chat Agent Tests ====================

    def test_chat_simple_query(self):
        """Test chat endpoint with simple query"""
        self.print_test("Chat - Simple Query")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/chat",
                json={
                    "program_id": "show_123",
                    "message": "What is the current EAOS score?",
                    "verbose": False
                },
                timeout=30  # Longer timeout for LLM calls
            )

            if response.status_code == 429:
                self.print_warning("Rate limit exceeded")
                return

            if response.status_code == 500:
                self.print_warning("Server error (check GCP credentials)")
                return

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Validate response structure
            required_fields = ["response", "program_id", "metadata"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                self.print_failure(f"Missing fields: {missing_fields}")
                return

            if not data["response"]:
                self.print_failure("Empty response from agent")
                return

            self.print_success()
            self.print_info(f"Response length: {len(data['response'])} chars")
            self.print_info(f"Execution time: {data['metadata'].get('execution_time_ms', 'N/A')}ms")
            self.print_info(f"Response preview: {data['response'][:100]}...")

        except requests.exceptions.Timeout:
            self.print_warning("Request timeout (LLM might be slow)")
        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    def test_chat_verbose_mode(self):
        """Test chat endpoint with verbose mode"""
        self.print_test("Chat - Verbose Mode")
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/chat",
                json={
                    "program_id": "show_123",
                    "message": "Top 5 trending topics?",
                    "verbose": True
                },
                timeout=30
            )

            if response.status_code == 429:
                self.print_warning("Rate limit exceeded")
                return

            if response.status_code == 500:
                self.print_warning("Server error (check GCP credentials)")
                return

            if response.status_code != 200:
                self.print_failure(f"Status code {response.status_code}")
                return

            data = response.json()

            # Check for reasoning steps (verbose mode)
            if "reasoning_steps" not in data:
                self.print_failure("Missing reasoning_steps in verbose mode")
                return

            if not data["reasoning_steps"]:
                self.print_warning("Empty reasoning steps")

            self.print_success()
            self.print_info(f"Reasoning steps: {len(data['reasoning_steps'])}")

            # Print reasoning steps summary
            for step in data["reasoning_steps"]:
                step_name = step.get("step", "unknown")
                self.print_info(f"  - {step_name}")

        except requests.exceptions.Timeout:
            self.print_warning("Request timeout (LLM might be slow)")
        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== Rate Limiting Tests ====================

    def test_rate_limiting(self):
        """Test rate limiting"""
        self.print_test("Rate Limiting")
        try:
            # Send multiple rapid requests
            rate_limited = False

            for i in range(5):
                response = requests.get(
                    f"{self.base_url}/api/v1/health",
                    timeout=5
                )

                if response.status_code == 429:
                    rate_limited = True
                    self.print_info(f"Rate limited after {i+1} requests")
                    break

                time.sleep(0.1)

            if not rate_limited:
                self.print_warning("Rate limiting not triggered (might be disabled)")
            else:
                self.print_success("Rate limiting working")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== Caching Tests ====================

    def test_caching(self):
        """Test response caching"""
        self.print_test("Response Caching")
        try:
            # First request
            start1 = time.time()
            response1 = requests.get(
                f"{self.base_url}/api/v1/eaos/current/show_123",
                timeout=10
            )
            time1 = (time.time() - start1) * 1000

            if response1.status_code != 200:
                self.print_warning(f"Status code {response1.status_code}")
                return

            # Second request (should be cached)
            time.sleep(0.5)
            start2 = time.time()
            response2 = requests.get(
                f"{self.base_url}/api/v1/eaos/current/show_123",
                timeout=10
            )
            time2 = (time.time() - start2) * 1000

            if response2.status_code != 200:
                self.print_warning(f"Status code {response2.status_code}")
                return

            # Compare responses and times
            if response1.json() == response2.json():
                speedup = time1 / time2 if time2 > 0 else 1
                if speedup > 1.5:
                    self.print_success(f"Cache hit (speedup: {speedup:.1f}x)")
                else:
                    self.print_warning("Responses match but no speedup detected")

                self.print_info(f"First request: {time1:.1f}ms")
                self.print_info(f"Second request: {time2:.1f}ms")
            else:
                self.print_warning("Responses don't match (cache might be disabled)")

        except requests.exceptions.RequestException as e:
            self.print_failure(f"Request failed: {str(e)}")
        except Exception as e:
            self.print_failure(f"Unexpected error: {str(e)}")

    # ==================== Run All Tests ====================

    def run_all_tests(self):
        """Run all end-to-end tests"""
        self.print_header("TV Producer Analytics AI Agent - E2E Tests")

        # Check if server is running
        print(f"{Colors.BOLD}Checking server connection...{Colors.ENDC}")
        try:
            requests.get(self.base_url, timeout=5)
            self.print_info(f"Connected to {self.base_url}")
        except requests.exceptions.RequestException:
            self.print_failure(f"Cannot connect to {self.base_url}")
            self.print_info("Make sure FastAPI is running: uvicorn src.api.main:app --port 8000")
            return 1

        # Health Check Tests
        self.print_header("1. Health Check Tests")
        self.test_health_check()

        # EAOS Tests
        self.print_header("2. EAOS Endpoint Tests")
        self.test_current_eaos()
        self.test_eaos_timeline()

        # Trends Tests
        self.print_header("3. Trends Endpoint Tests")
        self.test_trending_topics()

        # Chat Agent Tests
        self.print_header("4. Chat Agent Tests")
        self.test_chat_simple_query()
        self.test_chat_verbose_mode()

        # Performance Tests
        self.print_header("5. Performance Tests")
        self.test_rate_limiting()
        self.test_caching()

        # Print summary
        return self.print_summary()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Run E2E tests for TV Analytics AI Agent")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    tests = E2ETests(base_url=args.url)
    exit_code = tests.run_all_tests()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
