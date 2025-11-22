import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.knowledge_graph import check_neo4j_connection, close_neo4j_driver
from app.routers import auth, users, documents
from app.middlewares.cors import add_cors_middleware
from app.middlewares.logging import LoggingMiddleware

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Manage Life Cycle (Open/Close Neo4j) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # App Startup: Check Neo4j connection
    if not await check_neo4j_connection():
        logger.warning("Could not connect to Neo4j!")
    else:
        logger.info("Connected to Neo4j successfully.")
    
    yield # Let the app run
    
    # App Shutdown: Close connection
    await close_neo4j_driver()
    logger.info("Neo4j driver closed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan 
)

# Add Middlewares
add_cors_middleware(app)
app.add_middleware(LoggingMiddleware)

# Include Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)

# Root Endpoint
@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
