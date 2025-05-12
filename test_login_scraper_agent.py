# Check job status and error
        job = login_scraper_agent.scraping_jobs[job_id]
        self.assertEqual(job.status, "failed")
        self.assertIn("CAPTCHA", job.error)
    
    async def test_process_scraping_job_exception(self):
        """Test handling exceptions during job processing."""
        # Mock the agent to raise an exception
        self.mock_astream.side_effect = Exception("Test error")
        
        # Process a job
        job_id = "test_exception_job"
        await login_scraper_agent.process_scraping_job(
            job_id, "https://example.com", "testuser", "testpass"
        )
        
        # Check job status and error
        job = login_scraper_agent.scraping_jobs[job_id]
        self.assertEqual(job.status, "failed")
        self.assertIn("Test error", job.error)


# Integration tests with actual API endpoints
class TestLoginScraperAgentIntegration(unittest.TestCase):
    """Integration tests for the Login Scraper Agent API."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear existing jobs
        login_scraper_agent.scraping_jobs.clear()
        
        # Create a mock background task processor
        async def mock_process(job_id, url, username, password):
            job = login_scraper_agent.scraping_jobs[job_id]
            job.status = "completed"
            job.vm_url = "https://test-vm.example.com"
            job.html_content = f"<html><body>Content from {url}</body></html>"
            job.completed_at = datetime.now().isoformat()
        
        # Patch the background task
        self.patcher = patch('login_scraper_agent.process_scraping_job', mock_process)
        self.mock_process = self.patcher.start()
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()
    
    def test_end_to_end_flow(self):
        """Test the end-to-end flow of creating a job and getting results."""
        # Create a job
        response = client.post(
            "/api/scrape",
            json={
                "url": "https://example.com",
                "username": "testuser",
                "password": "testpass"
            }
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        
        # Give background task time to process
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.sleep(0.1))
        
        # Get job status
        response = client.get(f"/api/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["vm_url"], "https://test-vm.example.com")
        self.assertEqual(data["html_content"], "<html><body>Content from https://example.com</body></html>")


# Negative test cases for edge cases
class TestLoginScraperAgentNegative(unittest.TestCase):
    """Negative test cases for the Login Scraper Agent."""
    
    def test_malformed_url(self):
        """Test handling of malformed URLs."""
        response = client.post(
            "/api/scrape",
            json={
                "url": "not_a_url",
                "username": "testuser",
                "password": "testpass"
            }
        )
        # The API should accept it, but the agent should report failure
        self.assertEqual(response.status_code, 200)
    
    def test_empty_credentials(self):
        """Test handling of empty credentials."""
        response = client.post(
            "/api/scrape",
            json={
                "url": "https://example.com",
                "username": "",
                "password": ""
            }
        )
        # The API should accept it, but the agent should report failure
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
