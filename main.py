from datetime import datetime
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from app.slots import compute_free_slots

# Scope to access Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_google_calendar():
    creds = None
    # Token file stores user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no valid credentials, request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=3000)

        # Save the credentials for future use
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

def get_free_timeslots(service, calendar_id='primary', date=datetime.now()):
    start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0).isoformat() + 'Z'
    end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59).isoformat() + 'Z'

    events_result = service.freebusy().query(
        body={
            "timeMin": start_of_day,
            "timeMax": end_of_day,
            "timeZone": "UTC",
            "items": [{"id": calendar_id}],
        }
    ).execute()

    busy_times = events_result['calendars'][calendar_id].get('busy', [])
    return compute_free_slots(busy_times, date)

def main():
    service = authenticate_google_calendar()
    date_to_check = datetime.now()  # You can specify another date
    free_slots = get_free_timeslots(service, date=date_to_check)

    if free_slots:
        print("Free 30-minute timeslots:")
        for slot in free_slots:
            print(slot)
    else:
        print("No free slots available.")

if __name__ == '__main__':
    main()

