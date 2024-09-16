import asyncio
import aio_pika
import argparse
import re
import os
import signal
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read RabbitMQ URL from environment or use default
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
EXCHANGE_NAME = "flight_updates_exchange"


# Function to consume messages
async def consume_messages(client_id: str, airport_code: str):
    try:
        # Create a sanitized queue name by replacing invalid characters
        sanitized_client_id = re.sub(r'\W+', '_', client_id)
        queue_name = f"{sanitized_client_id}_queue"

        # Connect to RabbitMQ
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        logger.info(f"Connected to RabbitMQ at {RABBITMQ_URL}")

        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC)

            # Declare queue with sanitized name
            queue = await channel.declare_queue(queue_name, durable=True)

            # Bind the queue to the specific airport code
            routing_key = f"{sanitized_client_id}.{airport_code}"
            await queue.bind(exchange, routing_key)
            logger.info(f"Queue '{queue_name}' bound to routing key: {routing_key}")

            logger.info(f"Waiting for messages for {client_id}. To exit press CTRL+C")

            async def message_handler(message: aio_pika.IncomingMessage):
                async with message.process():
                    logger.info(f"[x] {client_id} received message: {message.body.decode()}")

            await queue.consume(message_handler)

            # Await a never-ending future to keep the consumer alive
            await asyncio.Future()
    
    except Exception as e:
        logger.error(f"Error in consumer: {e}")


# Command-line argument parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RabbitMQ Consumer")
    parser.add_argument("--client_id", required=True, help="Client ID")
    parser.add_argument("--airport_code", required=True, help="Single airport code")
    args = parser.parse_args()

    # Setup event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume_messages(args.client_id, args.airport_code))