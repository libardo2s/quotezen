from flask import current_app
import boto3
from app.config import Config

def send_email(recipient, subject, body_text, body_html=None):
    config = current_app.config

    ses = boto3.client(
        'ses',
        region_name=config['AWS_SES_REGION'],
        aws_access_key_id=config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=config['AWS_SECRET_ACCESS_KEY']
    )

    body = {
        'Text': {'Data': body_text}
    }

    if body_html:
        body['Html'] = {'Data': body_html}

    response = ses.send_email(
        Source=config['SES_SENDER_EMAIL'],
        Destination={'ToAddresses': [recipient]},
        Message={
            'Subject': {'Data': subject},
            'Body': body
        }
    )
    print(response)

    return response



import boto3

ses = boto3.client("ses", region_name="us-east-1")
ses.send_email(
    Source="adrip@quotezen.io",
    Destination={"ToAddresses": ["kandreyrosales@gmail.com"]},
    Message={
        "Subject": {"Data": "Hello"},
        "Body": {"Text": {"Data": "Welcome to QuoteZen!"}}
    }
)