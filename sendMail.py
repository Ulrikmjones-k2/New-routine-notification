import msal
import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta
from  babel.dates import format_date

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
            print("✅ Access token acquired successfully")
            return result["access_token"]
        else:
            print(f"❌ Failed to acquire access token: {result.get('error_description', 'Unknown error')}")
            return None
        
    except Exception as e:
        print(f"❌ Exception occurred while acquiring access token: {str(e)}")
        return None


def sendMail(routine_data):
    """
    Send routine data via email using Microsoft Graph API
    """
    try:
        token = get_access_token()
        if not token:
            return "access token not available"
        
        to_email = os.getenv("SUPPORT_MAIL")
        from_email = os.getenv("SUPPORT_MAIL")
        subject = f"Ny rutine: {routine_data['title']}"
        body = f"""
                    <h3>Ny rutine opprettet: {routine_data['title']}</h3>
                    <p>Rutinen ble publisert: {routine_data['formatted_date']}</p>
                    <p>Du kan se rutinen <a href="{routine_data['search_url']}">her</a>.</p>
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
        print(response)
        if response.status_code == 202:
            print("✅ Email sent successfully")
            return True
        else:
            print(f"❌ Failed to send email: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception occurred while sending email: {str(e)}")
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
            return "access token not available"
        
        to_email = os.getenv("SUPPORT_MAIL")
        from_email = os.getenv("SUPPORT_MAIL")
        subject = '"client secret" er i ferd med å utløpe'
        body = f"""
                    <h3>"Client secret" er i ferd med å utløpe for "Send email routines" programmet.</h3>
                    <p>Den nåværende "client secret" utløper {formatted_exp_date}.</p>
                    <p>Vennligst oppdater "client secret" <a href="{os.getenv('CLIENT_SECRET_UPDATE_URL')}">her</a>, og endre verdien på "CLIENT_SECRET" og "CLIENT_SECRET_EXPIRATION_DATE" i .env-filen i "RoutineNotifications Function App" <a href="https://portal.azure.com/#@k2kompetanse.no/resource/subscriptions/eaf7505d-e089-4798-9031-2e200df76549/resourceGroups/Routine_notification/providers/Microsoft.Web/sites/RoutineNotification/appServices">her</a> for å sikre fortsatt tilgang.</p>
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
            print("✅ Email sent successfully")
            return True
        else:
            print(f"❌ Failed to send email: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception occurred while sending email: {str(e)}")
        return False