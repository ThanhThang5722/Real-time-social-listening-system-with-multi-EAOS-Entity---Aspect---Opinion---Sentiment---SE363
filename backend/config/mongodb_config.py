"""MongoDB configuration settings"""
from typing import Optional


class MongoDBConfig:
    """MongoDB connection and database configuration"""

    # Connection settings
    HOST = "localhost"
    PORT = 27017
    USERNAME = "admin"
    PASSWORD = "admin123"
    AUTH_SOURCE = "admin"

    # Database and collection names
    DATABASE_NAME = "eaos_dashboard"
    COMMENTS_COLLECTION = "comments"
    ANALYTICS_COLLECTION = "analytics"
    TRAINING_DATA_COLLECTION = "training_data"

    # Connection string
    @classmethod
    def get_connection_string(cls) -> str:
        """Get MongoDB connection string"""
        return f"mongodb://{cls.USERNAME}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE_NAME}?authSource={cls.AUTH_SOURCE}"

    # Motor client settings
    MOTOR_CLIENT_CONFIG = {
        "maxPoolSize": 10,
        "minPoolSize": 1,
        "maxIdleTimeMS": 30000,
        "serverSelectionTimeoutMS": 5000,
    }

    # Document settings
    ENABLE_DUPLICATE_CHECK = True  # Check if comment already exists before insert
    BATCH_INSERT_SIZE = 100  # Number of documents to batch insert
