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
from langgraph_cua import create_cua
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

# Create the Cua agent
# Corrected function call: Changed 'create_kua' to 'create_cua'
# Corrected variable name: Changed 'kua_graph' to 'cua_graph'
cua_graph = create_cua()

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

# Create HTML template for testing (Ensure this file exists or is created)
# Check if template exists, if not create a basic one
index_html_path = "templates/index.html"
if not os.path.exists(index_html_path):
    os.makedirs("templates", exist_ok=True)
    with open(index_html_path, "w") as f:
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
        .status.running { background-color: #3498db; color: white; }
        .status.completed { background-color: #2ecc71; color: white; }
        .status.failed { background-color: #e74c3c; color: white; }
        .tabs { display: flex; margin-bottom: 15px; border-bottom: 1px solid #ddd; }
        .tab { padding: 10px 15px; cursor: pointer; border: 1px solid transparent; border-bottom: none; margin-bottom: -1px; }
        .tab.active { border-color: #ddd; border-bottom: 1px solid white; background-color: white; border-radius: 4px 4px 0 0; }
        .tab-content { display: none; padding: 15px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 4px 4px; background-color: white;}
        .tab-content.active { display: block; }
        .trace-link { margin-top: 10px; }
        .trace-link a { color: #3498db; text-decoration: none; }
        #loadingSpinner { display: none; /* Initially hidden */ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; margin-left: 10px; vertical-align: middle; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
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
            <button type="submit">Start Scraping <span id="loadingSpinner"></span></button>
        </form>

        <div class="result" id="result" style="display:none;">
            <h2>Results</h2>
            <div id="jobInfo">
                <strong>Job ID:</strong> <span id="jobIdDisplay"></span><br>
                <strong>Status:</strong> <span class="status pending" id="jobStatus">Pending</span>
            </div>
            <div class="vm-link" id="vmLink" style="display:none;">
                <strong>VM URL:</strong> <a href="#" target="_blank" id="vmUrl">View VM</a> (watch the agent in real-time)
            </div>
            <div class="trace-link" id="traceLink" style="display:none;">
                <strong>Trace URL:</strong> <a href="#" target="_blank" id="traceUrl">View LangSmith Trace</a>
            </div>

            <div id="outputTabs" style="display:none;">
                <div class="tabs">
                    <div class="tab active" onclick="showTab('htmlContent')">Rendered HTML</div>
                    <div class="tab" onclick="showTab('rawHtml')">Raw HTML Source</div>
                </div>

                <div class="tab-content active" id="htmlContent">
                    <iframe id="htmlFrame" style="width: 100%; height: 500px; border: 1px solid #ddd; border-radius: 4px;"></iframe>
                </div>

                <div class="tab-content" id="rawHtml">
                    <pre id="rawHtmlContent"></pre>
                </div>
            </div>
             <div id="errorMessage" style="display:none; color: #e74c3c; margin-top: 15px; background-color: #fceded; padding: 10px; border-radius: 4px;">
                <strong>Error:</strong> <span id="errorText"></span>
            </div>
        </div>
    </div>

    <script>
        const form = document.getElementById('loginForm');
        const resultDiv = document.getElementById('result');
        const jobStatusSpan = document.getElementById('jobStatus');
        const vmLinkDiv = document.getElementById('vmLink');
        const vmUrlLink = document.getElementById('vmUrl');
        const traceLinkDiv = document.getElementById('traceLink');
        const traceUrlLink = document.getElementById('traceUrl');
        const htmlFrame = document.getElementById('htmlFrame');
        const rawHtmlContentPre = document.getElementById('rawHtmlContent');
        const outputTabsDiv = document.getElementById('outputTabs');
        const errorMessageDiv = document.getElementById('errorMessage');
        const errorTextSpan = document.getElementById('errorText');
        const jobIdDisplaySpan = document.getElementById('jobIdDisplay');
        const loadingSpinner = document.getElementById('loadingSpinner');
        const submitButton = form.querySelector('button[type="submit"]');

        let pollingInterval = null; // To store the interval ID

        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.querySelector(`.tab[onclick="showTab('${tabId}')"]`).classList.add('active');
        }

        function updateJobStatusUI(jobData) {
            jobIdDisplaySpan.textContent = jobData.job_id;
            jobStatusSpan.textContent = jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1); // Capitalize
            jobStatusSpan.className = `status ${jobData.status}`; // Update class for styling

            if (jobData.vm_url) {
                vmUrlLink.href = jobData.vm_url;
                vmLinkDiv.style.display = 'block';
            } else {
                vmLinkDiv.style.display = 'none';
            }

            if (jobData.langsmith_trace_url) {
                traceUrlLink.href = jobData.langsmith_trace_url;
                traceLinkDiv.style.display = 'block';
            } else {
                traceLinkDiv.style.display = 'none';
            }

            if (jobData.status === 'completed') {
                clearInterval(pollingInterval); // Stop polling
                loadingSpinner.style.display = 'none';
                submitButton.disabled = false;
                outputTabsDiv.style.display = 'block'; // Show tabs
                errorMessageDiv.style.display = 'none'; // Hide error message
                if (jobData.html_content) {
                    htmlFrame.srcdoc = jobData.html_content;
                    rawHtmlContentPre.textContent = jobData.html_content;
                } else {
                     htmlFrame.srcdoc = '<p>No HTML content received.</p>';
                     rawHtmlContentPre.textContent = 'No HTML content received.';
                }
                showTab('htmlContent'); // Ensure the first tab is active
            } else if (jobData.status === 'failed') {
                clearInterval(pollingInterval); // Stop polling
                loadingSpinner.style.display = 'none';
                submitButton.disabled = false;
                outputTabsDiv.style.display = 'none'; // Hide tabs
                errorTextSpan.textContent = jobData.error || 'Unknown error occurred.';
                errorMessageDiv.style.display = 'block'; // Show error message
            } else {
                // Still pending or running
                outputTabsDiv.style.display = 'none';
                errorMessageDiv.style.display = 'none';
            }
        }

        async function pollJobStatus(jobId) {
            try {
                const response = await fetch(`/api/jobs/${jobId}`);
                if (!response.ok) {
                    // Handle non-2xx responses if needed, e.g., 404 Job Not Found
                    console.error(`Error fetching job status: ${response.status}`);
                    // Optionally stop polling or show an error
                    if (response.status === 404) {
                        clearInterval(pollingInterval);
                        loadingSpinner.style.display = 'none';
                        submitButton.disabled = false;
                        errorTextSpan.textContent = `Job ${jobId} not found.`;
                        errorMessageDiv.style.display = 'block';
                    }
                    return;
                }
                const jobData = await response.json();
                updateJobStatusUI(jobData);
            } catch (error) {
                console.error('Polling error:', error);
                // Optionally stop polling on network errors
                // clearInterval(pollingInterval);
                // loadingSpinner.style.display = 'none';
                // submitButton.disabled = false;
                // errorTextSpan.textContent = 'Network error while checking job status.';
                // errorMessageDiv.style.display = 'block';
            }
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (pollingInterval) {
                clearInterval(pollingInterval); // Clear previous interval if any
            }

            const url = document.getElementById('url').value;
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            // Reset UI
            resultDiv.style.display = 'block';
            jobStatusSpan.className = 'status pending';
            jobStatusSpan.textContent = 'Pending';
            jobIdDisplaySpan.textContent = 'N/A';
            vmLinkDiv.style.display = 'none';
            traceLinkDiv.style.display = 'none';
            outputTabsDiv.style.display = 'none';
            errorMessageDiv.style.display = 'none';
            rawHtmlContentPre.textContent = '';
            htmlFrame.srcdoc = '';
            loadingSpinner.style.display = 'inline-block'; // Show spinner
            submitButton.disabled = true; // Disable button during processing

            try {
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, username, password })
                });

                if (!response.ok) {
                    let errorMsg = `API request failed with status ${response.status}`;
                    try {
                        const errorData = await response.json();
                        errorMsg += `: ${errorData.detail || 'Unknown API error'}`;
                    } catch (jsonError) {
                        // Ignore if response is not JSON
                    }
                    throw new Error(errorMsg);
                }

                const data = await response.json();
                const jobId = data.job_id;
                jobIdDisplaySpan.textContent = jobId; // Display Job ID immediately

                // Start polling
                updateJobStatusUI({ job_id: jobId, status: 'pending' }); // Initial state
                pollJobStatus(jobId); // Poll immediately once
                pollingInterval = setInterval(() => pollJobStatus(jobId), 3000); // Poll every 3 seconds

            } catch (error) {
                console.error('Submission error:', error);
                jobStatusSpan.className = 'status failed';
                jobStatusSpan.textContent = 'Failed';
                errorTextSpan.textContent = error.message;
                errorMessageDiv.style.display = 'block';
                loadingSpinner.style.display = 'none'; // Hide spinner on error
                submitButton.disabled = false; // Re-enable button
            }
        });

        // Initialize with the first tab showing
        showTab('htmlContent');
    </script>
</body>
</html>
        """)

# Mount the static files and HTML pages
# Ensure a 'static' directory exists if you plan to serve static files from there
# os.makedirs("static", exist_ok=True)
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_html(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/scrape", status_code=202) # Use 202 Accepted for async tasks
async def scrape_page(credentials: LoginCredentials, background_tasks: BackgroundTasks):
    """
    Accepts login credentials and URL, starts a background scraping job,
    and returns the job ID.
    """
    job_id = f"job_{len(scraping_jobs) + 1}_{int(datetime.now().timestamp())}"
    logger.info(f"Received scrape request for URL: {credentials.url}. Assigning Job ID: {job_id}")

    # Create and store the initial job state
    scraping_jobs[job_id] = ScrapingJob(
        job_id=job_id,
        status="pending",
        started_at=datetime.now().isoformat(),
        url=credentials.url # Store URL in job for reference
    )

    # Add the scraping task to run in the background
    background_tasks.add_task(
        process_scraping_job,
        job_id=job_id,
        url=credentials.url,
        username=credentials.username,
        password=credentials.password
    )

    # Return the job ID and initial status
    return {"job_id": job_id, "status": "pending", "message": "Scraping job started."}

@app.get("/api/jobs/{job_id}", response_model=ScrapingJob)
async def get_job_status(job_id: str):
    """Returns the current status and results of a specific scraping job."""
    logger.debug(f"Received status request for Job ID: {job_id}")
    if job_id not in scraping_jobs:
        logger.warning(f"Job ID not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    # Return the current state of the job
    return scraping_jobs[job_id]

async def process_scraping_job(job_id: str, url: str, username: str, password: str):
    """
    The background task function that performs the actual scraping using the Cua agent.
    Updates the job status in the `scraping_jobs` dictionary.
    """
    logger.info(f"Starting background processing for Job ID: {job_id}, URL: {url}")

    # Update job status to 'running'
    if job_id in scraping_jobs:
        scraping_jobs[job_id].status = "running"
    else:
        logger.error(f"Job ID {job_id} disappeared before processing could start.")
        return # Cannot proceed if job entry is gone

    run_id = None
    vm_url = None
    html_content = None
    error_message = None
    trace_url = None

    try:
        # Define the system message for the agent
        system_message = """
        You are an advanced AI assistant specialized in web scraping and browser automation.
        Your task is to log into a website using provided credentials and extract the HTML content after successful login.

        Instructions:
        1. Navigate to the provided URL.
        2. Locate the login form (it might require navigating or handling redirects).
        3. Enter the username and password into the appropriate fields.
        4. Submit the login form.
        5. Wait for the page to load after login. Verify login success if possible (e.g., look for welcome message, account section).
        6. Once logged in and the target page is loaded, extract the *complete* HTML source code using `document.documentElement.outerHTML`.
        7. Return *only* the extracted HTML content within a single ```html code block. Do not include any other text, explanations, or summaries outside the code block.

        Error Handling:
        - If you encounter CAPTCHA, Cloudflare, 2FA, or any other blocker preventing login, clearly state the specific reason in your response (e.g., "Login failed: CAPTCHA detected."). Do *not* return HTML in this case.
        - If login fails due to incorrect credentials, state "Login failed: Incorrect username or password."
        - If you cannot find the login form or the target page after login, state the issue clearly.

        Example successful output format:
        ```html
        <!DOCTYPE html>
        <html>
        <head>...</head>
        <body>...</body>
        </html>
        ```

        Example error output format:
        Login failed: CAPTCHA detected.
        """

        # Define the human message with specific task details
        human_message = f"""
        Please log into the website at the following URL:
        {url}

        Use these credentials:
        Username: {username}
        Password: [REDACTED]

        After successful login, extract the complete HTML of the resulting page using `document.documentElement.outerHTML` and return it in a ```html code block.
        """
        # Note: Password is intentionally redacted in the log/human message for security,
        # but the actual password variable is passed to the agent execution context.

        input_data = {
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": human_message}
            ],
             # Pass credentials securely if the agent expects them in a specific format
             # This might vary based on the 'create_cua' implementation
             "credentials": {
                 "username": username,
                 "password": password
             }
        }

        # Configure tracing if LangSmith is enabled
        trace_config = {}
        if langsmith_client:
            trace_config = {
                "configurable": {
                    "project_name": "login_scraper_agent",
                    "run_name": f"Job {job_id} - {url}",
                    "client": langsmith_client, # Pass the client instance if required by astream
                 }
            }
            logger.info(f"LangSmith tracing enabled for Job ID: {job_id}")


        # Stream the agent's execution process
        agent_final_response = ""
        logger.info(f"Invoking cua_graph.astream for Job ID: {job_id}")
        # Corrected variable name: Changed 'kua_graph' to 'cua_graph'
        async for chunk in cua_graph.astream(input_data, config=trace_config):
            # Process chunks to extract relevant information (VM URL, Run ID, Agent Response)
            # The exact structure of 'chunk' depends on how 'create_cua' yields information.
            # Adapt the following based on the actual output structure.

            # Example: Extracting Run ID for LangSmith Trace URL
            # This assumes the run ID might be in a 'run_info' or similar key
            current_run_id = chunk.get("run_info", {}).get("run_id") or chunk.get("run_id")
            if current_run_id and not run_id:
                run_id = current_run_id
                if langsmith_client:
                    # Construct trace URL (adjust domain if using a self-hosted LangSmith)
                    trace_url = f"https://smith.langchain.com/runs/{run_id}"
                    if job_id in scraping_jobs:
                        scraping_jobs[job_id].langsmith_trace_url = trace_url
                    logger.info(f"LangSmith Run ID: {run_id}, Trace URL: {trace_url}")

            # Example: Extracting VM URL
            # This assumes the VM URL might be in a 'vm_instance' key
            current_vm_info = chunk.get("vm_instance")
            if current_vm_info and hasattr(current_vm_info, 'url') and not vm_url:
                 vm_url = current_vm_info.url
                 if job_id in scraping_jobs:
                     scraping_jobs[job_id].vm_url = vm_url
                 logger.info(f"VM URL obtained: {vm_url}")

            # Example: Accumulating the agent's final response
            # This assumes the response parts are in 'agent_response' or 'output' key
            response_part = chunk.get("agent_response") or chunk.get("output") or chunk.get("content")
            if isinstance(response_part, str):
                agent_final_response += response_part
                logger.debug(f"Agent response chunk received for Job {job_id}: {response_part[:100]}...") # Log snippet

        logger.info(f"Agent stream finished for Job ID: {job_id}. Final response length: {len(agent_final_response)}")

        # Attempt to parse the HTML from the final accumulated response
        html_content = extract_html_from_response(agent_final_response)

        if html_content:
            logger.info(f"Successfully extracted HTML content for Job ID: {job_id} ({len(html_content)} characters)")
        else:
            # If no HTML block found, the response likely contains an error message
            error_message = agent_final_response.strip() if agent_final_response else "Agent produced no output or failed to extract HTML."
            # More specific error checking based on expected error messages
            if not error_message or "login failed" not in error_message.lower() and "captcha" not in error_message.lower() and "cloudflare" not in error_message.lower() and "2fa" not in error_message.lower():
                 error_message = f"Failed to extract HTML. Agent response: {agent_final_response[:500]}" # Truncate long responses
            logger.warning(f"HTML extraction failed for Job ID: {job_id}. Error/Response: {error_message}")

    except Exception as e:
        error_message = f"Unhandled exception during agent execution: {str(e)}"
        logger.exception(f"Job {job_id} failed with an unhandled exception:") # Logs traceback

    # Final job status update
    if job_id in scraping_jobs:
        job = scraping_jobs[job_id]
        job.completed_at = datetime.now().isoformat()
        if error_message:
            job.status = "failed"
            job.error = error_message
            job.html_content = None # Ensure HTML is null on failure
        else:
            job.status = "completed"
            job.html_content = html_content
            job.error = None # Ensure error is null on success
        logger.info(f"Job {job_id} processing finished. Final Status: {job.status}")
    else:
         logger.error(f"Job ID {job_id} disappeared before final status update.")


def extract_html_from_response(response: str) -> Optional[str]:
    """
    Extracts HTML content enclosed in ```html ... ``` blocks from the agent's response.
    """
    logger.debug(f"Attempting to extract HTML from response (length {len(response)}).")
    # Use regex for more robust extraction
    import re
    # Regex to find content within ```html ... ```, handling potential leading/trailing whitespace
    # DOTALL flag allows '.' to match newlines
    match = re.search(r"```html\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
    if match:
        extracted_html = match.group(1).strip()
        logger.debug(f"HTML extracted using ```html block (length {len(extracted_html)}).")
        # Basic validation: check if it looks like HTML
        if extracted_html.startswith("<") and extracted_html.endswith(">"):
             return extracted_html
        else:
             logger.warning("Content within ```html block doesn't look like valid HTML.")
             return None # Or return the content anyway? Decide based on expected agent behavior.

    # Fallback: If no ```html block, check if the entire response might be HTML
    # This is less reliable and depends on agent strictly following instructions
    stripped_response = response.strip()
    if stripped_response.startswith("<!DOCTYPE html") or (stripped_response.startswith("<html") and stripped_response.endswith("</html>")):
         logger.debug("Assuming entire response is HTML based on start/end tags.")
         return stripped_response

    logger.debug("No HTML content found in the expected format.")
    return None


@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check endpoint accessed.")
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Entry point for running the FastAPI application using Uvicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000)) # Allow port configuration via environment variable
    host = os.environ.get("HOST", "0.0.0.0") # Allow host configuration
    reload_flag = os.environ.get("RELOAD", "true").lower() == "true" # Allow disabling reload

    logger.info(f"Starting Login Scraper Agent API on {host}:{port} (Reload: {reload_flag})")

    # Construct the app string based on the filename.
    # Assumes the script is named 'login_scraper_agent.py'. If not, adjust this logic.
    module_name = os.path.splitext(os.path.basename(__file__))[0]
    app_string = f"{module_name}:app"

    uvicorn.run(app_string, host=host, port=port, reload=reload_flag)
