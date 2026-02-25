from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class TravelState(BaseModel):

    user_query: str

    # extracted info
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None

    hotels_city: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None

    # intent flags
    needs_flights: bool = True
    needs_hotels: bool = True

    # results
    flights: Optional[List[Dict]] = Field(default_factory=list)
    hotels: Optional[List[Dict]] = Field(default_factory=list)

    # agent output
    response: Optional[str] = None

    # production tracking
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    legs: Optional[List[Dict]] = None