from pymongo import MongoClient
import os
from dotenv import load_dotenv


def test_mongodb_connection():
    # Load environment variables
    load_dotenv()

    # Get MongoDB URI from environment variable
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("Error: MONGODB_URI environment variable is not set")
        return False

    try:
        # Create MongoDB client
        print("Attempting to connect to MongoDB...")
        client = MongoClient(mongodb_uri)

        # Test the connection
        client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas!")

        # Test database access
        db = client["beyond_the_brush"]
        print("✅ Successfully accessed database 'beyond_the_brush'")

        # Test collections
        students = db["students"]
        access_codes = db["access_codes"]
        print("✅ Successfully accessed collections 'students' and 'access_codes'")

        # Test write operation
        test_doc = {"test": "connection"}
        result = students.insert_one(test_doc)
        print("✅ Successfully performed write operation")

        # Clean up test document
        students.delete_one({"_id": result.inserted_id})
        print("✅ Successfully performed delete operation")

        return True

    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {str(e)}")
        return False


if __name__ == "__main__":
    test_mongodb_connection()