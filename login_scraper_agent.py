"""
Login Scraper Agent - A general-purpose AI agent for accessing content behind login pages

This module provides a complete implementation of an agent that can:
1. Navigate to any URL provided by the user
2. Identify and complete login forms using provided credentials
3. Extract the rendered HTML after successful login
4. Handle redirects and complex login flows
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from langsmith import Client
import logging
from dotenv import load_dotenv
from langraph_kua import create_kua
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("login_scraper_agent")

# Load environment variables
load_dotenv()

# Check for required API keys
required_keys = ["OPENAI_API_KEY", "SCRAPERABARA_API_KEY"]
missing_keys = [key for key in required_keys if not os.environ.get(key)]
if missing_keys:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_keys)}")

# Initialize LangSmith client if API key is available
langsmith_client = None
if os.environ.get("LANGSMITH_API_KEY"):
    langsmith_client = Client()

# Create the Kua agent
kua_graph = create_kua()

# Input models
class LoginCredentials(BaseModel):
    url: str
    username: str
    password: str
    
class ScrapingJob(BaseModel):
    job_id: str
    status: str
    vm_url: Optional[str] = None
    html_content: Optional[str] = None
    error: Optional[str] = None
    langsmith_trace_url: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None

# Storage for job tracking
scraping_jobs = {}

# FastAPI app
app = FastAPI(
    title="Login Scraper Agent API",
    description="API for accessing content behind login-protected pages using AI",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates
templates = Jinja2Templates(directory="templates")
os.makedirs("templates", exist_ok=True)

# Create HTML template for testing
with open("templates/index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Login Scraper Agent</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f7f9fc; }
        .container { max-width: 1000px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-top: 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #34495e; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #2980b9; }
        pre { background-color: #f8f9fa; padding: 15px; border-radius: 4px; overflow: auto; max-height: 400px; }
        .result { margin-top: 30px; }
        .result h2 { color: #2c3e50; }
        .vm-link { margin-bottom: 15px; }
        .vm-link a { color: #3498db; text-decoration: none; }
        .vm-link a:hover { text-decoration: underline; }
        .status { padding: 5px 10px; border-radius: 4px; display: inline-block; margin-bottom: 15px; }
        .status.pending { background-color: #f39c12; color: white; }
        .status.completed { background-color: #2ecc71; color: white; }
        .status.failed { background-color: #e74c3c; color: white; }
        .tabs { display: flex; margin-bottom: 15px; }
        .tab { padding: 10px 15px; cursor: pointer; border: 1px solid #ddd; border-bottom: none; border-radius: 4px 4px 0 0; margin-right: 5px; }
        .tab.active { background-color: #f8f9fa; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .trace-link { margin-top: 10px; }
        .trace-link a { color: #3498db; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Login Scraper Agent</h1>
        <form id="loginForm">
            <div>
                <label for="url">URL:</label>
                <input type="text" id="url" name="url" placeholder="https://example.com/login" required>
            </div>
            <div>
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" placeholder="Username" required>
            </div>
            <div>
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit">Start Scraping</button>
        </form>

        <div class="result" id="result" style="display:none;">
            <h2>Results</h2>
            <div class="status pending" id="jobStatus">Pending</div>
            <div class="vm-link" id="vmLink" style="display:none;">
                <strong>VM URL:</strong> <a href="#" target="_blank" id="vmUrl">View VM</a> (watch the agent in real-time)
            </div>
            <div class="trace-link" id="traceLink" style="display:none;">
                <strong>Trace URL:</strong> <a href="#" target="_blank" id="traceUrl">View LangSmith Trace</a>
            </div>
            
            <div class="tabs">
                <div class="tab active" onclick="showTab('htmlContent')">HTML Content</div>
                <div class="tab" onclick="showTab('rawHtml')">Raw HTML</div>
            </div>
            
            <div class="tab-content active" id="htmlContent">
                <iframe id="htmlFrame" style="width: 100%; height: 500px; border: 1px solid #ddd; border-radius: 4px;"></iframe>
            </div>
            
            <div class="tab-content" id="rawHtml">
                <pre id="rawHtmlContent"></pre>
            </div>
        </div>
    </div>

    <script>
        function showTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Deactivate all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Activate the selected tab and content
            document.getElementById(tabId).classList.add('active');
            document.querySelector(`.tab[onclick="showTab('${tabId}')"]`).classList.add('active');
        }

        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const url = document.getElementById('url').value;
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            document.getElementById('result').style.display = 'block';
            document.getElementById('jobStatus').className = 'status pending';
            document.getElementById('jobStatus').textContent = 'Pending';
            document.getElementById('vmLink').style.display = 'none';
            document.getElementById('traceLink').style.display = 'none';
            document.getElementById('rawHtmlContent').textContent = '';
            document.getElementById('htmlFrame').srcdoc = '';
            
            try {
                // Start the scraping job
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        url: url,
                        username: username,
                        password: password
                    })
                });
                
                if (!response.ok) {
                    throw new Error('API request failed');
                }
                
                const data = await response.json();
                const jobId = data.job_id;
                
                // Poll for job status
                const statusCheck = setInterval(async () => {
                    const statusResponse = await fetch(`/api/jobs/${jobId}`);
                    const jobData = await statusResponse.json();
                    
                    if (jobData.vm_url) {
                        document.getElementById('vmLink').style.display = 'block';
                        document.getElementById('vmUrl').href = jobData.vm_url;
                    }
                    
                    if (jobData.langsmith_trace_url) {
                        document.getElementById('traceLink').style.display = 'block';
                        document.getElementById('traceUrl').href = jobData.langsmith_trace_url;
                    }
                    
                    if (jobData.status === 'completed') {
                        clearInterval(statusCheck);
                        document.getElementById('jobStatus').className = 'status completed';
                        document.getElementById('jobStatus').textContent = 'Completed';
                        
                        if (jobData.html_content) {
                            // Display the HTML content in the iframe
                            document.getElementById('htmlFrame').srcdoc = jobData.html_content;
                            
                            // Display the raw HTML
                            document.getElementById('rawHtmlContent').textContent = jobData.html_content;
                        }
                    } else if (jobData.status === 'failed') {
                        clearInterval(statusCheck);
                        document.getElementById('jobStatus').className = 'status failed';
                        document.getElementById('jobStatus').textContent = 'Failed: ' + (jobData.error || 'Unknown error');
                    }
                }, 3000);
            } catch (error) {
                document.getElementById('jobStatus').className = 'status failed';
                document.getElementById('jobStatus').textContent = 'Failed: ' + error.message;
            }
        });
    </script>
</body>
</html>
    """)

# Mount the static files and HTML pages
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_html(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/scrape")
async def scrape_page(credentials: LoginCredentials, background_tasks: BackgroundTasks):
    job_id = f"job_{len(scraping_jobs) + 1}_{int(datetime.now().timestamp())}"
    
    # Create a new job
    scraping_jobs[job_id] = ScrapingJob(
        job_id=job_id,
        status="pending",
        started_at=datetime.now().isoformat(),
        completed_at=None
    )
    
    # Start the scraping in the background
    background_tasks.add_task(
        process_scraping_job,
        job_id=job_id,
        url=credentials.url,
        username=credentials.username,
        password=credentials.password
    )
    
    return {"job_id": job_id, "status": "pending"}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in scraping_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return scraping_jobs[job_id]

async def process_scraping_job(job_id: str, url: str, username: str, password: str):
    logger.info(f"Starting job {job_id} for URL: {url}")
    
    run_id = None
    vm_url = None
    html_content = None
    error_message = None
    trace_url = None
    
    try:
        # Create system message with clear instructions
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
        - Format your final response with the complete HTML in a code block
        - Be explicit about each step you're taking to help with debugging
        
        If you encounter:
        - CAPTCHA: Report that the site has CAPTCHA protection and cannot be accessed
        - Cloudflare protection: Report that the site has Cloudflare protection and cannot be accessed
        - Two-factor authentication: Report that the site requires 2FA and cannot be accessed
        - Any other login obstacles: Clearly describe what's preventing login
        
        Security notes:
        - Do not store credentials beyond this specific task
        - Only interact with the specified website
        """
        
        # Create human message with specific instructions
        human_message = f"""
        Please navigate to {url} and login with these credentials:
        Username: {username}
        Password: {password}
        
        After logging in successfully, extract the complete HTML of the page using 'document.documentElement.outerHTML'.
        Return the HTML content in a code block for easy parsing.
        """
        
        input_data = {
            "system": system_message,
            "human": human_message,
        }
        
        # Execute the agent with tracing if available
        trace_kwargs = {}
        if langsmith_client:
            trace_kwargs = {
                "project_name": "login_scraper_agent",
                "trace_name": f"Job {job_id} - {url}",
            }
        
        # Update job with running status
        scraping_jobs[job_id].status = "running"
        
        # Stream the agent execution
        agent_response = ""
        stream = await kua_graph.astream(input_data, **trace_kwargs)
        
        async for chunk in stream:
            if "run" in chunk and not run_id:
                run_id = chunk["run"].id
                if langsmith_client:
                    trace_url = f"https://smith.langchain.com/traces/{run_id}"
                    scraping_jobs[job_id].langsmith_trace_url = trace_url
                    logger.info(f"LangSmith trace URL: {trace_url}")
            
            if "vm_instance" in chunk and not vm_url:
                vm_url = chunk["vm_instance"].url
                scraping_jobs[job_id].vm_url = vm_url
                logger.info(f"VM URL: {vm_url}")
            
            if "agent_response" in chunk:
                response_chunk = chunk["agent_response"]
                agent_response += response_chunk
                logger.debug(f"Agent response chunk: {response_chunk}")
        
        # Parse HTML from agent response
        logger.info("Parsing HTML from agent response")
        html_content = extract_html_from_response(agent_response)
        
        if html_content:
            logger.info(f"Successfully extracted HTML content ({len(html_content)} characters)")
        else:
            # Check for common error messages
            if "captcha" in agent_response.lower() or "CAPTCHA" in agent_response:
                error_message = "Login blocked by CAPTCHA protection"
            elif "cloudflare" in agent_response.lower():
                error_message = "Login blocked by Cloudflare protection"
            elif "two-factor" in agent_response.lower() or "2fa" in agent_response.lower():
                error_message = "Login requires two-factor authentication"
            elif "incorrect" in agent_response.lower() and "password" in agent_response.lower():
                error_message = "Login failed: Incorrect username or password"
            else:
                error_message = "Failed to extract HTML content. The login may have failed or the page structure was not as expected."
            
            logger.error(f"Job {job_id} failed: {error_message}")
    
    except Exception as e:
        error_message = f"Agent execution error: {str(e)}"
        logger.exception(f"Job {job_id} failed with exception")
    
    # Update job with results
    job = scraping_jobs[job_id]
    job.completed_at = datetime.now().isoformat()
    
    if error_message:
        job.status = "failed"
        job.error = error_message
    else:
        job.status = "completed"
        job.html_content = html_content
    
    logger.info(f"Job {job_id} completed with status: {job.status}")


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
    
    # Try alternative code block format
    if "```" in response:
        parts = response.split("```", 2)
        if len(parts) > 2:
            potential_html = parts[1]
            if potential_html.startswith("html"):
                potential_html = potential_html[4:].strip()
            if "<html" in potential_html and "</html>" in potential_html:
                return potential_html.strip()
    
    # Try extracting directly from response if it contains HTML tags
    if "<html" in response and "</html>" in response:
        start = response.find("<html")
        end = response.find("</html>") + 7
        return response[start:end]
    
    # Try extracting any large block of HTML even if not complete document
    if "<body" in response and "</body>" in response:
        start = max(0, response.find("<body") - 1000)  # Look for potential start before body
        end = min(len(response), response.find("</body>") + 1000)  # Include potential content after body
        html_block = response[start:end]
        if len(html_block) > 100:  # Only return if substantial
            return html_block
    
    return None


@app.get("/api/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    logger.info("Starting Login Scraper Agent API")
    uvicorn.run("login_scraper_agent:app", host="0.0.0.0", port=8000, reload=True)
