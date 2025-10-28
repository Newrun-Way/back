FROM python:3.9-slim-buster

WORKDIR /app

# Install Java Development Kit (JDK) for JPype1
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the python-hwplib directory (containing the JAR file)
# from the OWPML1 project into the app directory
COPY ../OWPML1/python-hwplib /app/app/python-hwplib

# Copy the rest of the application code
COPY ./app /app/app

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
