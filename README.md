# InvestiGraph
InvestiGraph is an advanced financial analysis tool that leverages Knowledge Graphs and GraphRAG (Retrieval-Augmented Generation) to extract, structure, and query insights from SEC 10-K documents.
## 🚀 Work Technique
The system employs a sophisticated pipeline to transform unstructured financial text into a structured knowledge graph:
1.  **Data Ingestion**: Downloads and parses SEC 10-K filings using `sec-edgar-downloader` and `beautifulsoup4`.
2.  **Graph Extraction**: Utilizes LLMs (Llama 3.1 via LiteLLM) to intelligently extract entities (Companies, People, Products) and relationships (CEO_OF, COMPETES_WITH, etc.) from text chunks.
3.  **Graph Storage**: Stores the extracted knowledge in a **Neo4j** graph database, ensuring data isolation per user and document.
4.  **GraphRAG Querying**: Enhances RAG by querying the knowledge graph for relevant connections based on user questions, providing context-aware answers that standard vector search might miss.
5.  **Reranking**: Uses a Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to re-score and rank the retrieved documents, ensuring the most relevant context is passed to the LLM.
## 🏗️ Project Structure
- **`backend/`**: The core API and logic.
    - **`app/`**: FastAPI application source code.
        - **`knowledge_graph.py`**: Core logic for graph extraction, storage, and querying.
        - **`sec_service.py`**: Handling SEC document downloading and processing.
        - **`routers/`**: API endpoints for auth, users, and documents.
- **`frontend/`**: The user interface.
    - Built with React and Vite for a fast, modern experience.
    - Uses Tailwind CSS for styling and Framer Motion for animations.
## 🛠️ Tech Stack
### Backend
- **Framework**: FastAPI
- **Database**: Neo4j (Graph), PostgreSQL (User data via SQLAlchemy/AsyncPG)
- **AI/LLM**: LiteLLM (Llama 3.1), Sentence Transformers (Embeddings & Reranking)
- **Reranker**: Cross-Encoder (`ms-marco-MiniLM-L-6-v2`)
- **Tools**: Tenacity (Retries), Pydantic (Validation)
### Frontend
- **Framework**: React (Vite)
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **Routing**: React Router DOM
- **Animation**: Framer Motion
## 🚦 Getting Started
### Prerequisites
- **Docker** & **Docker Compose** (for Backend & Databases)
- **Node.js** (v18+ recommended) & **npm** (for Frontend)
### Backend Setup
1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Create a `.env` file (based on `.env.example` if available) and configure your environment variables (LLM API keys, Database credentials, etc.).
    ```env
    PROJECT_NAME="Investi-Graph"
    # `openssl rand -hex 32` in git bash or use a web key generator
    JWT_SECRET_KEY="your_super_secret_key_here"
    JWT_ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    # --- DB Settings (For Docker Compose) ---
    DATABASE_USER=postgres
    DATABASE_PASSWORD=mysecretpassword
    DATABASE_NAME=postgres
    DATABASE_HOST=localhost # <-- Use Docker service name "db" from docker-compose.yml. If running locally, change to "localhost"
    DATABASE_PORT=5432
    # Database (Using postgresql+psycopg)
    # Format: dialect+driver://username:password@host:port/database_name
    DATABASE_URL="postgresql+psycopg://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_NAME}"
    LLM_PROVIDER="groq"
    LLM_API_KEY="gsk_..."
    # --- Neo4j Graph Database Settings ---
    NEO4J_URI=bolt://localhost:7687 # <-- docker use neo4j
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=mysecretneo4jpassword
    SEC_API_EMAIL="your_email@example.com"
    ```
3.  Start the services using Docker Compose:
    ```bash
    docker-compose up --build
    ```
    This will start FastAPI, PostgreSQL, and Neo4j.
### Frontend Setup
1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```
4.  Open your browser and visit `http://localhost:5173` (or the port shown in the terminal).