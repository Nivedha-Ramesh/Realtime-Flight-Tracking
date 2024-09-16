# app/flight_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import union
from typing import List, Optional
from datetime import datetime, timedelta
from app.models import *
from app.schema import FlightBase
from fastapi import Query
import os
import logging
from app.database import async_session
from app.flight_data_service import process_flight_data
from fastapi.responses import HTMLResponse, JSONResponse

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/flights",
    tags=["flights"],
    responses={404: {"description": "Not found"}},
)


# Dependency to get async DB session
async def get_db():
    async with async_session() as db:
        yield db


# Route to get a paginated list of flights
@router.get("/", response_model=List[FlightBase])
async def read_flights(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Fetch paginated list of flights with optional skip and limit.
    """
    result = await db.execute(select(Flight).offset(skip).limit(limit))
    flights = result.scalars().all()
    return flights

# Route to update flight data (calls the background data fetching service)
@router.get("/update")
async def update_data(db: AsyncSession = Depends(get_db)):
    """
    Trigger flight data update from external API.
    """
    await process_flight_data()
    return {"message": "Flight data updated successfully."}

@router.get("/summary", response_model=dict)
async def get_airport_summary(airport_code: str = None, time_range: str = 'last_24_hours', db: AsyncSession = Depends(get_db)):

    """
    Get summary of inbound/outbound flights for a given airport or globally for the last 24 hours or today.
    """
    now = datetime.now()    
    if time_range == 'last_24_hours':
        start_time = now - timedelta(hours=24)
    else:
        start_time = datetime.combine(now.date(), datetime.min.time())
    if airport_code:
        result = await db.execute(
            select(Flight).where(
                (Flight.scheduled_departure >= start_time) | (Flight.scheduled_arrival >= start_time)
            ).where(
                (Flight.source_code == airport_code) | (Flight.destination_code == airport_code)
            )
        )
    else:
        result = await db.execute(
            select(Flight).where(
                (Flight.scheduled_departure >= start_time) | (Flight.scheduled_arrival >= start_time)
            )
        )

    flights = result.scalars().all()

    if not flights:
        raise HTTPException(status_code=404, detail="No flights found.")

    # Distinguish between inbound and outbound flights
    inbound_flights = [flight for flight in flights if flight.destination_code == airport_code]
    outbound_flights = [flight for flight in flights if flight.source_code == airport_code]

    # Create the summary for both inbound and outbound flights
    def create_summary(flight_list):
        return {
            "on_time": sum(1 for flight in flight_list if 
                            (flight.departure_delay == 0 or flight.arrival_delay == 0) and 
                            flight.status in ["active", "on_time", "scheduled", "in_flight"]),
            "delayed": sum(1 for flight in flight_list if 
                            (flight.departure_delay > 0 or flight.arrival_delay > 0) and 
                            flight.status != "cancelled"),
            "cancelled": sum(1 for flight in flight_list if flight.status == "cancelled"),
            "landed": sum(1 for flight in flight_list if flight.status == "landed"),
            "delayed": sum(1 for flight in flight_list if 
                        (flight.departure_delay > 0 or flight.arrival_delay > 0) and 
                        flight.status in ["delayed", "active"]),
            "diverted": sum(1 for flight in flight_list if flight.status == "diverted"),
            "incident": sum(1 for flight in flight_list if flight.status == "incident"),
        }

    inbound_summary = create_summary(inbound_flights)
    outbound_summary = create_summary(outbound_flights)

    summary = {
        "inbound_flights": inbound_summary,
        "outbound_flights": outbound_summary,
    }

    return summary

# Route to provide real-time data for flight status dashboard
# Endpoint 1: Serve the dashboard HTML page
@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_page():
    """
    Serve the flight dashboard HTML page.
    """
    file_path = os.path.join("static", "index.html")
    with open(file_path, 'r') as html_file:
        return html_file.read()


# Route to fetch available airports
@router.get("/airports")
async def get_airports(db: AsyncSession = Depends(get_db)):
    """
    Fetch unique airport codes from source and destination airports.
    """
    query = union(
        select(Flight.source_code),
        select(Flight.destination_code)
    )

    result = await db.execute(query)
    unique_airports = list(set(result.scalars().all()))
    return unique_airports

# Endpoint 2: Serve the flight data to populate the dashboard
@router.get("/dashboard/data")
async def get_dashboard_data(airport: str = None, time_range: str = 'last_24_hours', db: AsyncSession = Depends(get_db)):
    """
    Serve flight data to populate the dashboard based on the selected time range and airport.
    """
    now = datetime.now()
    if time_range == 'last_24_hours':
        start_time = now - timedelta(hours=24)
    elif time_range == 'today':
        start_time = datetime.combine(now.date(), datetime.min.time())
    else:
        start_time = now - timedelta(hours=24)

    # Base query for flights where scheduled departure or arrival is within the time range
    query = select(Flight).where(
        (Flight.scheduled_departure >= start_time) | (Flight.scheduled_arrival >= start_time)
    )

    # If airport is specified and not empty, filter flights for that airport
    if airport and airport != '':
        query = query.where(
            (Flight.source_code == airport) | (Flight.destination_code == airport)
        )


    # Execute the query
    result = await db.execute(query)
    flights = result.scalars().all()

    # Prepare the statistics
    total_flights = len(flights)
    on_time_flights = sum(
        1 for flight in flights 
        if flight.arrival_delay == 0 and flight.departure_delay == 0 and flight.status in ["scheduled", "active", "on_time", "in_flight"]
    )

    delayed_flights = sum(1 for flight in flights if flight.status == "delayed")
    cancelled_flights = sum(1 for flight in flights if flight.status == "cancelled")
    landed_flights = sum(1 for flight in flights if flight.status == "landed")

    # Prepare flight details for the table
    flight_details = [
        {
            "icao": flight.icao24,
            "status": flight.status,
            "scheduled_departure": flight.scheduled_departure.strftime('%Y-%m-%d %H:%M'),
            "scheduled_arrival": flight.scheduled_arrival.strftime('%Y-%m-%d %H:%M'),
            "source": flight.source_code,
            "destination": flight.destination_code
        }
        for flight in flights
    ]

    # Return the data as a JSON response
    return JSONResponse({
        "total_flights": total_flights,
        "on_time": on_time_flights,
        "delayed": delayed_flights,
        "cancelled": cancelled_flights,
        "landed": landed_flights,
        "flights": flight_details,
        "real_time_updates": [len(flights)]
    })

# Route to subscribe to flight or airport updates
@router.post("/subscribe")
async def subscribe_to_updates(client_id: str, flight_id: Optional[str] = None, airport_code: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Subscribe to flight or airport updates based on the given client ID, flight, or airport.
    """
    if not flight_id and not airport_code:
        raise HTTPException(status_code=400, detail="You must provide either a flight_id or an airport_code.")
    
    subscription_type = 'flight' if flight_id else 'airport'

    query = select(Subscription).where(
        (Subscription.flight_id == flight_id) | (Subscription.airport_code == airport_code),
        Subscription.client_id == client_id
    )
    existing_subscription = await db.execute(query)
    existing_subscription = existing_subscription.scalar_one_or_none()

    if existing_subscription:
        return {"message": "You are already subscribed to this flight or airport."}
    
    # Create new subscription
    new_subscription = Subscription(
        client_id=client_id,
        flight_id=flight_id if flight_id else None,
        airport_code=airport_code if airport_code else None,
        subscription_type=subscription_type
    )

    db.add(new_subscription)
    await db.commit()

    return {"message": f"Successfully subscribed to {subscription_type} updates."}

# Route to get data for a specific flight by icao
@router.get("/{icao}", response_model=FlightBase)
async def read_flight(icao: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch flight details by callsign.
    """
    result = await db.execute(select(Flight).where(Flight.icao24 == icao))
    flight = result.scalar_one_or_none()
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight

# Route to get all flights associated with an airport (source or destination)
@router.get("/airport/{airport_code}", response_model=dict)
async def get_flights_by_airport(airport_code: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch inbound and outbound flights for a given airport code.
    """
    inbound_result = await db.execute(
        select(Flight).where(Flight.destination_code == airport_code)
    )
    inbound_flights = inbound_result.scalars().all()

    outbound_result = await db.execute(
        select(Flight).where(Flight.source_code == airport_code)
    )
    outbound_flights = outbound_result.scalars().all()

    return {
        "inbound_flights": [FlightBase.from_orm(flight) for flight in inbound_flights],
        "outbound_flights": [FlightBase.from_orm(flight) for flight in outbound_flights],
    }
