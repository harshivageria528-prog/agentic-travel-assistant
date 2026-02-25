from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class TravelState(BaseModel):
    user_query: str

    # Flight params
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    legs: Optional[List[Dict[str, str]]] = None  # Multi-leg: [{origin, destination, departureDate}]

    # Hotel params
    hotels_city: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None

    # Results
    flights: Optional[List[Dict]] = None
    hotels: Optional[List[Dict]] = None
    response: Optional[str] = None

    # Edge case feedback
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None

    class Config:
        extra = "allow"  # Allow extra fields for flexibility
