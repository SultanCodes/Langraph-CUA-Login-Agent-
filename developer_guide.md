
# Login Scraper Agent Developer Guide

This document provides detailed technical information for developers working with the Login Scraper Agent.

## Architecture Overview

The Login Scraper Agent is built using the following components:

1. **LangGraph CUA**: A wrapper around OpenAI's computer use model that provides a graph-based agent framework
2. **Scrapabara**: A service providing virtual desktop environments for AI agents
3. **FastAPI**: A high-performance web framework for building APIs
4. **LangSmith**: An optional tracing and debugging tool for LLM applications

### Component Interaction Flow


User Request -> FastAPI API -> LangGraph Agent -> OpenAI Computer Use Model -> Scrapabara VM -> Website
                                                                                    |
                                                                                    v
User <- FastAPI Response <- HTML Content <- LangGraph Agent <- Computer Use Actions


## Agent Details

The LangGraph CUA agent operates in a simple loop:

1. **Call Model**: Sends the current state to the OpenAI computer use model
2. **Take Computer Action**: Executes the actions requested by the model in the Scrapabara VM
3. **Repeat**: Continues this loop until the model completes the task

## Implementation Highlights

### System Prompting

The system prompt is critical for guiding the agent's behavior. Key aspects:

```python
system_message = """
You are an advanced computer use AI assistant specialized in accessing content behind login pages.

Your task is to:
1. Navigate to the specific URL provided by the user
2. Identify the login form (which might be on another page after redirects)
3. Enter the username and password provided
4. Submit the login form
5. Verify successful login
6. Extract the full HTML content of the target page after login

Important instructions:
- Handle redirects automatically
- If login fails, try alternative login forms if available
- Extract the complete HTML document using 'document.documentElement.outerHTML'
...
"""
```

### HTML Extraction

Several methods are employed to reliably extract HTML from agent responses:

```python
def extract_html_from_response(response: str) -> Optional[str]:
    """
    Extract HTML content from the agent's response.
    Handles different ways the agent might format the HTML.
    """
    # Try to extract HTML from code blocks
    if "```html" in response:
        parts = response.split("```html", 1)
        if len(parts) > 1 and "```" in parts[1]:
            return parts[1].split("```", 1)[0].strip()

    # Additional extraction methods...
```

### Job Management

The system uses a simple in-memory job store to track progress:

```python
# Storage for job tracking
scraping_jobs = {}
```

In a production environment, this should be replaced with a persistent database.

## Customization Points

### Extending Login Methods

To support additional login methods (e.g., OAuth):

1. Enhance the system prompt with specific instructions
2. Add specialized error handling for the new login flows

### Supporting Advanced Authentication

For sites with more complex authentication:

1. Modify the agent timeout settings (longer timeouts)
2. Add additional extraction and verification steps
3. Implement custom pre-processing or post-processing logic

### Performance Optimization

For high-throughput scenarios:

1. Replace in-memory job storage with a database
2. Implement job queuing and rate limiting
3. Add caching for frequently accessed sites

## Troubleshooting Common Issues

### Login Detection Failures

If the agent struggles to find login forms:

1. Check if the site uses non-standard form elements
2. Review the agent's logs for what elements it's finding
3. Enhance the system prompt with more specific guidance

### HTML Extraction Issues

If the agent fails to extract HTML:

1. Check if the site dynamically loads content after login
2. Review the extraction logic for edge cases
3. Add delays after login to ensure content loads fully

### Browser Automation Problems

If browser actions fail:

1. Check if the site has anti-automation measures
2. Review VM capabilities and limitations
3. Try simplifying the task or breaking it down into smaller steps

## API Extension Guide

Adding new endpoints to the API:

```python
@app.post("/api/new-endpoint")
async def new_endpoint(data: YourDataModel, background_tasks: BackgroundTasks):
    # Implementation
    return {"status": "success"}
```

## Testing Strategy

### Unit Testing

Each component has dedicated tests focusing on:

1. HTML extraction logic
2. Job status management
3. API endpoint behavior

### Integration Testing

Tests that validate:

1. End-to-end job creation and completion
2. Agent execution flow
3. Error handling and reporting

### Stress Testing

The `stress_test.sh` script conducts comprehensive tests against:

1. Known-good login sites
2. Sites with expected failure modes (CAPTCHA, Cloudflare, etc.)
3. Edge cases (empty credentials, malformed URLs)

## Future Enhancements

1. **Session Management**: Store and reuse login sessions to reduce load
2. **Headless Mode**: Option to run without VM visualization for better performance
3. **Site-Specific Customization**: Allow per-site configuration for challenging websites
4. **Rate Limiting**: Built-in protection against overloading target sites
5. **Credential Management**: Secure storage and rotation of credentials
```
