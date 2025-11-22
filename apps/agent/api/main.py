"""FastAPI server for LangGraph fact-checking workflows."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


class WorkflowResponse(BaseModel):
    """Generic response model for workflow execution."""

    status: str = Field(description="Status of the workflow execution")
    result: Dict[str, Any] = Field(description="The workflow result")


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


@app.post("/fact-check", response_model=WorkflowResponse)
async def fact_check(request: FactCheckerRequest, api_key: str = Depends(verify_api_key)):
    """Run the complete fact-checking pipeline on text.

    This endpoint orchestrates the full fact-checking workflow:
    1. Extract claims from input text
    2. Verify each claim in parallel
    3. Generate a comprehensive report
    """
    try:
        graph = graphs.get("fact_checker")
        if not graph:
            raise HTTPException(status_code=503, detail="Fact checker not available")

        logger.info(f"Fact-checking text: {request.answer[:100]}...")

        # Invoke the graph asynchronously
        result = await graph.ainvoke({"answer": request.answer})

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
        
        return WorkflowResponse(
            status="success",
            result={
                "final_report": final_report_dict,
                "claims_extracted": len(result.get("extracted_claims", [])),
                "claims_verified": len(result.get("verification_results", [])),
            },
        )
    except Exception as e:
        logger.error(f"Error fact-checking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
