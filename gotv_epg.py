import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import gzip
import pytz  # Import pytz for timezone handling

# URLs for data
epg_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/epgjson'
genre_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/liveAssetsBasedOnkey'

# Set Kathmandu timezone
kathmandu_tz = pytz.timezone('Asia/Kathmandu')
now = datetime.now(kathmandu_tz)

# Set the start time to today's midnight (00:00 AM)
start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

# Set the stop time to tomorrow's midnight (00:00 AM)
end_of_day = start_of_day + timedelta(days=1)

# Update payload timestamps
payload = {
    'startTimeTimestamp': int(start_of_day.timestamp() * 1000),  # Start at 12 AM today
    'stopTimeTimestamp': int(end_of_day.timestamp() * 1000),  # End at 12 AM tomorrow
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
        programme_date = program.get("programmeDate", "").replace("-", "")
        start_time = program.get("startTime", "000000")
        stop_time = program.get("stopTime", "235959")
        program_id = str(program.get("id", "TBA"))

        # Convert start and stop times to datetime objects
        program_start = kathmandu_tz.localize(datetime.strptime(programme_date + start_time, "%Y%m%d%H%M%S"))
        program_stop = kathmandu_tz.localize(datetime.strptime(programme_date + stop_time, "%Y%m%d%H%M%S"))

        # Ensure the program falls within our 12 AM to 12 AM window
        if not (start_of_day <= program_start < end_of_day):
            continue

        # Format timestamps in EPG format
        start = program_start.strftime('%Y%m%d%H%M%S') + " +0545"
        stop = program_stop.strftime('%Y%m%d%H%M%S') + " +0545"

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

print(f"EPG Data fetched for {start_of_day.strftime('%Y-%m-%d')} (12:00 AM to 11:59 PM) Kathmandu Time")
print("XML and compressed XML files saved successfully as gotv.xml and gotv.xml.gz.")
