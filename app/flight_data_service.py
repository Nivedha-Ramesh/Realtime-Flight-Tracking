# app/flight_data_service.py

import aiohttp
import asyncio
import os
import logging
from sqlalchemy.future import select
from datetime import datetime
from app.models import Flight, Subscription
from app.database import async_session
from app.utils.messaging import send_notifications

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch API key from environment variable
API_KEY = os.getenv("API_KEY")
API_URL = f"http://api.aviationstack.com/v1/flights?access_key={API_KEY}"

# Fetch flight data from AviationStack API asynchronously
async def fetch_flight_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                response.raise_for_status()
                data = await response.json()
                return data['data']  # Return flight data
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching flight data: {e}")
        return []
        
# Process the flight data, store it in the database, and notify when data is updated
async def process_flight_data():
    flight_data = await fetch_flight_data()  # Fetch data from AviationStack API
    if not flight_data:
        logger.warning("No flight data fetched")
        return
    
    async with async_session() as session:
        for flight in flight_data:
            if not flight:
                continue

            # Extract flight details with safeguards
            flight_info = flight.get('flight')
            departure_info = flight.get('departure')
            arrival_info = flight.get('arrival')
            live_info = flight.get('live')
            airline_info = flight.get('airline')

            # Ensure the existence of nested fields before accessing them
            icao = flight_info.get('icao') if flight_info else None
            source_location = departure_info.get('airport') if departure_info else None
            destination_location = arrival_info.get('airport') if arrival_info else None
            source_code = departure_info.get('icao') if departure_info else None
            destination_code = arrival_info.get('icao') if arrival_info else None

            # Safely handle the scheduled and actual times for departure and arrival
            scheduled_departure = departure_info.get('scheduled') if departure_info else None
            actual_departure = departure_info.get('actual') if departure_info else None
            scheduled_arrival = arrival_info.get('scheduled') if arrival_info else None
            actual_arrival = arrival_info.get('actual') if arrival_info else None

            # Compute departure and arrival delays
            departure_delay = 0
            if scheduled_departure:
                estimated_departure = departure_info.get('estimated', scheduled_departure) if departure_info else None
                if actual_departure:
                    departure_delay = (datetime.fromisoformat(actual_departure) - datetime.fromisoformat(scheduled_departure)).total_seconds() / 60
                elif estimated_departure:
                    departure_delay = (datetime.fromisoformat(estimated_departure) - datetime.fromisoformat(scheduled_departure)).total_seconds() / 60

            arrival_delay = 0
            if scheduled_arrival:
                estimated_arrival = arrival_info.get('estimated', scheduled_arrival) if arrival_info else None
                if actual_arrival:
                    arrival_delay = (datetime.fromisoformat(actual_arrival) - datetime.fromisoformat(scheduled_arrival)).total_seconds() / 60
                elif estimated_arrival:
                    arrival_delay = (datetime.fromisoformat(estimated_arrival) - datetime.fromisoformat(scheduled_arrival)).total_seconds() / 60

            # Flight status
            status = flight.get('flight_status', "Unknown")
            if arrival_delay == 0 and departure_delay == 0:
                if status == 'active':
                    status = "in_flight"
                elif status == 'scheduled':
                    status = "scheduled"
            else:
                status = "delayed"


            # Check if real-time 'live' data is available for the flight
            altitude = live_info.get('altitude') if live_info else None
            velocity = live_info.get('speed_horizontal') if live_info else None
            longitude = live_info.get('longitude') if live_info else None
            latitude = live_info.get('latitude') if live_info else None
            on_ground = live_info.get('is_ground') if live_info else 0



            # Create or update Flight instance
            flight_instance = Flight(
                icao24=icao,
                origin_country=airline_info.get('name'),
                source_location=source_location,
                destination_location=destination_location,
                source_code=source_code,
                destination_code=destination_code,
                scheduled_departure=datetime.fromisoformat(scheduled_departure.replace("Z", "")) if scheduled_departure else None,
                actual_departure=datetime.fromisoformat(actual_departure.replace("Z", "")) if actual_departure else None,
                scheduled_arrival=datetime.fromisoformat(scheduled_arrival.replace("Z", "")) if scheduled_arrival else None,
                actual_arrival=datetime.fromisoformat(actual_arrival.replace("Z", "")) if actual_arrival else None,
                arrival_delay=arrival_delay,
                departure_delay=departure_delay,
                status=status,
                altitude=altitude,
                velocity=velocity,
                longitude=longitude,
                latitude=latitude,
                on_ground=on_ground
            )

            # Insert or update the flight in the database
            await session.merge(flight_instance)

            # Handle status notifications
            if status in ["landed", "cancelled", "delayed", "incident", "diverted"]:
                query = select(Subscription).where(
                    (Subscription.airport_code == destination_code) | 
                    (Subscription.airport_code == source_code)
                )
                subscriptions = await session.execute(query)
                subscriptions = subscriptions.scalars().all()

                for subscription in subscriptions:
                    await handle_notifications(subscription, status, arrival_delay, source_code, destination_code, icao, source_location, destination_location)

        # Commit the changes to the database
        await session.commit()

# Handle notifications for each subscription
async def handle_notifications(subscription, status, arrival_delay, source_code, destination_code, icao, source_location, destination_location):
    if status == "cancelled":
        if subscription.airport_code == source_code:
            source_message = (
                f"Notification for {subscription.client_id}: "
                f"Departure Alert at {source_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has been cancelled."
            )
            await send_notifications(source_code, source_message, subscription.client_id)

        if subscription.airport_code == destination_code:
            destination_message = (
                f"Notification for {subscription.client_id}: "
                f"Arrival Alert at {destination_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has been cancelled."
            )
            await send_notifications(destination_code, destination_message, subscription.client_id)

    elif status == "delayed" and arrival_delay:
        if subscription.airport_code == destination_code:
            message = (
                f"Notification for {subscription.client_id}: "
                f"Arrival Alert at {destination_code}: Flight {icao} from {source_location} "
                f"is delayed by {arrival_delay} minutes."
            )
            await send_notifications(destination_code, message, subscription.client_id)

    elif status == "diverted":
        if subscription.airport_code == source_code:
            source_message = (
                f"Notification for {subscription.client_id}: "
                f"Departure Alert at {source_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has been diverted."
            )
            await send_notifications(source_code, source_message, subscription.client_id)

        if subscription.airport_code == destination_code:
            destination_message = (
                f"Notification for {subscription.client_id}: "
                f"Arrival Alert at {destination_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has been diverted."
            )
            await send_notifications(destination_code, destination_message, subscription.client_id)

    elif status == "incident":
        if subscription.airport_code == source_code:
            source_message = (
                f"Notification for {subscription.client_id}: "
                f"Departure Alert at {source_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has reported an incident."
            )
            await send_notifications(source_code, source_message, subscription.client_id)

        if subscription.airport_code == destination_code:
            destination_message = (
                f"Notification for {subscription.client_id}: "
                f"Arrival Alert at {destination_code}: Flight {icao} from {source_location} "
                f"to {destination_location} has reported an incident."
            )
            await send_notifications(destination_code, destination_message, subscription.client_id)