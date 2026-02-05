import os
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus
from pgvector.sqlalchemy import Vector
from pgvector.psycopg2 import register_vector

load_dotenv()

def get_engine():
    """
    Initializes a connection pool for a Cloud SQL instance of Postgres.
    Uses the Cloud SQL Auth Proxy via a Unix socket.
    """
    db_user = os.environ["DB_USER"]
    # URL-encode the password to handle special characters
    db_pass = quote_plus(os.environ["DB_PASS"])
    db_name = os.environ["DB_NAME"]
    instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]
    
    # The socket path is formatted as /tmp/cloudsql/INSTANCE_CONNECTION_NAME
    unix_socket_path = f"/tmp/cloudsql/{instance_connection_name}"

    # Create a SQLAlchemy engine
    engine = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}?host={unix_socket_path}"
    )
    
    return engine

engine = get_engine()

# Register the vector type with psycopg2
@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    register_vector(dbapi_connection)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Creates the vector extension and the chat_history table if they don't exist."""
    try:
        with engine.connect() as connection:
            with connection.begin():
                # Enable the pgvector extension
                connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
                
                # Create the chat_history table with an embedding column
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.chat_history_external (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        topic TEXT NOT NULL,
                        final_output TEXT,
                        embedding VECTOR(768),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """))
        print("Database for external model initialized: 'chat_history' table checked/created.")
    except Exception as e:
        print(f"An error occurred during database initialization: {e}")
