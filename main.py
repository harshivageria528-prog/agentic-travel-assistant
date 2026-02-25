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


@app.get("/flights")
def get_flights(origin: str, destination: str, date: str, return_date: Optional[str] = None):
    """
    Manual flight search endpoint (GET).
    Uses Amadeus API. Handles past dates and invalid locations via errors.
    """
    try:
        flights = []
        errors = []
        if origin and destination and date:
            try:
                flights = search_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=date,
                    return_date=return_date,
                    adults=1,
                    max_results=10,
                )
            except ValueError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"Flight search failed: {e}")

        return {
            "query": "manual search",
            "origin": origin,
            "destination": destination,
            "departure_date": date,
            "return_date": return_date,
            "flights": flights,
            "errors": errors,
        }
    except Exception as e:
        raise HTTPException(500, detail={"error": str(e), "trace": traceback.format_exc()})


@app.get("/hotels")
def get_hotels(city: str, check_in: Optional[str] = None, check_out: Optional[str] = None):
    """
    Manual hotel search endpoint (GET).
    Uses Amadeus API. Validates city code and dates.
    """
    try:
        hotels = []
        errors = []
        if city:
            try:
                hotels = search_hotels(
                    city_code=city,
                    check_in=check_in,
                    check_out=check_out,
                    adults=1,
                    max_hotels=10,
                )
            except ValueError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"Hotel search failed: {e}")

        return {
            "query": "manual search",
            "city": city,
            "check_in": check_in,
            "check_out": check_out,
            "hotels": hotels,
            "errors": errors,
        }
    except Exception as e:
        raise HTTPException(500, detail={"error": str(e), "trace": traceback.format_exc()})


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
