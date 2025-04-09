import os

db_host = os.getenv("db_endpoint")
db_name = os.getenv("db_name")
db_user = os.getenv("username_db")
db_password = os.getenv("password_db")


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{db_user}:{db_password}"
        f"@quotezen.cizaqa88qbef.us-east-1.rds.amazonaws.com:5432/{db_name}"
    )
    COGNITO_REGION = os.getenv("AWS_REGION", "us-east-1")
    USER_POOL_ID = os.getenv("USER_POOL_ID", "")
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    COGNITO_KEYS_URL = os.getenv("COGNITO_KEYS_URL", "")

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_SES_REGION = os.getenv("AWS_REGION", "us-east-1")
    SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "")
    HASH_KEY = os.getenv("HASH_KEY", "")
    DOMAIN_URL = os.getenv("DOMAIN_URL", "")


