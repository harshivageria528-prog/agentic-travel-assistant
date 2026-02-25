from langgraph.graph import StateGraph, END

from src.state import TravelState
from src.tools.flight_tool import flight_tool
from src.tools.hotel_tool import hotel_tool


def decide(state: TravelState):

    query = state.user_query.lower()

    if "flight" in query:
        return "flight"

    if "hotel" in query:
        return "hotel"

    return END


builder = StateGraph(TravelState)

builder.add_node("flight", flight_tool)
builder.add_node("hotel", hotel_tool)

builder.set_entry_point("flight")

builder.add_edge("flight", END)
builder.add_edge("hotel", END)

travel_agent = builder.compile()