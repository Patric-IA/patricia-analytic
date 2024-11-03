import os
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")
MONGO_URI = os.getenv("MONGO_URI")