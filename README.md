# InvestiGraph

## Project Structure
- **`backend/`**: FastAPI application, Database, Docker config.
- **`frontend/`**: React application.

## How to Run Locally

### 1. Backend
The backend code is now in the `backend/` folder. You need to run commands from there.

```bash
# Open a new terminal
cd backend

# Create/Activate virtual environment (if you haven't)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```
*Backend will run at http://localhost:8000*

### 2. Frontend
```bash
# Open a new terminal
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```
*Frontend will run at http://localhost:5173*

## How to Run with Docker

The `docker-compose.yml` is located in the `backend/` directory and currently manages the Backend, Database, and Neo4j.

```bash
cd backend
docker-compose up --build
```
