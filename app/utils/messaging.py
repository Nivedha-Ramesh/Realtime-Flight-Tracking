import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost/"


# Function to send a message to RabbitMQ
async def send_notifications(airport_code: str, message: str, client_id: str):
    # Connect to RabbitMQ server
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    
    async with connection:
        # Open a channel
        channel = await connection.channel()

        # Declare a topic exchange
        exchange = await channel.declare_exchange('flight_updates_exchange', aio_pika.ExchangeType.TOPIC)

        # Generate the routing key using client_id and airport_code
        routing_key = f"{client_id}.{airport_code}"
        
        # Publish message to the exchange with the routing key
        await exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=routing_key
        )
