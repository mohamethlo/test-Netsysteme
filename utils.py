import os
from dotenv import load_dotenv
load_dotenv()
import math
from werkzeug.utils import secure_filename
from datetime import datetime, time

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two coordinates using the Haversine formula
    Returns distance in meters
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    
    return c * r

def format_duration(minutes):
    """Convert minutes to hours and minutes format"""
    if not minutes:
        return "0h 0min"
    
    hours = minutes // 60
    mins = minutes % 60
    
    if hours > 0:
        return f"{hours}h {mins}min"
    else:
        return f"{mins}min"

def get_status_badge_class(status):
    """Get Bootstrap badge class for status"""
    status_classes = {
        'planifiee': 'bg-primary',
        'en_cours': 'bg-warning',
        'terminee': 'bg-success',
        'annulee': 'bg-danger',
        'en_attente': 'bg-warning',
        'approuve': 'bg-success',
        'refuse': 'bg-danger',
        'present': 'bg-success',
        'absent': 'bg-danger',
        'late': 'bg-warning'
    }
    return status_classes.get(status, 'bg-secondary')

def get_priority_badge_class(priority):
    """Get Bootstrap badge class for priority"""
    priority_classes = {
        'basse': 'bg-secondary',
        'normale': 'bg-primary',
        'haute': 'bg-warning',
        'urgente': 'bg-danger'
    }
    return priority_classes.get(priority, 'bg-secondary')

import requests
def send_orange_sms(to, message, sender=None):
    client_id = os.getenv("ORANGE_CLIENT_ID")
    client_secret = os.getenv("ORANGE_CLIENT_SECRET")
    # Ajoute le préfixe tel: si absent
    if sender and not sender.startswith("tel:"):
        sender_tel = f"tel:{sender}"
    else:
        sender_tel = sender
    token_url = "https://api.orange.com/oauth/v3/token"
    sms_url = f"https://api.orange.com/smsmessaging/v1/outbound/{sender_tel}/requests"

    auth = (client_id, client_secret)
    data = {'grant_type': 'client_credentials'}
    token_resp = requests.post(token_url, auth=auth, data=data)
    token = token_resp.json().get('access_token')

    if not token:
        print("Erreur d'obtention du token Orange:", token_resp.text, flush=True)
        return False

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "outboundSMSMessageRequest": {
            "address": f"tel:{to}",
            "senderAddress": sender_tel,  # doit être identique à l'URL
            "outboundSMSTextMessage": {
                "message": message
            }
        }
    }
    resp = requests.post(sms_url, headers=headers, json=payload)
    print(f"Orange SMS API status: {resp.status_code}, réponse: {resp.text}", flush=True)
    return resp.status_code == 201