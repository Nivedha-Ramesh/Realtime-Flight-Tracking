from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Define a Pydantic model for the Flight
class FlightBase(BaseModel):
    icao24: Optional[str]  # 24-bit ICAO aircraft identifier
    origin_country: Optional[str]  # The country of the airline's origin

    source_location: str  # Source airport name
    destination_location: str  # Destination airport name
    source_code: str  # IATA/ICAO code for the source airport
    destination_code: str  # IATA/ICAO code for the destination airport

    scheduled_departure: Optional[datetime]  # Scheduled departure time
    actual_departure: Optional[datetime]  # Actual departure time
    scheduled_arrival: Optional[datetime]  # Scheduled arrival time
    actual_arrival: Optional[datetime]  # Actual arrival time

    arrival_delay: Optional[int]  # Delay in minutes for arrival
    departure_delay: Optional[int]  # Delay in minutes for departure
    status: Optional[str]  # Flight status: landed, delayed, cancelled, etc.

    altitude: Optional[float]  # Altitude of the aircraft (if in flight)
    velocity: Optional[float]  # Ground speed of the aircraft (if in flight)
    longitude: Optional[float]  # Current longitude (if in flight)
    latitude: Optional[float]  # Current latitude (if in flight)

    on_ground: Optional[int]  # 1 if on the ground, 0 if airborne

    class Config:
        from_attributes = True

# Define a Pydantic model for Subscription
class SubscriptionBase(BaseModel):
    client_id: str  # ID of the subscribing client
    airport_code: Optional[str]  # Airport code the client subscribes to
    flight_id: Optional[str]  # Flight ID the client subscribes to 

    subscription_type: str  # Either 'flight' or 'airport'

    class Config:
        from_attributes = True