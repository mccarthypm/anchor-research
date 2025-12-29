"""
FastAPI web server for the Stock Analysis Agent.

This server exposes HTTP endpoints to interact with the stock analysis agent
for deployment on Google Cloud Run.
"""

import os

# Disable LiteLLM's async logging worker to avoid event loop conflicts
# Must be set before importing litellm
os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "true")

import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.stock_analysis import StockAnalysisAgent

app = FastAPI(
    title="Stock Analysis Agent API",
    description="API for analyzing SEC filings using AI",
    version="1.0.0",
)

# Configure CORS - adjust allowed origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL, MSFT)")
    question: str = Field(..., description="Question to ask about the stock")
    model: Optional[str] = Field(
        None,
        description="Model to use (default: Claude Sonnet via LiteLLM)"
    )
    max_full_docs: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum documents to keep in full context"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    ticker: str
    company_name: str
    response: str
    session_summary: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    message: str


# Store agents per ticker (in production, consider using Redis or similar)
_agent_cache: dict[str, StockAnalysisAgent] = {}


def get_or_create_agent(
    ticker: str,
    model: Optional[str] = None,
    max_full_docs: int = 3
) -> StockAnalysisAgent:
    """Get or create an agent instance for a ticker."""
    cache_key = f"{ticker}:{model}:{max_full_docs}"
    
    if cache_key not in _agent_cache:
        try:
            agent = StockAnalysisAgent(
                ticker=ticker,
                companies_dir=None,  # Uses Firebase Storage
                model=model,
                max_full_docs=max_full_docs,
            )
            _agent_cache[cache_key] = agent
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create agent: {str(e)}"
            )
    
    return _agent_cache[cache_key]


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check."""
    return HealthResponse(
        status="ok",
        message="Stock Analysis Agent API is running"
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        message="Service is healthy"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a question to the stock analysis agent.
    
    This endpoint:
    1. Creates or retrieves an agent for the specified ticker
    2. Sends the question to the agent
    3. Returns the agent's response along with session summary
    """
    try:
        agent = get_or_create_agent(
            ticker=request.ticker,
            model=request.model,
            max_full_docs=request.max_full_docs,
        )
        
        # Send the question and get response
        response = await agent.chat_async(request.question)
        
        # Get session summary
        session_summary = agent.get_session_summary()
        
        return ChatResponse(
            ticker=agent.ticker,
            company_name=agent.company_name,
            response=response,
            session_summary=session_summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@app.delete("/sessions/{ticker}")
async def clear_session(ticker: str):
    """Clear cached agent session for a ticker."""
    # Remove all agents for this ticker
    keys_to_remove = [k for k in _agent_cache.keys() if k.startswith(f"{ticker.upper()}:")]
    for key in keys_to_remove:
        del _agent_cache[key]
    
    return {"status": "ok", "message": f"Cleared sessions for {ticker}"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

