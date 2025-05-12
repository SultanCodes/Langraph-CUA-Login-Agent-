# Login Scraper Agent

A general-purpose AI agent that can fetch content behind login-protected pages using computer vision and browser automation via LLM agents.

## Overview

This project implements a solution for accessing content behind login pages using OpenAI's computer use capabilities through the LangGraph framework. The agent can:

1. Navigate to any URL provided by the user
2. Identify and complete login forms using provided credentials
3. Extract the complete HTML content after successful login
4. Handle redirects and complex login flows automatically
5. Provide detailed logging and visual monitoring of the agent's actions

## Features

- **Dynamic URL Handling**: Works with any login-protected site that doesn't implement anti-bot protections
- **Visual Navigation**: Uses AI to visually navigate websites like a human would
- **Automatic Login Detection**: Identifies login forms without prior knowledge of the site structure
- **Real-time Monitoring**: Watch the agent's actions through a virtual machine interface
- **Comprehensive Logging**: Detailed logging of each step the agent takes
- **REST API**: Simple API for integration with other systems
- **User-friendly Interface**: Web UI for non-technical users to test the system

## Installation

### Prerequisites

- Docker and Docker Compose
- OpenAI API key with access to the computer use model
- Scrapabara API key (for VM access)
- Optional: LangSmith API key (for enhanced tracing)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/login-scraper-agent.git
   cd login-scraper-agent
   ```

2. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   SCRAPERABARA_API_KEY=your_scrapabara_api_key
   LANGSMITH_API_KEY=your_langsmith_api_key  # optional
   ```

3. Build and start the Docker container:
   ```bash
   docker-compose up -d
   ```

4. Access the web interface at http://localhost:8000

## Usage

### Web Interface

1. Open http://localhost:8000 in your browser
2. Enter the URL of the login-protected page
3. Enter the username and password
4. Click "Start Scraping"
5. Monitor the progress and view the extracted HTML

### REST API

#### Start a scraping job

```bash
curl -X POST http://localhost:8000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/login",
    "username": "your_username",
    "password": "your_password"
  }'
```

Response:
```json
{
  "job_id": "job_123_1589237845",
  "status": "pending"
}
```

#### Check job status

```bash
curl http://localhost:8000/api/jobs/job_123_1589237845
```

Response (in progress):
```json
{
  "job_id": "job_123_1589237845",
  "status": "running",
  "vm_url": "https://vm.scrapabara.com/session/abc123",
  "started_at": "2025-05-12T14:23:45.123456",
  "completed_at": null
}
```

Response (completed):
```json
{
  "job_id": "job_123_1589237845",
  "status": "completed",
  "vm_url": "https://vm.scrapabara.com/session/abc123",
  "html_content": "<html>...</html>",
  "started_at": "2025-05-12T14:23:45.123456",
  "completed_at": "2025-05-12T14:24:15.654321",
  "langsmith_trace_url": "https://smith.langchain.com/traces/abc123"
}
```

## Testing

### Running Unit Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run the tests
python -m pytest tests/
```

### Running Stress Tests

```bash
# Make the script executable
chmod +x stress_test.sh

# Run the stress tests (requires a running instance)
./stress_test.sh
```

## Known Limitations

1. Cannot bypass CAPTCHA challenges
2. Cannot bypass Cloudflare and similar bot protection systems
3. Cannot handle two-factor authentication
4. May struggle with highly dynamic JavaScript-heavy sites
5. Login sessions are not persisted between runs

## Implementation Details

### Architecture

The system consists of several key components:

1. **LangGraph Kua Agent**: A wrapped version of OpenAI's computer use model
2. **Scrapabara VM Interface**: Provides browser automation capabilities
3. **FastAPI Backend**: Handles API requests and job management
4. **Web Interface**: User-friendly frontend for testing

### Agent Workflow

1. The agent receives a URL and credentials
2. It navigates to the provided URL
3. It identifies login elements and enters credentials
4. After successful login, it extracts the complete HTML
5. The HTML is returned to the user

### Monitoring and Debugging

- **VM URL**: Watch the agent's actions in real-time
- **LangSmith Traces**: View detailed execution traces (if configured)
- **Logging**: Comprehensive logs for troubleshooting

## License

MIT

## Acknowledgements

- [LangGraph](https://github.com/langchain-ai/langgraph) for the agent framework
- [Scrapabara](https://scrapabara.com) for virtual machine access
- [OpenAI](https://openai.com) for the computer use model
