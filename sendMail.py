import msal
import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta
from babel.dates import format_date
import logging

load_dotenv()

CONFIG = {
    "tenantId": os.getenv("TENANT_ID"),
    "clientId": os.getenv("CLIENT_ID"),
    "clientSecret": os.getenv("CLIENT_SECRET"),
    "authority": f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
    "scopes": ["https://graph.microsoft.com/.default"],
}

def get_access_token():
    """
    Get access token using MSAL client credentials flow
    """
    try:
        app = msal.ConfidentialClientApplication(
            client_id=CONFIG["clientId"],
            client_credential=CONFIG["clientSecret"],
            authority=CONFIG["authority"]
        )

        result = app.acquire_token_for_client(scopes=CONFIG["scopes"])
        if result and "access_token" in result:
            logging.info("✅ Access token acquired successfully")
            return result["access_token"]
        else:
            logging.info(f"❌ Failed to acquire access token: {result.get('error_description', 'Unknown error')}")
            return None
        
    except Exception as e:
        logging.info(f"❌ Exception occurred while acquiring access token: {str(e)}")
        return None


def sendMail(routines):
    """
    Send all new routines in a single email using Microsoft Graph API
    """
    try:
        token = get_access_token()
        if not token:
            return False
        

        to_email = os.getenv("RECIEVER_MAIL")
        from_email = os.getenv("SENDER_MAIL")

        routine_count = len(routines)
        if routine_count > 1:
            subject = f"K2 Quality: {routine_count} nye rutiner publisert"
            header_text = f"{routine_count} nye rutiner opprettet siste uken"
        else:
            subject = "K2 Quality: 1 ny rutine publisert"
            header_text = "1 ny rutine opprettet siste uken"

        # Build HTML body with styling
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #DAAA00; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">K2 Quality</h1>
            </div>
            <div style="padding: 20px; background-color: #f9f9f9;">
                <h2 style="color: black; margin-top: 0;">{header_text}</h2>
        """

        for routine in routines:
            body += f"""
                <div style="background-color: white; border-left: 4px solid #DAAA00; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 10px 0; color: #333;">{routine['title']}</h3>
                    <p style="margin: 5px 0; color: #666;">Publisert: {routine['formatted_date']}</p>
                    <a href="{routine['search_url']}" style="display: inline-block; background-color: #DAAA00; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-top: 10px;">Se rutinen</a>
                </div>
            """

        body += """
            </div>
            <div style="padding: 15px; text-align: center; color: #666; font-size: 12px;">
                <p>Dette er en automatisk generert e-post fra K2 Quality rutineovervåking.</p>
            </div>
        </div>
        """

        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        endpoint = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(endpoint, headers=headers, json=email_data)
        logging.info(response)
        if response.status_code == 202:
            logging.info("✅ Email sent successfully")
            return True
        else:
            logging.info(f"❌ Failed to send email: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logging.info(f"❌ Exception occurred while sending email: {str(e)}")
        return False
    


def ChangeClientSecret():
    """
    Send mail to tell that the client secret is about to expire
    """

    expiration_date_str = os.getenv('CLIENT_SECRET_EXPIRATION_DATE')
    expiration_date_str = expiration_date_str.strip('"')  # Remove quotes
    expiration_date = datetime.strptime(expiration_date_str, '%m/%d/%Y')  # Parse from .env format
    
    formatted_exp_date = format_date(
        expiration_date,
        format='d. MMM yyyy',
        locale='nb'
    )

    try:
        token = get_access_token()
        if not token:
            return False

        from_email = os.getenv("SENDER_MAIL")
        to_email = from_email  # Send warning to sender (admin) instead of receiver
        subject = 'K2 Quality: Client secret utløper snart'
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #cc0000; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Advarsel</h1>
            </div>
            <div style="padding: 20px; background-color: #f9f9f9;">
                <div style="background-color: white; border-left: 4px solid #cc0000; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h2 style="color: #cc0000; margin-top: 0;">Client secret utløper snart</h2>
                    <p style="color: #333;">Den nåværende "client secret" for <strong>K2 Quality rutineovervåking</strong> utløper <strong>{formatted_exp_date}</strong>.</p>
                    <p style="color: #333;">Vennligst oppdater før utløpsdatoen for å sikre fortsatt drift.</p>
                </div>
                <h3 style="color: #333;">Steg for å oppdatere:</h3>
                <div style="margin-bottom: 10px;">
                    <a href="{os.getenv('CLIENT_SECRET_UPDATE_URL')}" style="display: inline-block; background-color: #DAAA00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">1. Opprett ny client secret</a>
                </div>
                <div>
                    <a href="{os.getenv('CHANGE_SECRET_URL')}" style="display: inline-block; background-color: #DAAA00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">2. Oppdater Function App</a>
                </div>
                <p style="color: #666; margin-top: 20px; font-size: 14px;">Husk å oppdatere både <code>CLIENT_SECRET</code> og <code>CLIENT_SECRET_EXPIRATION_DATE</code> i Function App.</p>
            </div>
            <div style="padding: 15px; text-align: center; color: #666; font-size: 12px;">
                <p>Dette er en automatisk generert e-post fra K2 Quality rutineovervåking.</p>
            </div>
        </div>
        """
        
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        endpoint = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(endpoint, headers=headers, json=email_data)
        
        if response.status_code == 202:
            logging.info("✅ Email sent successfully")
            return True
        else:
            logging.info(f"❌ Failed to send email: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logging.info(f"❌ Exception occurred while sending email: {str(e)}")
        return False