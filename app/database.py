# app/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Define the database URL, using SQLite for simplicity
DATABASE_URL = "sqlite+aiosqlite:///./flights.db"  

# Create an asynchronous engine for the SQLite database
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a session factory for creating database sessions
async_session = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False  
)
