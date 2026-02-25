"""
Amadeus API integration for flights and hotels.
Handles authentication, flight search (single & multi-leg), hotel search,
and location validation.
"""
import os
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any

import requests
from dotenv import load_dotenv

load_dotenv()
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
BASE_URL = "https://test.api.amadeus.com"


def get_access_token() -> str:
    """Obtain OAuth2 access token for Amadeus API."""
    url = f"{BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Amadeus Auth Error: {response.text}")
    return response.json()["access_token"]


def _request(
    method: str,
    path: str,
    token: str,
    params: Optional[Dict] = None,
    json_body: Optional[Dict] = None,
) -> Dict:
    """Make authenticated request to Amadeus API."""
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if method.upper() == "POST" and json_body:
        headers["Content-Type"] = "application/vnd.amadeus+json"
    kwargs = {"headers": headers, "timeout": 15}
    if method.upper() == "GET":
        kwargs["params"] = params or {}
    else:
        kwargs["json"] = json_body or {}
    response = requests.request(method, url, **kwargs)
    if response.status_code == 204:
        return {}
    try:
        data = response.json()
    except Exception:
        raise Exception(f"Invalid JSON response: {response.text[:500]}")
    if response.status_code >= 400:
        errors = data.get("errors", [])
        msg = errors[0].get("detail", response.text) if errors else response.text
        raise Exception(f"Amadeus API error: {msg}")
    return data


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------
def parse_date(s: str) -> Optional[date]:
    """Parse YYYY-MM-DD string to date."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def is_past_date(date_str: str) -> bool:
    """Return True if date is in the past."""
    d = parse_date(date_str)
    return d is not None and d < date.today()


def validate_departure_date(date_str: str) -> Tuple[bool, str]:
    """
    Validate departure date. Returns (valid, error_message).
    """
    if not date_str:
        return True, ""
    d = parse_date(date_str)
    if d is None:
        return False, "Invalid date format. Use YYYY-MM-DD."
    if d < date.today():
        return False, "Departure date cannot be in the past."
    return True, ""


def validate_check_dates(check_in: str, check_out: str) -> Tuple[bool, str]:
    """Validate check-in and check-out dates for hotels."""
    ci = parse_date(check_in) if check_in else None
    co = parse_date(check_out) if check_out else None
    if ci and ci < date.today():
        return False, "Check-in date cannot be in the past."
    if ci and co and co <= ci:
        return False, "Check-out date must be after check-in."
    return True, ""


# ---------------------------------------------------------------------------
# Location validation
# ---------------------------------------------------------------------------
def validate_location(keyword: str, sub_type: str = "AIRPORT,CITY") -> Tuple[bool, Optional[str]]:
    """
    Validate that a location (IATA code or city name) exists in Amadeus.
    Returns (is_valid, resolved_iata_code or error_message).
    """
    if not keyword or not isinstance(keyword, str):
        return False, "Location is required."
    kw = keyword.strip().upper()[:3]  # IATA codes are 3 chars
    if len(kw) < 2:
        return False, "Location code must be at least 2 characters."
    try:
        token = get_access_token()
        data = _request(
            "GET",
            "/v1/reference-data/locations",
            token,
            params={"keyword": kw, "subType": sub_type},
        )
        locations = data.get("data") or []
        if not locations:
            return False, f"Location '{keyword}' not found. Use a valid IATA city/airport code (e.g. NYC, LON, PAR)."
        # Prefer exact match
        for loc in locations:
            if loc.get("iataCode", "").upper() == kw.upper():
                return True, loc.get("iataCode", kw)
        return True, locations[0].get("iataCode", kw)
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Flight search
# ---------------------------------------------------------------------------
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    max_results: int = 10,
) -> List[Dict]:
    """
    Search for one-way or round-trip flight offers.
    Returns list of flight offer dicts.
    """
    valid_orig, resolved_orig = validate_location(origin)
    if not valid_orig:
        raise ValueError(resolved_orig or "Invalid origin")
    valid_dest, resolved_dest = validate_location(destination)
    if not valid_dest:
        raise ValueError(resolved_dest or "Invalid destination")
    ok, err = validate_departure_date(departure_date)
    if not ok:
        raise ValueError(err)
    if return_date:
        ok, err = validate_departure_date(return_date)
        if not ok:
            raise ValueError(err)

    token = get_access_token()
    params = {
        "originLocationCode": resolved_orig,
        "destinationLocationCode": resolved_dest,
        "departureDate": departure_date,
        "adults": adults,
        "max": max_results,
    }
    if return_date:
        params["returnDate"] = return_date

    data = _request("GET", "/v2/shopping/flight-offers", token, params=params)
    return _normalize_flight_offers(data.get("data") or [])


def search_flights_multi_leg(legs: List[Dict[str, str]], adults: int = 1) -> List[Dict]:
    """
    Search for multi-leg flight offers.
    legs: [{"origin": "NYC", "destination": "LON", "departureDate": "2025-03-15"}, ...]
    """
    if not legs or len(legs) > 6:
        raise ValueError("Provide 1-6 legs. Each leg needs origin, destination, departureDate.")

    origin_destinations = []
    for i, leg in enumerate(legs):
        o = (leg.get("origin") or "").strip().upper()
        d = (leg.get("destination") or "").strip().upper()
        dep = leg.get("departureDate", "").strip()
        if not all([o, d, dep]):
            raise ValueError(f"Leg {i+1} must have origin, destination, departureDate.")
        valid_o, res_o = validate_location(o)
        if not valid_o:
            raise ValueError(f"Leg {i+1} origin: {res_o}")
        valid_d, res_d = validate_location(d)
        if not valid_d:
            raise ValueError(f"Leg {i+1} destination: {res_d}")
        ok, err = validate_departure_date(dep)
        if not ok:
            raise ValueError(f"Leg {i+1}: {err}")
        origin_destinations.append({
            "id": str(i + 1),
            "originLocationCode": res_o,
            "destinationLocationCode": res_d,
            "departureDateTimeRange": {"date": dep, "time": "10:00:00"},
        })

    body = {
        "currencyCode": "USD",
        "originDestinations": origin_destinations,
        "travelers": [{"id": "1", "travelerType": "ADULT"}],
        "sources": ["GDS"],
        "searchCriteria": {"maxFlightOffers": 10},
    }

    token = get_access_token()
    data = _request("POST", "/v2/shopping/flight-offers", token, json_body=body)
    return _normalize_flight_offers(data.get("data") or [])


def _normalize_flight_offers(offers: List[Dict]) -> List[Dict]:
    """Convert Amadeus flight offers to a simplified schema."""
    out = []
    for offer in offers:
        itineraries = offer.get("itineraries") or []
        if not itineraries:
            continue
        segs = itineraries[0].get("segments") or []
        dep = segs[0].get("departure", {}).get("at", "") if segs else ""
        arr = segs[-1].get("arrival", {}).get("at", "") if segs else ""
        price_info = offer.get("price") or {}
        total = price_info.get("total", "")
        currency = price_info.get("currency", "EUR")
        airlines = offer.get("validatingAirlineCodes") or []
        airline = airlines[0] if airlines else ""
        legs_detail = []
        for it in itineraries:
            for seg in it.get("segments", []):
                legs_detail.append({
                    "departure": seg.get("departure", {}).get("at"),
                    "arrival": seg.get("arrival", {}).get("at"),
                    "carrier": seg.get("carrierCode"),
                    "flightNumber": seg.get("number"),
                })
        out.append({
            "id": offer.get("id"),
            "price": total,
            "currency": currency,
            "airline": airline,
            "departure": dep,
            "arrival": arr,
            "legs": legs_detail,
        })
    return out


# ---------------------------------------------------------------------------
# Hotel search
# ---------------------------------------------------------------------------
def search_hotels(
    city_code: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    adults: int = 1,
    max_hotels: int = 5,
) -> List[Dict]:
    """
    Search for hotels in a city using Amadeus Hotel List + Hotel Offers.
    1. Get hotel IDs by city code
    2. Fetch offers for those hotels (if dates provided)
    """
    valid, resolved = validate_location(city_code, sub_type="CITY,AIRPORT")
    if not valid:
        raise ValueError(resolved or "Invalid city/location")

    check_in = check_in or (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    check_out = check_out or (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
    ok, err = validate_check_dates(check_in, check_out)
    if not ok:
        raise ValueError(err)

    token = get_access_token()

    # 1. Get hotel IDs by city
    list_data = _request(
        "GET",
        "/v1/reference-data/locations/hotels/by-city",
        token,
        params={"cityCode": resolved},
    )
    hotel_ids = []
    for h in list_data.get("data") or []:
        hid = h.get("hotelId")
        if hid:
            hotel_ids.append(hid)
    if not hotel_ids:
        return []

    # Limit to avoid huge responses
    hotel_ids = hotel_ids[:max_hotels * 2]  # Request more in case some have no offers
    hotel_ids_str = ",".join(hotel_ids)

    # 2. Get hotel offers
    try:
        offers_data = _request(
            "GET",
            "/v3/shopping/hotel-offers",
            token,
            params={
                "hotelIds": hotel_ids_str,
                "adults": adults,
                "checkInDate": check_in,
                "checkOutDate": check_out,
            },
        )
    except Exception:
        # Hotel offers API may not return data for all cities; fallback to list
        return _hotels_from_list(list_data.get("data") or [], resolved)

    offers_list = offers_data.get("data") or []
    return _normalize_hotel_offers(offers_list, resolved)


def _hotels_from_list(hotels_raw: List[Dict], city: str) -> List[Dict]:
    """Fallback when hotel offers are unavailable."""
    out = []
    for h in hotels_raw[:10]:
        name = h.get("name") or h.get("hotelId", "Hotel")
        out.append({
            "hotelId": h.get("hotelId"),
            "name": name,
            "city": city,
            "price": None,
            "currency": None,
            "checkIn": None,
            "checkOut": None,
        })
    return out


def _normalize_hotel_offers(offers: List[Dict], city: str) -> List[Dict]:
    """Convert Amadeus hotel offers to simplified schema."""
    out = []
    for o in offers:
        hotel = o.get("hotel") or {}
        offer = (o.get("offers") or [{}])[0]
        price_info = offer.get("price") or {}
        total = price_info.get("total")
        currency = price_info.get("currency", "EUR")
        check_in = offer.get("checkInDate")
        check_out = offer.get("checkOutDate")
        out.append({
            "hotelId": hotel.get("hotelId"),
            "name": hotel.get("name", "Hotel"),
            "city": city,
            "price": total,
            "currency": currency,
            "checkIn": check_in,
            "checkOut": check_out,
        })
    return out
