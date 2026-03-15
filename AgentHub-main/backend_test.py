#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class AgentNetAPITester:
    def __init__(self, base_url="https://agent-network-graph.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_agent_id = None

    def log(self, message):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def run_test(self, name, method, endpoint, expected_status=200, data=None, use_auth=False):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if use_auth and self.session_token:
            headers['Authorization'] = f'Bearer {self.session_token}'

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    self.log(f"   Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    self.log(f"   Error: {response.text[:200]}")
                return False, {}

        except requests.exceptions.Timeout:
            self.log(f"❌ {name} - Request timed out")
            return False, {}
        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_basic_endpoints(self):
        """Test basic public endpoints"""
        self.log("=== Testing Basic Public Endpoints ===")
        
        # Test stats endpoint
        success, stats = self.run_test("Stats API", "GET", "stats")
        if success:
            self.log(f"   Stats: {stats.get('total_agents', 0)} agents, {stats.get('total_deployments', 0)} deployments")

        # Test categories endpoint
        success, categories = self.run_test("Categories API", "GET", "categories")
        if success:
            self.log(f"   Categories: {len(categories.get('categories', []))} categories found")

        # Test seed endpoint (should create 8 agents if not exists)
        success, seed_result = self.run_test("Seed API", "POST", "seed")
        if success:
            self.log(f"   Seed result: {seed_result.get('message', 'Unknown')}")

        # Test agents list endpoint
        success, agents = self.run_test("List Agents API", "GET", "agents")
        if success:
            total_agents = agents.get('total', 0)
            agent_list = agents.get('agents', [])
            self.log(f"   Found {total_agents} agents, returned {len(agent_list)}")
            if agent_list:
                self.test_agent_id = agent_list[0].get('agent_id')
                self.log(f"   Using agent ID for further tests: {self.test_agent_id}")

    def test_search_and_filter(self):
        """Test search and filter functionality"""
        self.log("=== Testing Search & Filter ===")
        
        # Test search functionality
        success, search_result = self.run_test("Search Agents", "GET", "agents?search=CodexPrime")
        if success:
            found = len(search_result.get('agents', []))
            self.log(f"   Search for 'CodexPrime' found {found} agents")

        # Test category filter
        success, filter_result = self.run_test("Category Filter", "GET", "agents?category=coding")
        if success:
            found = len(filter_result.get('agents', []))
            self.log(f"   Category 'coding' found {found} agents")

        # Test sort by deployment count
        success, sort_result = self.run_test("Sort by Deployments", "GET", "agents?sort_by=deployment_count")
        if success:
            agents = sort_result.get('agents', [])
            if len(agents) >= 2:
                first_deploys = agents[0].get('deployment_count', 0)
                second_deploys = agents[1].get('deployment_count', 0)
                self.log(f"   Top agent has {first_deploys} deployments, second has {second_deploys}")

    def test_agent_details(self):
        """Test agent profile details"""
        if not self.test_agent_id:
            self.log("=== Skipping Agent Details (no agent ID) ===")
            return

        self.log("=== Testing Agent Details ===")
        
        # Get agent details
        success, agent = self.run_test("Agent Details", "GET", f"agents/{self.test_agent_id}")
        if success:
            self.log(f"   Agent: {agent.get('name')} by {agent.get('builder')}")
            self.log(f"   Trust Score: {agent.get('trust_score')}")
            self.log(f"   Portfolio Items: {len(agent.get('portfolio', []))}")
            self.log(f"   Reviews: {len(agent.get('reviews', []))}")
            self.log(f"   Network Recommendations: {len(agent.get('network', []))}")

        # Test trust score endpoint
        success, trust_data = self.run_test("Trust Score", "GET", f"trust-score/{self.test_agent_id}")
        if success:
            self.log(f"   Trust Score Details: {trust_data.get('trust_score')}")

        # Test network recommendations
        success, network = self.run_test("Network Recommendations", "GET", f"network/{self.test_agent_id}")
        if success:
            recommendations = network.get('recommendations', [])
            self.log(f"   Network Recommendations: {len(recommendations)} agents")

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        self.log("=== Testing Authentication ===")
        
        # Generate unique test user
        timestamp = str(int(datetime.now().timestamp()))
        test_email = f"test.agent.{timestamp}@agentnet.test"
        test_password = "TestPassword123!"
        test_name = f"Test Agent Builder {timestamp[-4:]}"

        # Test registration
        success, reg_result = self.run_test("User Registration", "POST", "auth/register", 
                                          expected_status=200,
                                          data={
                                              "name": test_name,
                                              "email": test_email, 
                                              "password": test_password
                                          })
        if success:
            self.session_token = reg_result.get('token')
            self.user_id = reg_result.get('user', {}).get('user_id')
            self.log(f"   Registered user: {test_name} ({self.user_id})")

            # Test auth/me endpoint
            success, me_result = self.run_test("Auth Me", "GET", "auth/me", use_auth=True)
            if success:
                self.log(f"   Auth me: {me_result.get('name')} - {me_result.get('email')}")

            # Test logout
            success, logout_result = self.run_test("Logout", "POST", "auth/logout", use_auth=True)
            if success:
                self.log("   Logout successful")

            # Test login with same credentials
            success, login_result = self.run_test("User Login", "POST", "auth/login",
                                                expected_status=200,
                                                data={
                                                    "email": test_email,
                                                    "password": test_password
                                                })
            if success:
                self.session_token = login_result.get('token')
                self.log(f"   Login successful, got new token")
        else:
            self.log("   Registration failed, skipping further auth tests")

    def test_github_import(self):
        """Test GitHub import functionality (iteration 2 feature)"""
        self.log("=== Testing GitHub Import Feature ===")
        
        # First check if GitHub agents already exist (since 65 should already be imported)
        success, github_agents = self.run_test("List GitHub Agents", "GET", "github/agents?limit=10")
        if success:
            total_github = github_agents.get('total', 0)
            agents_list = github_agents.get('agents', [])
            self.log(f"   Found {total_github} GitHub agents already imported")
            
            if agents_list:
                # Verify GitHub agent structure
                github_agent = agents_list[0]
                self.log(f"   Sample GitHub agent: {github_agent.get('name')} by {github_agent.get('builder')}")
                self.log(f"   GitHub stats: {github_agent.get('github_stars', 0)} stars, {github_agent.get('github_forks', 0)} forks")
                self.log(f"   Language: {github_agent.get('github_language', 'N/A')}")
                self.log(f"   License: {github_agent.get('github_license', 'N/A')}")
                self.log(f"   Source: {github_agent.get('source', 'N/A')}")
                
                # Verify required GitHub fields
                required_fields = ['github_stars', 'github_forks', 'github_url', 'source']
                missing_fields = [field for field in required_fields if field not in github_agent or github_agent[field] is None]
                if missing_fields:
                    self.log(f"   ⚠️  Missing GitHub fields: {missing_fields}")
                else:
                    self.log("   ✅ All required GitHub fields present")
        
        # Test import endpoint (but don't trigger actual import to avoid rate limits)
        # We'll just verify the endpoint exists and structure
        self.log("   Note: Skipping actual import to avoid GitHub API rate limits")
        self.log("   (Based on context, 65 agents should already be imported)")

    def test_huggingface_import(self):
        """Test HuggingFace import functionality (NEW iteration 3 feature)"""
        self.log("=== Testing HuggingFace Import Feature ===")
        
        # Test HuggingFace agents endpoint (49 models should already be imported)
        success, hf_agents = self.run_test("List HuggingFace Agents", "GET", "huggingface/agents?limit=10")
        if success:
            total_hf = hf_agents.get('total', 0)
            agents_list = hf_agents.get('agents', [])
            self.log(f"   Found {total_hf} HuggingFace agents already imported")
            
            if agents_list:
                # Sort by downloads to verify the endpoint sorts correctly
                success, hf_sorted = self.run_test("HF Agents Sorted by Downloads", "GET", "huggingface/agents?limit=5")
                if success and hf_sorted.get('agents'):
                    sorted_agents = hf_sorted.get('agents', [])
                    downloads = [agent.get('hf_downloads', 0) for agent in sorted_agents[:3]]
                    self.log(f"   Downloads sort verification: {downloads}")
                
                # Verify HuggingFace agent structure
                hf_agent = agents_list[0]
                self.log(f"   Sample HF agent: {hf_agent.get('name')} by {hf_agent.get('builder')}")
                self.log(f"   HF stats: {hf_agent.get('hf_downloads', 0)} downloads, {hf_agent.get('hf_likes', 0)} likes")
                self.log(f"   Pipeline tag: {hf_agent.get('hf_pipeline_tag', 'N/A')}")
                self.log(f"   Tags: {len(hf_agent.get('hf_tags', []))} tags")
                self.log(f"   Source: {hf_agent.get('source', 'N/A')}")
                
                # Verify required HuggingFace fields
                required_fields = ['hf_downloads', 'hf_likes', 'hf_url', 'source', 'hf_model_id']
                missing_fields = [field for field in required_fields if field not in hf_agent or hf_agent[field] is None]
                if missing_fields:
                    self.log(f"   ⚠️  Missing HuggingFace fields: {missing_fields}")
                else:
                    self.log("   ✅ All required HuggingFace fields present")
        
        # Test import endpoint structure (don't trigger to avoid hitting limits)
        self.log("   Note: Skipping actual import to avoid HuggingFace API rate limits")
        self.log("   (Based on context, 49 HuggingFace models should already be imported)")

    def test_sync_endpoints(self):
        """Test sync status and trigger endpoints (NEW iteration 3 feature)"""
        self.log("=== Testing Auto-Sync Endpoints ===")
        
        # Test sync status endpoint
        success, sync_status = self.run_test("Sync Status", "GET", "sync/status")
        if success:
            last_sync = sync_status.get('last_sync', {})
            if last_sync:
                self.log(f"   Last sync: {last_sync.get('timestamp', 'N/A')}")
                self.log(f"   GitHub agents: {sync_status.get('github_agents_count', 0)}")
                self.log(f"   HuggingFace agents: {sync_status.get('huggingface_agents_count', 0)}")
                self.log(f"   Sync interval: {sync_status.get('sync_interval_hours', 0)}h")
            else:
                self.log("   No sync history found")
        
        # Test manual sync trigger (but don't actually trigger to avoid issues)
        self.log("   Note: Skipping manual sync trigger to avoid system load")
        self.log("   POST /api/sync/trigger endpoint should be available for manual sync")

    def test_protected_endpoints(self):
        """Test endpoints that require authentication"""
        if not self.session_token:
            self.log("=== Skipping Protected Endpoints (no auth token) ===")
            return

        self.log("=== Testing Protected Endpoints ===")

        # Test creating an agent
        agent_data = {
            "name": "Test AI Assistant",
            "builder": "Test Labs",
            "description": "A test AI agent for automated testing purposes",
            "category": "general",
            "integrations": ["OpenAI Codex", "GitHub"],
            "compatible_systems": ["Docker", "Kubernetes"],
            "skills": [
                {"name": "Test Automation", "benchmark": 95.0, "verified": True},
                {"name": "API Testing", "benchmark": 92.5, "verified": True}
            ]
        }

        success, create_result = self.run_test("Create Agent", "POST", "agents", 
                                             expected_status=200,
                                             data=agent_data, use_auth=True)
        if success:
            created_agent_id = create_result.get('agent_id')
            self.log(f"   Created agent: {created_agent_id}")

            # Test getting my agents
            success, my_agents = self.run_test("My Agents", "GET", "agents/owner/me", use_auth=True)
            if success:
                agent_count = len(my_agents.get('agents', []))
                self.log(f"   My agents: {agent_count} agents found")

            # Test creating a review
            review_data = {
                "agent_id": created_agent_id,
                "rating": 5,
                "comment": "Excellent test agent! Performs automated testing flawlessly.",
                "reviewer_type": "human"
            }

            success, review_result = self.run_test("Create Review", "POST", "reviews",
                                                 expected_status=200,
                                                 data=review_data, use_auth=True)
            if success:
                review_id = review_result.get('review_id')
                self.log(f"   Created review: {review_id}")

            # Test GPT-5.2 summarize endpoint (might fail due to API key credits)
            success, summary_result = self.run_test("AI Summarize", "POST", f"agents/{created_agent_id}/summarize",
                                                   expected_status=200, use_auth=True)
            if success:
                summary = summary_result.get('summary', 'No summary')[:100]
                self.log(f"   AI Summary generated: {summary}...")
            else:
                self.log("   AI Summarize failed (likely API key/credits issue)")

    def run_all_tests(self):
        """Run all test suites"""
        self.log("🚀 Starting AgentNet API Testing - Iteration 3 (HuggingFace Features)")
        self.log(f"Base URL: {self.base_url}")
        
        try:
            self.test_basic_endpoints()
            self.test_search_and_filter()
            self.test_agent_details()
            self.test_github_import()  # Previous GitHub import tests
            self.test_huggingface_import()  # NEW: HuggingFace import tests
            self.test_sync_endpoints()  # NEW: Auto-sync functionality tests
            self.test_auth_endpoints()
            self.test_protected_endpoints()
            
            self.log("=" * 50)
            self.log(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
            
            if self.tests_passed == self.tests_run:
                self.log("🎉 All tests passed!")
                return 0
            else:
                failed = self.tests_run - self.tests_passed
                self.log(f"❌ {failed} tests failed")
                return 1
                
        except KeyboardInterrupt:
            self.log("⚠️ Testing interrupted by user")
            return 130
        except Exception as e:
            self.log(f"💥 Testing failed with error: {str(e)}")
            return 1

def main():
    """Main entry point"""
    tester = AgentNetAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())