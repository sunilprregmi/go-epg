import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import gzip
import pytz  # Import timezone library

# URLs for data
epg_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/epgjson'
genre_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/liveAssetsBasedOnkey'

# Set Kathmandu timezone
kathmandu_tz = pytz.timezone('Asia/Kathmandu')
now = datetime.now(kathmandu_tz)  # Current time in Kathmandu

# Get today's date and 12:00 AM timestamp for whole day EPG
start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=kathmandu_tz)  # 12:00 AM
end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)  # 11:59:59 PM

# Update payload timestamps (in milliseconds)
payload = {
    'startTimeTimestamp': int(start_of_day.timestamp() * 1000),  # 12:00 AM
    'stopTimeTimestamp': int(end_of_day.timestamp() * 1000),  # 11:59:59 PM
    'account_id': 1, 'offset': 0, 'limit': 1000,
    'programmeDate': now.strftime('%Y-%m-%d'),  # YYYY-MM-DD format
    'timezone': 'plus0545', 'date': now.strftime('%Y%m%d')  # YYYYMMDD format
}

headers = {"Authorization": "Bearer null", "User-Agent": "okhttp/4.10.0"}

# Fetch data
epg_data = requests.post(epg_url, data=payload, headers=headers).json().get("data", [])
genre_data = requests.post(genre_url, data=payload, headers=headers).json()
genre_mapping = {str(d["id"]): d["name"] for d in genre_data["data"][0]["genreDetails"].values()}

# Sanitization function
def sanitize_text(text):
    if text:
        sanitized = re.sub(r'[^a-zA-Z0-9\s\.,-]', '', text)
        return re.sub(r'\s+', ' ', sanitized).strip()
    return "TBA"

# Create XML structure
tv = ET.Element("tv", {"generator-info-name": "@guruusr", "generator-info-url": "https:/t.me/guruusr"})
channels, programmes = [], []

for channel_data in epg_data:
    channel_id = str(channel_data["id"])
    channel_title = sanitize_text(channel_data.get("title", "TBA"))
    thumbnails = channel_data.get("thumbnails", [])
    icon_url = f"https://soapbox.dishhome.com.np/genesis/{thumbnails[0]['thumbnailUrl']}" if thumbnails else ""

    channel = ET.Element("channel", {"id": channel_id})
    ET.SubElement(channel, "display-name").text = channel_title
    if icon_url:
        ET.SubElement(channel, "icon", {"src": icon_url})
    channels.append(channel)

    for program in channel_data.get("epg", []):
        program_id = str(program.get("id", "TBA"))

        # Fix: Use actual timestamps from API
        start_timestamp = int(program.get("startTimeTimestamp", 0)) / 1000  # Convert from milliseconds to seconds
        stop_timestamp = int(program.get("stopTimeTimestamp", 0)) / 1000  # Convert from milliseconds to seconds

        # Convert timestamps to Nepal Time
        start_time = datetime.fromtimestamp(start_timestamp, kathmandu_tz)
        stop_time = datetime.fromtimestamp(stop_timestamp, kathmandu_tz)

        # Ensure the program belongs to today's EPG (including those that end at 12:00 AM)
        if not (start_of_day <= stop_time <= end_of_day):
            continue  

        # Format timestamps for XMLTV (Correct +0545 time offset)
        start = start_time.strftime("%Y%m%d%H%M%S") + " +0545"
        stop = stop_time.strftime("%Y%m%d%H%M%S") + " +0545"

        title = sanitize_text(program.get("displayName", "TBA"))
        description = sanitize_text(program.get("description", "TBA"))
        sub_title = sanitize_text(program.get("title", "TBA"))
        live_thumbnail = channel_data.get("liveThumbnailPath", "") + "/thumbnail.png"

        programme = ET.Element("programme", {
            "start": start, "stop": stop, "channel": channel_id, "catchup-id": program_id
        })
        ET.SubElement(programme, "title").text = title
        ET.SubElement(programme, "desc").text = description
        ET.SubElement(programme, "sub-title").text = sub_title
        ET.SubElement(programme, "icon", {"src": live_thumbnail})

        unique_categories = {genre_mapping.get(str(g["genreId"]), "Uncategorized") for g in channel_data.get("genres", [])}
        for category in unique_categories:
            if category != "Uncategorized" or len(unique_categories) == 1:
                ET.SubElement(programme, "category").text = category

        programmes.append(programme)

for element in channels + programmes:
    tv.append(element)

# Format XML output
pretty_xml = minidom.parseString(ET.tostring(tv, encoding="utf-8", method="xml")).toprettyxml(indent="    ")

# Save the XML file
with open("gotv.xml", "w", encoding="utf-8") as xml_file:
    xml_file.write(pretty_xml)

# Save the compressed XML file
with gzip.open("gotv.xml.gz", "wt", encoding="utf-8") as gz_file:
    gz_file.write(pretty_xml)

print(f"EPG Data fetched for {now.strftime('%Y-%m-%d %H:%M:%S')} (Kathmandu Time)")
print("XML and compressed XML files saved successfully as gotv.xml and gotv.xml.gz.")
