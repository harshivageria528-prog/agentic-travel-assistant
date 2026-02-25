"""
Flight search tool using Amadeus API.
Handles single-leg, round-trip, and multi-leg searches with validation.
"""
from src.state import TravelState
from src.services.amadeus_service import (
    search_flights,
    search_flights_multi_leg,
    validate_location,
    validate_departure_date,
    is_past_date,
)


def flight_tool(state: TravelState) -> TravelState:
    """Fetch flights from Amadeus and populate state.flights."""
    errors = list(state.errors or [])
    warnings = list(state.warnings or [])

    # Multi-leg
    legs = state.legs
    if legs and len(legs) > 1:
        try:
            flights = search_flights_multi_leg(legs)
            state.flights = flights
        except ValueError as e:
            errors.append(str(e))
            state.flights = []
        except Exception as e:
            errors.append(f"Flight search failed: {e}")
            state.flights = []
        state.errors = errors if errors else None
        state.warnings = warnings if warnings else None
        return state

    # Single or round-trip
    origin = state.origin
    destination = state.destination
    departure_date = state.departure_date

    if not origin or not destination:
        if not origin and not destination:
            pass  # No flight search needed
        else:
            errors.append("Both origin and destination are required for flight search.")
        state.errors = errors if errors else None
        return state

    if not departure_date:
        errors.append("Departure date is required for flight search.")
        state.errors = errors if errors else None
        return state

    # Past date check
    if is_past_date(departure_date):
        errors.append("Departure date cannot be in the past.")
        state.flights = []
        state.errors = errors
        return state

    # Return date validation
    return_date = state.return_date
    if return_date and is_past_date(return_date):
        errors.append("Return date cannot be in the past.")
        state.flights = []
        state.errors = errors
        return state

    # Location validation
    valid_orig, msg_orig = validate_location(origin)
    if not valid_orig:
        errors.append(f"Origin '{origin}': {msg_orig}")
        state.flights = []
        state.errors = errors
        return state

    valid_dest, msg_dest = validate_location(destination)
    if not valid_dest:
        errors.append(f"Destination '{destination}': {msg_dest}")
        state.flights = []
        state.errors = errors
        return state

    try:
        flights = search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=1,
            max_results=10,
        )
        state.flights = flights
        if not flights:
            warnings.append("No flights found for the given route and dates.")
    except ValueError as e:
        errors.append(str(e))
        state.flights = []
    except Exception as e:
        errors.append(f"Flight search failed: {e}")
        state.flights = []

    state.errors = errors if errors else None
    state.warnings = warnings if warnings else None
    return state
