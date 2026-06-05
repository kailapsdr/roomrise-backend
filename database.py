from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# DEBUG: cetak apa yang terbaca
print("=" * 50)
print(f"DATABASE_URL terbaca: {DATABASE_URL}")
print(f"Semua env keys: {[k for k in os.environ.keys() if 'DATA' in k or 'JWT' in k or 'POSTGRES' in k or 'PG' in k]}")
print("=" * 50)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()