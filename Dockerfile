# Use an official Python runtime as a parent image
FROM python:3.9

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libffi-dev \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install each package individually
RUN pip install --no-cache-dir discord.py>=2.0.0
RUN pip install --no-cache-dir python-dotenv
RUN pip install --no-cache-dir requests
RUN pip install --no-cache-dir asyncio
RUN pip install --no-cache-dir logging
RUN pip install --no-cache-dir discord-py-interactions
RUN pip install --no-cache-dir PyNaCl

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME DiscordTTCBOT

# Run bot.py when the container launches
CMD ["python", "bot.py"]