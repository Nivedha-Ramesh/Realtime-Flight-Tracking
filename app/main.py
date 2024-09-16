from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import asyncio
import os
from app.models import Base
from app.flight_data_service import process_flight_data
from app.database import engine
from app.flight_routes import router as flight_router

app = FastAPI(
    title="Real-Time Flight Tracking Service",
    description="An API to provide real-time flight updates.",
    version="1.0.0",
)

# Serve static files (including index.html) from the /static directory
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")

# Function to create database tables asynchronously
async def create_tables():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Error creating tables: {e}")

# Function to handle startup events, such as table creation and starting background tasks
@app.on_event("startup")
async def startup_event():
    # Ensure tables are created on startup
    await create_tables()

    # Start background task to periodically fetch flight data
    asyncio.create_task(periodic_fetch())

# Function to fetch flight data periodically every minute
async def periodic_fetch():
    while True:
        try:
            await process_flight_data()  # Fetch and process the latest flight data
        except Exception as e:
            print(f"Error during flight data fetch: {e}")
        await asyncio.sleep(60)  # Sleep for 1 minute before fetching again

# Include the flight routes in the application
app.include_router(flight_router)
