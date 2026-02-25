"""
Hotel search tool using Amadeus API.
Populates hotels dynamically from Amadeus Hotel List + Hotel Offers.
"""
from src.state import TravelState
from src.services.amadeus_service import search_hotels, validate_location, validate_check_dates


def hotel_tool(state: TravelState) -> TravelState:
    """Fetch hotels from Amadeus and populate state.hotels."""
    errors = list(state.errors or [])
    warnings = list(state.warnings or [])

    city = state.hotels_city or state.destination
    if not city:
        state.errors = errors if errors else None
        return state

    # Validate city/location
    valid, msg = validate_location(city, sub_type="CITY,AIRPORT")
    if not valid:
        errors.append(f"Hotel city '{city}': {msg}")
        state.hotels = []
        state.errors = errors
        return state

    check_in = state.check_in
    check_out = state.check_out

    try:
        hotels = search_hotels(
            city_code=city,
            check_in=check_in,
            check_out=check_out,
            adults=1,
            max_hotels=10,
        )
        state.hotels = hotels
        if not hotels:
            warnings.append(f"No hotels found for {city}.")
    except ValueError as e:
        errors.append(str(e))
        state.hotels = []
    except Exception as e:
        errors.append(f"Hotel search failed: {e}")
        state.hotels = []

    state.errors = errors if errors else None
    state.warnings = warnings if warnings else None
    return state
