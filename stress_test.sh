#!/bin/bash

# Login Scraper Agent - Integration and Stress Tests
# This script runs comprehensive tests to validate the agent's capabilities
# and its handling of various edge cases

# Ensure we exit on any command error
set -e

echo "===== Running Login Scraper Agent Stress Tests ====="

# Define test cases
declare -a SUCCESSFUL_CASES=(
  "https://login-demo.netlify.app/|user|password"
  "https://the-internet.herokuapp.com/login|tomsmith|SuperSecretPassword!"
  "https://practicetestautomation.com/practice-test-login/|student|Password123"
)

declare -a FAILING_CASES=(
  # CAPTCHA test case
  "https://www.google.com/recaptcha/api2/demo|test|test"
  
  # Cloudflare protected site
  "https://www.cloudflare.com/|test|test"
  
  # Invalid credentials
  "https://the-internet.herokuapp.com/login|invalid|wrongpassword"
  
  # Non-existent site
  "https://this-site-does-not-exist-abc123xyz456.com/|test|test"
)

# Function to run a test case
run_test() {
  local test_data=$1
  local expected_outcome=$2
  
  # Parse test data
  IFS='|' read -r url username password <<< "$test_data"
  
  echo ""
  echo "🧪 Testing URL: $url"
  echo "   Username: $username"
  echo "   Password: ${password:0:1}**** (masked)"
  echo "   Expected outcome: $expected_outcome"
  
  # Call the API
  local response=$(curl -s -X POST http://localhost:8000/api/scrape \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$url\", \"username\": \"$username\", \"password\": \"$password\"}")
  
  # Get job ID
  local job_id=$(echo $response | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
  
  if [ -z "$job_id" ]; then
    echo "❌ Error: Failed to get job ID"
    return 1
  fi
  
  echo "   Job ID: $job_id"
  
  # Poll for job completion
  local max_attempts=30
  local attempt=0
  local status="pending"
  
  while [ "$status" = "pending" ] || [ "$status" = "running" ]; do
    sleep 2
    attempt=$((attempt+1))
    
    echo -n "   Polling status... attempt $attempt/$max_attempts"
    
    local job_status=$(curl -s -X GET http://localhost:8000/api/jobs/$job_id)
    status=$(echo $job_status | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    
    echo -ne "\r"
    
    if [ $attempt -ge $max_attempts ]; then
      echo "❌ Error: Test timed out after $max_attempts attempts"
      return 1
    fi
  done
  
  echo "   Final status: $status"
  
  # Check if outcome matches expected
  if [ "$expected_outcome" = "success" ] && [ "$status" = "completed" ]; then
    echo "✅ Test PASSED: Successfully accessed content behind login"
    
    # Check if HTML content is present
    if echo $job_status | grep -q '"html_content":'; then
      local html_size=$(echo $job_status | grep -o '"html_content":"[^"]*' | wc -c)
      echo "   HTML content size: approximately $((html_size - 16)) characters"
    else
      echo "❌ Warning: No HTML content found in response"
    fi
    
    return 0
  elif [ "$expected_outcome" = "failure" ] && [ "$status" = "failed" ]; then
    echo "✅ Test PASSED: Failed as expected"
    
    # Extract error message
    local error_msg=$(echo $job_status | grep -o '"error":"[^"]*' | cut -d'"' -f4)
    echo "   Error message: $error_msg"
    
    return 0
  else
    echo "❌ Test FAILED: Expected $expected_outcome but got $status"
    return 1
  fi
}

# Run successful test cases
echo ""
echo "===== Testing Sites That Should Succeed ====="
success_count=0
total_success_cases=${#SUCCESSFUL_CASES[@]}

for test_case in "${SUCCESSFUL_CASES[@]}"; do
  if run_test "$test_case" "success"; then
    success_count=$((success_count+1))
  fi
done

# Run failing test cases
echo ""
echo "===== Testing Sites That Should Fail ====="
failure_count=0
total_failure_cases=${#FAILING_CASES[@]}

for test_case in "${FAILING_CASES[@]}"; do
  if run_test "$test_case" "failure"; then
    failure_count=$((failure_count+1))
  fi
done

# Print summary
echo ""
echo "===== Test Summary ====="
echo "Success cases: $success_count/$total_success_cases"
echo "Failure cases: $failure_count/$total_failure_cases"
echo "Total: $((success_count + failure_count))/$((total_success_cases + total_failure_cases))"

if [ $success_count -eq $total_success_cases ] && [ $failure_count -eq $total_failure_cases ]; then
  echo "✅ All tests passed successfully!"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi
