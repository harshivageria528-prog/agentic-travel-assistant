"""
Travel agent pipeline: extract info from query, call flight/hotel tools, generate response.
"""
import json
import re

from src.state import TravelState
from src.tools.parser import parse_date_from_text, normalize_location, CITY_ALIASES
from src.llm.llm_client import get_llm
from src.tools.flight_tool import flight_tool
from src.tools.hotel_tool import hotel_tool

llm = get_llm()

EXTRACT_PROMPT = """Extract travel info from this query. Return ONLY valid JSON, no markdown.

Schema:
{{"origin": "IATA code or null", "destination": "IATA code or null", "departure_date": "YYYY-MM-DD or null", "return_date": "YYYY-MM-DD or null", "hotels_city": "IATA city code or null", "check_in": "YYYY-MM-DD or null", "check_out": "YYYY-MM-DD or null", "legs": []}}

For simple trips use origin, destination, departure_date.
For multi-leg use legs: [{{"origin":"XXX","destination":"YYY","departureDate":"YYYY-MM-DD"}}].
For hotels set hotels_city (default to destination).

Query:
{query}
"""


def extract_info(state: TravelState) -> TravelState:
    """Extract structured travel params from user query using LLM."""
    prompt = EXTRACT_PROMPT.format(query=state.user_query)
    response = llm.invoke(prompt)
    text = response.content.strip()
    # Strip markdown code blocks if present
    # if text.startswith("```"):
    #     lines = text.split("\n")
    #     if lines[0].startswith("```"):
    #         lines = lines[1:]
    #     if lines and lines[-1].strip() == "```":
    #         lines = lines[:-1]
    #     text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end != -1:
        text = text[start:end]
    try:
        data = json.loads(text)
        needs_flights = data.get("needs_flights")
        needs_hotels = data.get("needs_hotels")
        if needs_flights is not None:
            state.needs_flights = bool(needs_flights)
        if needs_hotels is not None:
            state.needs_hotels = bool(needs_hotels)
        state.origin = data.get("origin") or state.origin
        state.destination = data.get("destination") or state.destination
        state.departure_date = data.get("departure_date") or state.departure_date
        state.return_date = data.get("return_date") or state.return_date
        state.hotels_city = data.get("hotels_city") or state.hotels_city
        state.check_in = data.get("check_in") or state.check_in
        state.check_out = data.get("check_out") or state.check_out
        legs = data.get("legs")
        if legs and isinstance(legs, list) and len(legs) > 1:
            state.legs = [
                {
                    "origin": lg.get("origin"),
                    "destination": lg.get("destination"),
                    "departureDate": lg.get("departureDate"),
                }
                for lg in legs
                if lg.get("origin") and lg.get("destination") and lg.get("departureDate")
            ]
        if state.hotels_city is None and state.destination:
            state.hotels_city = state.destination
        if state.needs_flights is None or state.needs_hotels is None:
            _infer_intent_from_params(state)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"JSON parse error: {e}\nModel output: {text[:500]}")
        _fallback_extract(state)
    return state


def _infer_intent_from_params(state: TravelState) -> None:
    """Infer needs_flights/needs_hotels from extracted params when LLM omits them."""
    q = state.user_query.lower()
    if state.needs_flights is None:
        state.needs_flights = bool(
            (state.origin and state.destination)
            or (state.legs and len(state.legs) > 0)
            or "flight" in q or "fly" in q or "plane" in q
        )
    if state.needs_hotels is None:
        state.needs_hotels = bool(
            (state.hotels_city or (state.destination and "hotel" in q))
            or "hotel" in q or "accommodation" in q or "stay" in q
        )


def _fallback_extract(state: TravelState) -> None:
    """Regex-based fallback when LLM JSON parsing fails."""
    q = state.user_query.lower()
    # Flights from X to Y (on/in) date
    m = re.search(
        r"(?:from|fly)\s+(\w+(?:\s+\w+)?)\s+to\s+(\w+(?:\s+\w+)?)(?:\s+(?:on|for|date)?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}))?",
        q,
        re.IGNORECASE,
    )
    if m:
        state.origin = normalize_location(m.group(1))
        state.destination = normalize_location(m.group(2))
        if m.group(3):
            state.departure_date = parse_date_from_text(m.group(3))
    # X to Y on date
    if not state.origin and not state.destination:
        m = re.search(r"(\w{3})\s+to\s+(\w{3})(?:\s+(?:on|for)\s*(\d{4}-\d{2}-\d{2}))?", q)
        if m:
            state.origin = m.group(1).upper()
            state.destination = m.group(2).upper()
            if m.group(3):
                state.departure_date = m.group(3)
    # Date pattern standalone
    if not state.departure_date:
        state.departure_date = parse_date_from_text(state.user_query)
    if state.destination and not state.hotels_city:
        state.hotels_city = state.destination
    _infer_intent_from_params(state)


def generate_response(state: TravelState) -> TravelState:
    """Generate final natural language response from flights/hotels."""
    prompt = f"""You are a travel assistant.

User query:
{state.user_query}

Flights:
{state.flights or []}

Hotels:
{state.hotels or []}

Errors (if any):
{state.errors or []}

Warnings (if any):
{state.warnings or []}

Write a helpful, concise travel recommendation. If there are errors, acknowledge them and suggest corrections.
"""
    response = llm.invoke(prompt)
    state.response = response.content
    return state


def run_agent(user_query: str) -> TravelState:
    """Main agent pipeline. Agent decides which tools to call based on query intent."""
    state = TravelState(user_query=user_query)
    state = extract_info(state)
    if state.needs_flights:
        state = flight_tool(state)
    if state.needs_hotels:
        state = hotel_tool(state)
    state = generate_response(state)
    return state
