# FastAPI Backend for OWPML RAG Project

This project provides a FastAPI backend for parsing HWP and HWPX documents, integrating with the OWPML1 repository's parsing capabilities.

## Setup and Run Locally (without Docker)

To run the FastAPI application directly on your local machine, follow these steps:

1.  **Navigate to the `back` directory:**
    ```bash
    cd C:\한컴개발\파이썬\back
    ```

2.  **Install Python Dependencies:**
    Install the required Python packages using pip:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Java Development Kit (JDK) and Set `JAVA_HOME`:**
    HWP file parsing requires a Java Development Kit (JDK) to be installed on your system. Ensure that `JAVA_HOME` environment variable is set to your JDK installation path. If not, download and install a JDK (e.g., from [Adoptium](https://adoptium.net/)) and configure `JAVA_HOME`.

4.  **Copy `hwplib-1.1.8.jar`:**
    The `hwplib-1.1.8.jar` file, essential for HWP parsing, needs to be copied from the `OWPML1` project to the `back/app/python-hwplib/` directory. You can do this manually or use the following command:
    ```bash
    copy "C:\한컴개발\파이썬\OWPML1\python-hwplib\hwplib-1.1.8.jar" "C:\한컴개발\파이썬\back\app\python-hwplib\"
    ```

5.  **Run the FastAPI Application:**
    Once all dependencies are installed and the JAR file is in place, start the FastAPI application using Uvicorn:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The API will be accessible at `http://localhost:8000`.

## Setup and Run with Docker

To run the FastAPI application using Docker, follow these steps:

1.  **Navigate to the `back` directory:**
    ```bash
    cd C:\한컴개발\파이썬\back
    ```

2.  **Build the Docker Image:**
    ```bash
    docker build -t owpml-fastapi-backend .
    ```
    This command builds a Docker image named `owpml-fastapi-backend`. This process includes installing the JDK and Python dependencies, which may take some time.

3.  **Run the Docker Container:**
    ```bash
    docker run -d --name owpml-parser -p 8000:8000 owpml-fastapi-backend
    ```
    This will start the container in the background, mapping port 8000 on your host to port 8000 in the container.

## API Endpoint

Once the application is running (either locally or via Docker), you can access the API at:

-   **Swagger UI:** `http://localhost:8000/docs`
-   **File Upload and Parse Endpoint:** `http://localhost:8000/api/v1/parsing/upload-and-parse/`
    -   This endpoint accepts `.hwp` and `.hwpx` file uploads.

## Project Structure

```
back/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   └── parsing.py
│   │       ├── __init__.py
│   │       └── router.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── jpype_setup.py
│   │   ├── logging.py
│   │   └── parser.py
│   ├── main.py
│   └── python-hwplib/  # Contains hwplib-1.1.8.jar for HWP parsing
├── Dockerfile
├── requirements.txt
└── README.md
```
