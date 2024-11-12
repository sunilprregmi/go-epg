import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import gzip

# URLs for data
epg_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/epgjson'
genre_url = 'https://soapbox.dishhome.com.np/dhdbcacheV2/liveAssetsBasedOnkey'

# Set up payload
now = datetime.now()
payload = {
    'startTimeTimestamp': int(now.timestamp() * 1000),
    'stopTimeTimestamp': int((now + timedelta(days=1)).timestamp() * 1000),
    'account_id': 1, 'offset': 0, 'limit': 1000,
    'programmeDate': now.strftime('%Y-%m-%d'),
    'timezone': 'plus0545', 'date': now.strftime('%Y%m%d')
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
        programme_date = program.get("programmeDate", now.strftime('%Y%m%d'))
        start_time = program.get("startTime", "000000")
        stop_time = program.get("stopTime", "235959")
        program_id = str(program.get("id", "TBA"))

        start = programme_date.replace("-", "") + start_time.replace(":", "") + " +0000"
        stop = programme_date.replace("-", "") + stop_time.replace(":", "") + " +0000"

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

print("XML and compressed XML files saved successfully as gotv.xml and gotv.xml.gz.")
