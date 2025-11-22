"""FastAPI server for LangGraph fact-checking workflows."""

import logging
import os
import asyncio
import httpx
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Security, Depends, BackgroundTasks
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from claim_extractor.agent import create_graph as create_claim_extractor_graph
from claim_verifier.agent import create_graph as create_claim_verifier_graph
from fact_checker.agent import create_graph as create_fact_checker_graph

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# API Key Authentication
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from the request header."""
    if not API_KEY:
        logger.warning("API_KEY not set in environment variables - API is unprotected!")
        return api_key
    
    if api_key is None or api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key. Include X-API-Key header.",
        )
    return api_key


# Global graph instances
graphs = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize graphs on startup."""
    logger.info("Initializing LangGraph workflows...")
    try:
        graphs["claim_extractor"] = create_claim_extractor_graph()
        graphs["claim_verifier"] = create_claim_verifier_graph()
        graphs["fact_checker"] = create_fact_checker_graph()
        logger.info("All graphs initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize graphs: {e}")
        raise
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="ClaimeAI - Fact Checking API",
    description="API for fact-checking workflows using LangGraph",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class ClaimExtractorRequest(BaseModel):
    """Request model for claim extraction."""

    text: str = Field(description="The text to extract claims from")


class ClaimVerifierRequest(BaseModel):
    """Request model for claim verification."""

    claim: str = Field(description="The claim text to verify")
    disambiguated_sentence: str = Field(
        description="The disambiguated sentence containing the claim"
    )
    original_sentence: str = Field(
        description="The original sentence from the source"
    )
    original_index: int = Field(
        default=0, description="The index of the sentence in the source text"
    )


class FactCheckerRequest(BaseModel):
    """Request model for full fact-checking."""

    answer: str = Field(description="The text to fact-check")
    callback_url: Optional[HttpUrl] = Field(
        default=None, 
        description="Optional URL to POST the results to when processing completes"
    )


class WorkflowResponse(BaseModel):
    """Generic response model for workflow execution."""

    status: str = Field(description="Status of the workflow execution")
    result: Dict[str, Any] = Field(description="The workflow result")


class JobAcceptedResponse(BaseModel):
    """Response model for accepted background job."""

    status: str = Field(description="Status of the job submission")
    message: str = Field(description="Human-readable message")
    job_id: Optional[str] = Field(default=None, description="Unique identifier for the background job")


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "ClaimeAI Fact Checking API",
        "version": "0.1.0",
        "available_workflows": ["claim_extractor", "claim_verifier", "fact_checker"],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "graphs_loaded": list(graphs.keys()),
    }


async def process_fact_check_job(text: str, callback_url: Optional[str] = None, job_id: Optional[str] = None):
    """Background task to process fact-checking and send results to callback URL."""
    try:
        graph = graphs.get("fact_checker")
        if not graph:
            logger.error("Fact checker not available in background job")
            return

        logger.info(f"[Job {job_id}] Starting fact-check for text: {text[:100]}...")

        # Invoke the graph asynchronously
        result = await graph.ainvoke({"answer": text})

        final_report = result.get("final_report")
        
        # Remove "text" field from sources in verified_claims (safe navigation)
        final_report_dict = None
        if final_report:
            final_report_dict = final_report.model_dump()
            verified_claims = final_report_dict.get("verified_claims", [])
            for claim in verified_claims:
                sources = claim.get("sources", [])
                for source in sources:
                    source.pop("text", None)  # Remove "text" key if it exists
        
        workflow_result = {
            "status": "success",
            "job_id": job_id,
            "result": {
                "final_report": final_report_dict,
                "claims_extracted": len(result.get("extracted_claims", [])),
                "claims_verified": len(result.get("verification_results", [])),
            },
        }

        logger.info(f"[Job {job_id}] Fact-check completed successfully")

        # Send results to callback URL if provided
        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.info(f"[Job {job_id}] Sending results to callback URL: {callback_url}")
                    response = await client.post(
                        callback_url,
                        json=workflow_result,
                        headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    logger.info(f"[Job {job_id}] Successfully sent results to callback URL. Status: {response.status_code}")
            except httpx.HTTPError as e:
                logger.error(f"[Job {job_id}] Failed to send results to callback URL: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[Job {job_id}] Unexpected error sending to callback URL: {e}", exc_info=True)
        else:
            logger.info(f"[Job {job_id}] No callback URL provided, results not sent")

    except Exception as e:
        logger.error(f"[Job {job_id}] Error in background fact-checking job: {e}", exc_info=True)
        
        # Send error to callback URL if provided
        if callback_url:
            try:
                error_result = {
                    "status": "error",
                    "job_id": job_id,
                    "error": str(e),
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(callback_url, json=error_result)
            except Exception as callback_error:
                logger.error(f"[Job {job_id}] Failed to send error to callback URL: {callback_error}")


@app.post("/fact-check", response_model=JobAcceptedResponse)
async def fact_check(
    request: FactCheckerRequest, 
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Run the complete fact-checking pipeline on text as a background job.

    This endpoint orchestrates the full fact-checking workflow:
    1. Extract claims from input text
    2. Verify each claim in parallel
    3. Generate a comprehensive report
    4. Send results to callback_url if provided

    The workflow runs asynchronously in the background. Results are sent to the
    callback_url via HTTP POST when processing completes.
    """
    try:
        graph = graphs.get("fact_checker")
        if not graph:
            raise HTTPException(status_code=503, detail="Fact checker not available")

        # Generate a simple job ID
        import uuid
        job_id = str(uuid.uuid4())[:8]

        logger.info(f"[Job {job_id}] Accepting fact-check job for text: {request.answer[:100]}...")
        
        # Add the background task
        background_tasks.add_task(
            process_fact_check_job,
            text=request.answer,
            callback_url=str(request.callback_url) if request.callback_url else None,
            job_id=job_id
        )

        return JobAcceptedResponse(
            status="accepted",
            message="Fact-checking job started. Results will be sent to callback URL when complete.",
            job_id=job_id
        )

    except Exception as e:
        logger.error(f"Error accepting fact-check job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
