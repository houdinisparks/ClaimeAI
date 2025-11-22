"""FastAPI server for LangGraph fact-checking workflows."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from claim_extractor.agent import create_graph as create_claim_extractor_graph
from claim_verifier.agent import create_graph as create_claim_verifier_graph
from fact_checker.agent import create_graph as create_fact_checker_graph

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


@app.post("/extract-claims", response_model=WorkflowResponse)
async def extract_claims(request: ClaimExtractorRequest):
    """Extract verifiable claims from text.

    This endpoint processes text through the claim extraction pipeline:
    1. Split text into contextual sentences
    2. Filter for sentences with factual content
    3. Resolve ambiguities like pronouns
    4. Extract specific atomic claims
    5. Validate claims are properly formed
    """
    try:
        graph = graphs.get("claim_extractor")
        if not graph:
            raise HTTPException(status_code=503, detail="Claim extractor not available")

        logger.info(f"Extracting claims from text: {request.text[:100]}...")

        # Invoke the graph asynchronously
        result = await graph.ainvoke({"text": request.text})

        return WorkflowResponse(
            status="success",
            result={
                "text": result.get("text"),
                "validated_claims": [
                    claim.model_dump() for claim in result.get("validated_claims", [])
                ],
            },
        )
    except Exception as e:
        logger.error(f"Error extracting claims: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify-claim", response_model=WorkflowResponse)
async def verify_claim(request: ClaimVerifierRequest):
    """Verify a single claim using iterative evidence gathering.

    This endpoint processes a claim through the verification pipeline:
    1. Generate search queries
    2. Retrieve evidence from web search
    3. Decide whether to continue searching
    4. Evaluate evidence and make a verdict
    """
    try:
        graph = graphs.get("claim_verifier")
        if not graph:
            raise HTTPException(status_code=503, detail="Claim verifier not available")

        logger.info(f"Verifying claim: {request.claim}")

        # Create ValidatedClaim object for the graph
        from claim_extractor.schemas import (
            ValidatedClaim,
            PotentialClaim,
            DisambiguatedContent,
            SelectedContent,
            ContextualSentence,
        )

        validated_claim = ValidatedClaim(
            verified_claim=PotentialClaim(
                claim_text=request.claim,
                original_disambiguated_item=DisambiguatedContent(
                    disambiguated_sentence=request.disambiguated_sentence,
                    original_selected_item=SelectedContent(
                        processed_sentence=request.original_sentence,
                        original_context_item=ContextualSentence(
                            original_sentence=request.original_sentence,
                            context_for_llm=request.original_sentence,
                            original_index=request.original_index,
                        ),
                    ),
                ),
            )
        )

        # Invoke the graph asynchronously
        result = await graph.ainvoke({"claim": validated_claim})

        verdict = result.get("verdict")
        return WorkflowResponse(
            status="success",
            result={
                "verdict": verdict.model_dump() if verdict else None,
                "evidence_count": len(result.get("evidence", [])),
                "iterations": result.get("iteration_count", 0),
            },
        )
    except Exception as e:
        logger.error(f"Error verifying claim: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fact-check", response_model=WorkflowResponse)
async def fact_check(request: FactCheckerRequest):
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
        return WorkflowResponse(
            status="success",
            result={
                "final_report": final_report.model_dump() if final_report else None,
                "claims_extracted": len(result.get("extracted_claims", [])),
                "claims_verified": len(result.get("verification_results", [])),
            },
        )
    except Exception as e:
        logger.error(f"Error fact-checking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflows/{workflow_name}/invoke")
async def invoke_workflow(workflow_name: str, input_data: Dict[str, Any]):
    """Generic endpoint to invoke any workflow by name.

    Args:
        workflow_name: One of 'claim_extractor', 'claim_verifier', 'fact_checker'
        input_data: The input state for the workflow
    """
    try:
        graph = graphs.get(workflow_name)
        if not graph:
            raise HTTPException(
                status_code=404, detail=f"Workflow '{workflow_name}' not found"
            )

        logger.info(f"Invoking workflow: {workflow_name}")

        # Invoke the graph asynchronously
        result = await graph.ainvoke(input_data)

        # Convert Pydantic models to dicts for JSON serialization
        serialized_result = {}
        for key, value in result.items():
            if hasattr(value, "model_dump"):
                serialized_result[key] = value.model_dump()
            elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                serialized_result[key] = [item.model_dump() for item in value]
            else:
                serialized_result[key] = value

        return WorkflowResponse(status="success", result=serialized_result)
    except Exception as e:
        logger.error(f"Error invoking workflow {workflow_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
