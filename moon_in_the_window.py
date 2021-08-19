#%%
import ephem
import numpy as np
import matplotlib.pyplot as plt
from statistics import mean
import time
from math import sin, cos, sqrt, atan2, radians, pi
from apiclient import discovery
from apiclient.discovery import build
import sys
import os
from datetime import datetime, timedelta
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import progressbar
import matplotlib.pyplot as plt
from matplotlib.projections import PolarAxes
import re

from secrets import CAL_ID, CLIENT_SECRET_FILENAME, ADDRESS, LAT, LON
# You need to supply a secrets.py file in your project directory which assigns these two variables with the correct strings from google's API: 
# CAL_ID = [numbers_and_letters]@group.calendar.google.com'
# CLIENT_SECRET_FILENAME = 'client_secret_[numbers]-[numbers_and_letters].apps.googleusercontent.com.json')
# ADDRESS = [the_street_addres]
# LAT = '12.312312'
# LON = '34.534534'

print('Libraries loaded.')
#%%
root_dir = os.path.dirname(os.path.abspath(__file__))+'/'

obs = ephem.Observer()
obs.lat = LAT
obs.lon = LON
obs.elevation = 100
obs.date = '2020-01-10 20:45:00'
#obs.date = '2020-09-03 21:24:00'
sweet_spot = ephem.Moon(obs).copy()
print('sweet_spot:')
print('sweet_spot.alt: ',sweet_spot.alt)
print('sweet_spot.az: ',sweet_spot.az)
#%%
y,x = [],[]
durations = []
in_sweet_spot = False

moon_phases = ['Crescent','Quarter','Gibbous','Full']

dt = datetime.utcnow() - timedelta(days=2)
sweet_spot_tolerance = 15

def distance(lat1,lon1,lat2,lon2):
    # approximate radius of earth in km
    R = 6373.0
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

min_off = 9**9
last_m_degrees_off_w = 9**9

while dt < datetime.utcnow() + timedelta(days=3*365) or in_sweet_spot:

    obs.date = dt
    sun = ephem.Sun(obs)
    moon = ephem.Moon(obs)
    mars = ephem.Mars(obs)
    phase = 0
    
    m_hrs_off_w = ephem.separation((sweet_spot.az, sweet_spot.alt), (moon.az, moon.alt))
    m_degrees_off_w = float(repr(m_hrs_off_w))/pi*180
    s_hrs_off_m = ephem.separation((sun.az, sun.alt), (moon.az, moon.alt))
    s_degrees_off_m = float(repr(s_hrs_off_m))/pi*180
    #print(sun.alt < 0 , moon.az > 90/360 , moon.az < 135/360 , moon.alt > 30, moon.alt < 80)

    if m_degrees_off_w < sweet_spot_tolerance and (s_degrees_off_m > 90 or float(repr(sun.alt))/pi*180 < 0):  
        if m_degrees_off_w < min_off:
            min_off = m_degrees_off_w
            m_az, m_alt, s_az, s_alt = moon.az,moon.alt,sun.az,sun.alt
        if not in_sweet_spot:
            event = {
                'start':dt
            }
        in_sweet_spot = True
        
    else:
        if in_sweet_spot:
            # Here is where the gathered up data is pushed to list(durations) from where it's turned into stuff.
            event['end'] = dt
            event['dur'] = (event['end'] - event['start']).total_seconds()
            #find moon phase
            if ephem.Moon(obs).phase > phase:
                phase_dir = 'Waxing '
            elif ephem.Moon(obs).phase < phase:
                phase_dir = 'Waning '
            else:
                phase_dir = ''
            phase = ephem.Moon(obs).phase
            mid_time = event['start'] + (event['end'] - event['start'])/2
            obs.date = mid_time
            event['phase'] = int(round(ephem.Moon(obs).phase,0))
            event['phase_dir'] = str(phase_dir)
            event['min_off'] = str(min_off)
            event['name'] = moon_phases[int(round(event['phase']/100*3))]
            event['az'], event['alt'] = m_az, m_alt
            event['sun_az'], event['sun_alt'] = s_az,s_alt
            durations.append(event)
            min_off = 99999
        in_sweet_spot = False
    
    last_m_degrees_off_w = m_degrees_off_w
    dt += timedelta(minutes=1+(m_degrees_off_w/10) ** 1)
print(len(durations),'occations found when the moon is in the window and it is dark (enough). Preparing to add them to Google Calendar...')

#%%
#fig, ax = plt.subplots(figsize=(10,5),polar=True)
moon_az = [i['az'] for i in durations]
moon_alt = [i['alt'] for i in durations]
sun_az = [i['sun_az'] for i in durations],
sun_alt = [i['sun_alt'] for i in durations],
window_duration = [i['dur'] for i in durations],
fc = np.arange(0,np.pi*2,.01) #full circle
sweet_spot_az = [sweet_spot.az + sin(i)*(np.pi*sweet_spot_tolerance/180) for i in fc]
sweet_spot_alt = [sweet_spot.alt + cos(i)*(np.pi*sweet_spot_tolerance/180) for i in fc]
#plt.plot(sweet_spot_az,sweet_spot_alt)
#plt.scatter(sweet_spot.az,sweet_spot.alt)
horizon = np.arange(0,np.pi*2,.01)
fig = plt.figure(figsize=(10,10))
ax = plt.subplot(polar=True)
ax.set_theta_offset(np.pi/2)
ax.set_ylim((1,-1))
ax = plt.plot(horizon,[0 for i in horizon],c='#000')
ax = plt.scatter(moon_az,moon_alt,label='Moon',c=window_duration,s=2)
ax = plt.scatter(sun_az,sun_alt,label='Sun',c='y')
ax = plt.plot(sweet_spot_az,sweet_spot_alt,label='Sweet Spot')

fig.legend()
plt.show()


# %%

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

creds = None
# The file token.pickle stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
                root_dir + CLIENT_SECRET_FILENAME, SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('calendar', 'v3', credentials=creds)

# Call the Calendar API
now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
events_result = service.events().list(calendarId=CAL_ID, timeMin=now, maxResults=1000, singleEvents=True,orderBy='startTime').execute()
events = events_result.get('items', [])
if not events:
    print('\nNo upcoming events found.')
else:
    print('\nDeleting all upcoming existing events in calendar...')
    bar = progressbar.ProgressBar(max_value=len(events))
    tick = 0
    for event in events:
        time.sleep(.1)
        tick += 1
        bar.update(tick)

        start = event['start'].get('dateTime', event['start'].get('date'))
        
        start = re.sub('(?<=\+[0-9][0-9])\:', '', start)
        start = datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
        start = time.mktime(start.timetuple())
        #print(start)
        if start > time.time():
            service.events().delete(calendarId=CAL_ID, eventId=event['id']).execute()
        else:
            print('not delete')
    
    print('\nAll previous events deleted.\nAdding newly generated events...')

bar = progressbar.ProgressBar(max_value=len(durations))
tick = 0
for i in durations:
    time.sleep(.1)
    tick += 1
    bar.update(tick)
    event = {
        'summary': i['phase_dir'] + i['name'] + ' Moon in the Roof Light',
        'location': ADDRESS,
        'description': 'Fullmoon-ness: ' + str(i['phase']) + '%. \nClosest proximity to original "sweet spot": ' + str(round(float(i['min_off']),1)) + '°.',
        'start': {
            'dateTime': i['start'].isoformat(),
            'timeZone': 'UTC'},
        'end': {
            'dateTime': i['end'].isoformat(),
            'timeZone': 'UTC'}
    }

    service.events().insert(calendarId=CAL_ID, body=event).execute()

print('%s events added between now and %s. Great success!' % (len(durations),i['end'].strftime('%b %Y')))



# %%
