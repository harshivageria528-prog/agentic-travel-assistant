"""
FastAPI application for the agentic travel assistant.
POST /query - handles arbitrary queries and returns structured JSON.
"""
import traceback
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agent.travel_agent import run_agent
from src.state import TravelState
from src.services.amadeus_service import search_flights, search_hotels

app = FastAPI(title="Travel Assistant API", version="1.0.0")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    """Structured response for arbitrary travel queries."""

    query: str
    extracted_params: Dict[str, Any]
    flights: List[Dict[str, Any]]
    hotels: List[Dict[str, Any]]
    response: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []


def _state_to_response(state: TravelState) -> QueryResponse:
    """Convert TravelState to structured QueryResponse."""
    return QueryResponse(
        query=state.user_query,
        extracted_params={
            "needs_flights": state.needs_flights,
            "needs_hotels": state.needs_hotels,
            "origin": state.origin,
            "destination": state.destination,
            "departure_date": state.departure_date,
            "return_date": state.return_date,
            "hotels_city": state.hotels_city,
            "check_in": state.check_in,
            "check_out": state.check_out,
            "legs": state.legs,
        },
        flights=state.flights or [],
        hotels=state.hotels or [],
        response=state.response,
        errors=state.errors or [],
        warnings=state.warnings or [],
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """
    Handle arbitrary travel queries. Returns structured JSON with:
    - query: original user query
    - extracted_params: parsed origin, destination, dates, etc.
    - flights: Amadeus flight offers (dynamically populated)
    - hotels: Amadeus hotel offers (dynamically populated)
    - response: natural language summary
    - errors: validation/API errors (past dates, invalid locations, etc.)
    - warnings: non-fatal notices
    """
    try:
        state = run_agent(req.query)
        return _state_to_response(state)
    except Exception as e:
        return QueryResponse(
            query=req.query,
            extracted_params={},
            flights=[],
            hotels=[],
            response=None,
            errors=[f"Failed to process query: {e}"],
            warnings=[],
        )


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/env-test")
def env_test():
    """Verify environment variables for Amadeus API (masked)."""
    import os

    k = os.getenv("AMADEUS_API_KEY")
    s = os.getenv("AMADEUS_API_SECRET")
    return {
        "AMADEUS_API_KEY": f"{k[:8]}..." if k and len(k) > 8 else ("set" if k else "not set"),
        "AMADEUS_API_SECRET": "***" if s else "not set",
    }
