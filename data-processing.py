import re
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import pytz
import json

timezone = pytz.timezone('US/Eastern')

# Operating hours for the facility
OPERATING_HOURS = {
    'Monday': ('7am', '11pm'),
    'Tuesday': ('7am', '11pm'),
    'Wednesday': ('7am', '11pm'),
    'Thursday': ('7am', '11pm'),
    'Friday': ('7am', '8pm'),
    'Saturday': ('8am', '8pm'),
    'Sunday': ('8am', '8pm')
}

def parse_time(time_str, context_time_str=None):
    """
    Parse time strings with flexible formats (e.g., '7pm', '10:30am', '7')
    If a bare number is provided without am/pm, infer from context_time_str if available
    """
    # Normalize the time string
    time_str = time_str.lower().strip()
    
    # Check if time_str is just a number without am/pm
    if re.match(r'^\d+$', time_str) and context_time_str:
        # Infer am/pm from context_time_str
        if 'pm' in context_time_str.lower():
            time_str += 'pm'
        elif 'am' in context_time_str.lower():
            time_str += 'am'
    
    # Try different patterns
    patterns = [
        '%I%p',      # 7pm
        '%I:%M%p',   # 7:30pm
        '%H:%M',     # 14:30
    ]
    
    for pattern in patterns:
        try:
            return datetime.strptime(time_str, pattern)
        except ValueError:
            continue
    
    raise ValueError(f"Time format not recognized: {time_str}")

# def parse_schedule_data(events_list: List[str]) -> List[Dict]:
#     """
#     Parse schedule data from a list of event strings into structured format.
    
#     Args:
#         events_list: A list of strings containing the event information
        
#     Returns:
#         A list of dictionaries, each containing date, start time, end time, and location
#     """
#     parsed_events = []
    
#     for event in events_list:
#         # Skip empty entries
#         if not event.strip():
#             continue
            
#         # Improved pattern to better handle time formats
#         pattern = r'([A-Za-z]+, [A-Za-z]+ \d+, \d{4})(?:, (\d+(?::\d+)?(?:am|pm)?) - (\d+(?::\d+)?(?:am|pm)?))?(.+)'
#         match = re.match(pattern, event)
        
#         if match:
#             date_str, start_time, end_time, location = match.groups()
            
#             # Clean up the location and check if it contains misplaced time information
#             location = location.strip()
            
#             # Check if location starts with a time pattern that might have been missed
#             time_in_location = re.match(r',?\s*(\d+(?::\d+)?(?:am|pm)?) - (\d+(?::\d+)?(?:am|pm)?)(.*)', location)
#             if time_in_location and not start_time:
#                 # Extract the time from the location field
#                 start_time = time_in_location.group(1)
#                 end_time = time_in_location.group(2)
#                 location = time_in_location.group(3).strip()
            
#             # If no time is given, it means the entire date
#             if start_time is None:
#                 start_time = "12am"
#                 end_time = "11:59pm"
                
#             parsed_events.append({
#                 "date": date_str,
#                 "start_time": start_time,
#                 "end_time": end_time,
#                 "location": location
#             })
#         else:
#             print(f"Failed to parse event: {event}")
    
#     return parsed_events

def parse_schedule_data(events_list: List[str]) -> List[Dict]:
    """
    Parse schedule data from a list of event strings into structured format.
    Handles both single-day and multi-day formats.
    """
    parsed_events = []
    for event in events_list:
        if not event.strip():
            continue

        # Handle multi-day range
        range_pattern = (
            r'([A-Za-z]+, [A-Za-z]+ \d+), (\d+(?::\d+)?(?:am|pm)?) - '
            r'([A-Za-z]+, [A-Za-z]+ \d+, \d{4}), (\d+(?::\d+)?(?:am|pm)?)(.+)'
        )
        match_range = re.match(range_pattern, event)
        if match_range:
            start_day_str, start_time, end_day_str, end_time, location = match_range.groups()
            start_date = datetime.strptime(f"{start_day_str}, {end_day_str[-4:]}", '%A, %B %d, %Y')
            end_date = datetime.strptime(end_day_str, '%A, %B %d, %Y')

            location = location.strip()

            current_date = start_date
            while current_date <= end_date:
                # First day uses start_time, last day uses end_time, others use full day
                if current_date == start_date:
                    st, et = start_time, "11:59pm"
                elif current_date == end_date:
                    st, et = "12am", end_time
                else:
                    st, et = "12am", "11:59pm"
                parsed_events.append({
                    "date": current_date.strftime('%A, %B %d, %Y'),
                    "start_time": st,
                    "end_time": et,
                    "location": location
                })
                current_date += timedelta(days=1)
            continue

        # Handle single-day format
        single_day_pattern = (
            r'([A-Za-z]+, [A-Za-z]+ \d+, \d{4})(?:, (\d+(?::\d+)?(?:am|pm)?) - (\d+(?::\d+)?(?:am|pm)?))?(.+)'
        )
        match_single = re.match(single_day_pattern, event)
        if match_single:
            date_str, start_time, end_time, location = match_single.groups()
            location = location.strip()

            # Try to extract time from location if missing
            time_match = re.match(r',?\s*(\d+(?::\d+)?(?:am|pm)?) - (\d+(?::\d+)?(?:am|pm)?)(.*)', location)
            if time_match and not start_time:
                start_time, end_time, location = time_match.groups()
                location = location.strip()

            if not start_time:
                start_time = "12am"
            if not end_time:
                end_time = "11:59pm"

            parsed_events.append({
                "date": date_str.strip(),
                "start_time": start_time,
                "end_time": end_time,
                "location": location
            })
        else:
            print(f"Failed to parse event: {event}")

    return parsed_events

def fetch_events(date, events_data, court_number=3):
    """
    Fetch events for the specified date and court number.

    Args:
        date: The date to check for events
        events_data: List of parsed event dictionaries
        court_number: Court number to filter by (default: 3)

    Returns:
        List of (start_time, end_time) tuples for that date and court
    """
    # Format date to string for comparison
    date_str = date.strftime('%A, %B %d, %Y')
    print(f"Looking for events on {date_str} for Court #{court_number}")
    
    matching_events = []
    for event in events_data:
        # Check if date matches
        if event["date"] == date_str:
            print(f"Found event on {date_str}: {event}")
            # Check if this event has any court mentioned for this date
            court_pattern = f"Court #{court_number}"
            if court_pattern in event["location"]:
                print(f"  - Court #{court_number} found in location")
                matching_events.append((event["start_time"], event["end_time"]))
    
    return matching_events

def normalize_date_format(date_str):
    """
    Ensure date strings have consistent format
    """
    try:
        # Parse the date string
        date_obj = datetime.strptime(date_str, '%A, %B %d, %Y')
        # Return a standardized format
        return date_obj.strftime('%A, %B %d, %Y')
    except ValueError:
        print(f"Error normalizing date: {date_str}")
        return date_str

def get_available_times(date, events_data, court_number=3):
    """
    Get available time slots for the specified court on the given date.
    Merges overlapping or adjacent time slots.

    Args:
        date: The date to check for availability
        events_data: List of parsed event dictionaries
        court_number: Court number to check availability for (default: 3)

    Returns:
        List of (start_datetime, end_datetime) tuples representing available slots
    """
    # Ensure consistent date format for events_data
    for event in events_data:
        event["date"] = normalize_date_format(event["date"])
    
    day_name = date.strftime('%A')
    open_time_str, close_time_str = OPERATING_HOURS[day_name]
    open_time = datetime.combine(date, parse_time(open_time_str).time())
    close_time = datetime.combine(date, parse_time(close_time_str).time())

    events = fetch_events(date, events_data, court_number)
    
    if not events:
        # If no events found, the entire time from open to close is available
        return [(open_time, close_time)]
    
    # Parse the event times
    parsed_events = []
    for start, end in events:
        try:
            # Pass the end time as context to infer am/pm for start time if needed
            start_dt = datetime.combine(date, parse_time(start, end).time())
            end_dt = datetime.combine(date, parse_time(end).time())
            parsed_events.append((start_dt, end_dt))
        except ValueError as e:
            print(f"Error parsing event time: {start} - {end}: {e}")
    
    # Sort events by start time
    parsed_events.sort()

    # Merging available time slots by checking gaps between events
    available_times = []
    current_time = open_time

    for start, end in parsed_events:
        # If there's time between the current_time and the event, add it to available_times
        if current_time + timedelta(minutes=1) < start:
            available_times.append((current_time, start))
        # Set current_time to the end of the last event
        current_time = max(current_time, end)

    # Check if there is available time after the last event until closing time
    if current_time < close_time:
        available_times.append((current_time, close_time))

    return available_times


def format_datetime(dt):
    """Format datetime for readability"""
    return dt.strftime('%A, %B %d, %Y %I:%M %p')

def format_time(dt):
    return dt.strftime('%-I:%M%p').lower().replace(':00', '') if dt.minute != 0 else dt.strftime('%-I%p').lower()

def fetch_availability_data(unique_dates, parsed_events):
    """
    Fetch availability data for the next 14 days and format it as a JSON structure.
    Returns a dictionary with dates as keys and available time slots as values.
    """
    try:
        availability_data = {}
        for date in unique_dates:   
            date_str = date.strftime('%Y-%m-%d')  # Use ISO format for keys     
            available_slots = []
            available_times = get_available_times(date.date(), parsed_events, court_number=3)
            
            for start, end in available_times:
                slot = f"{format_time(start)} - {format_time(end)}"
                available_slots.append(slot)
            
            availability_data[date_str] = available_slots
        
        result = {
            "availability": availability_data,
            "last_updated": datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return result
    except Exception as e:
        print(f"Error generating availability data: {e}")
        return {"availability": {}, "last_updated": datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")}

def save_availability_to_file(unique_dates, parsed_events, filename="data/availability.json"):
    """
    Save the availability data to a JSON file.
    """
    try:
        data = fetch_availability_data(unique_dates, parsed_events)
        with open(filename, 'w') as f:
            json.dump(data, f)
        print(f"Availability data saved to {filename}")
        return data
    except Exception as e:
        print(f"Error saving availability data: {e}")
        return None

# load a json file
data = []
for i in range(4):
    with open(f'checkpoints/batch_{i}_checkpoint.json') as f:
        d_ = json.load(f)
        data.extend(d_)
print(f"Total events: {len(data)}")
descs = [d['description'] for d in data]
try:
    parsed_events = parse_schedule_data(descs)
    parsed_dates = [datetime.strptime(event['date'], '%A, %B %d, %Y') for event in parsed_events]
    unique_dates = sorted(set(parsed_dates))
    print(f"Unique dates: {unique_dates}")

    for event in parsed_events:
        if 'm' not in event['start_time'] and 'pm' in event['end_time']:
            event['start_time'] += 'pm'
        elif 'm' not in event['start_time'] and 'am' in event['end_time']:
            event['start_time'] += 'am'
        if not event['end_time']:
            event['end_time'] = '11:59pm'
        if not event['start_time']:
            event['start_time'] = '12:00am'
    print(f"Parsed {len(parsed_events)} events")
    save_availability_to_file(unique_dates, parsed_events)
except NameError:
    print("Variable 'descs' is not defined. Please define it before running this code.")
