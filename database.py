import os
import platform
import logging
from sqlalchemy import create_engine, text, event, inspect
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus
from pgvector.sqlalchemy import Vector
from pgvector.psycopg2 import register_vector

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_engine():
    """
    Initializes a connection pool for a Cloud SQL instance of Postgres.
    Uses the Cloud SQL Auth Proxy via a Unix socket.
    """
    try:
        db_user = os.environ["DB_USER"]
        db_pass = quote_plus(os.environ["DB_PASS"])
        db_name = os.environ["DB_NAME"]

        db_url = ""
        # Check the operating system
        if platform.system() == "Windows":
            # Windows-specific connection using TCP
            db_host = os.environ.get("DB_HOST", "127.0.0.1")
            db_port = os.environ.get("DB_PORT", 5432)
            db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            logger.info(f"Attempting to connect to database on Windows: {db_host}:{db_port}")
        else:
            # Unix-based (macOS, Linux) connection using a Unix socket
            instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]
            unix_socket_path = f"/tmp/cloudsql/{instance_connection_name}"
            db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}?host={unix_socket_path}"
            logger.info(f"Attempting to connect to database via Unix socket: {unix_socket_path}")

        engine = create_engine(db_url)
        
        # Test the connection
        with engine.connect() as connection:
            logger.info("Database connection successful.")
        return engine

    except KeyError as e:
        logger.error(f"Missing required environment variable: {e}. Please check your .env file.")
        return None
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}. Check if the Cloud SQL Auth Proxy is running and the DB credentials are correct.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating the database engine: {e}")
        return None

engine = get_engine()

# Register the vector type with psycopg2 if the engine was created successfully
if engine:
    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        register_vector(dbapi_connection)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    logger.error("Database engine is not available. SessionLocal could not be configured.")
    SessionLocal = None

def init_db():
    """Creates the vector extension and the chat_history table if they don't exist."""
    if not engine:
        logger.error("Cannot initialize database: engine is not available.")
        return
        
    try:
        with engine.connect() as connection:
            with connection.begin():
                logger.info("Enabling 'vector' extension...")
                connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
                
                logger.info("Checking/creating 'chat_history' table...")
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.chat_history (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        topic TEXT NOT NULL,
                        final_output TEXT,
                        embedding VECTOR(768),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """))
        logger.info("Database schema check/creation complete.")

        # Inspect the database to list tables and their schemas
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Tables present in the database: {tables}")

        # Display the schema for the target table if it exists
        table_name = "chat_history"
        if table_name in tables:
            logger.info(f"--- Schema for '{table_name}' ---")
            columns = inspector.get_columns(table_name)
            for column in columns:
                logger.info(f"  Column: {column['name']}, Type: {column['type']}")
            logger.info("------------------------------------")

    except SQLAlchemyError as e:
        logger.error(f"An error occurred during database initialization: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during database initialization: {e}")

# --- Main execution block ---
if __name__ == "__main__":
    logger.info("Running database initialization directly...")
    if engine:
        init_db()
    else:
        logger.error("Database initialization skipped because the engine could not be created.")
