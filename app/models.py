from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime


Base = declarative_base()

class Flight(Base):
    __tablename__ = 'flights'

    id = Column(Integer, primary_key=True, index=True)

    # Flight identifiers
    icao24 = Column(String(255), nullable=True)
    origin_country = Column(String(255))

    # Locations
    source_location = Column(String(255))
    destination_location = Column(String(255))
    source_code = Column(String(10), index=True)
    destination_code = Column(String(10), index=True)  

    # Scheduled and actual times
    scheduled_departure = Column(DateTime, nullable=True)
    actual_departure = Column(DateTime, nullable=True)
    scheduled_arrival = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)

    # Delay and status
    arrival_delay = Column(Integer, nullable=True) 
    departure_delay = Column(Integer, nullable=True)  
    status = Column(String(30))  

    # Real-time flight data (if available)
    altitude = Column(Float, nullable=True)
    velocity = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    on_ground = Column(Integer, default=0)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), index=True)
    flight_id = Column(String(255), nullable=True)
    airport_code = Column(String(10), nullable=True)
    subscription_type = Column(String(10), nullable=False)