import os

db_host = os.getenv("db_endpoint")
db_name = os.getenv("db_name")
db_user = os.getenv("username_db")
db_password = os.getenv("password_db")


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://postgres:Protools9366!@quotezen.cizaqa88qbef.us-east-1.rds.amazonaws.com:5432/quotezen"
    )
    COGNITO_REGION = "us-east-1"
    USER_POOL_ID = "us-east-1_RfcsToPmD"
    CLIENT_ID = "31os5virvbq7oipm6s65c8ongu"
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
    COGNITO_KEYS_URL = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_RfcsToPmD/.well-known/jwks.json"

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_SES_REGION = "us-east-1"
    SES_SENDER_EMAIL = "adrip@quotezen.io"
    HASH_KEY = "BXRCXmnOsoAtgkP3YrptLfK6OhtQGdCw9owM6HJXYcQ="
    DOMAIN_URL = "http://54.147.174.118:5000"


