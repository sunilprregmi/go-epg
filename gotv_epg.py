#!/usr/bin/env python3
import json
import gzip
import requests
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import os

class DishHomeGoEPG:
    def __init__(self):
        self.base_url = "https://storefront.dishhomego.com.np/dhome/web-app/webepg"
        self.image_base = "https://assets.dishhomego.com.np/"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0'}
    
    def get_date_range(self):
        today = datetime.now()
        start = (today - timedelta(days=2)).replace(hour=18, minute=30, second=0)
        end = (today + timedelta(days=3)).replace(hour=18, minute=29, second=59)
        return start, end
    
    def fetch_data(self):
        start_date, end_date = self.get_date_range()
        start_enc = start_date.strftime('%Y-%m-%d %H:%M:%S').replace(' ', '%20').replace(':', '%3A')
        end_enc = end_date.strftime('%Y-%m-%d %H:%M:%S').replace(' ', '%20').replace(':', '%3A')
        
        channels = []
        page = 1
        
        while page <= 20:
            url = f"{self.base_url}?start={start_enc}&stop={end_enc}&page={page}"
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                data = response.json()
                
                if not data.get('list'):
                    break
                
                channels.extend(data['list'])
                page += 1
            except:
                break
        
        return channels
    
    def create_fallback_programs(self, channel):
        """Create fallback programs using channel's actual information."""
        programs = []
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        # Use channel's actual data
        channel_title = channel.get('title', '')
        channel_desc = channel.get('fullSynopsis', '')
        channel_cats = channel.get('catogory', [])
        channel_images = channel.get('images', [])
        
        for day in range(5):
            for hour in range(24):
                start_time = (now + timedelta(days=day, hours=hour))
                end_time = start_time + timedelta(hours=1)
                
                program = {
                    'title': channel_title,
                    'start': start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'stop': end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'fullSynopsis': channel_desc,
                    'shortSynopsis': channel_desc[:100] + '...' if len(channel_desc) > 100 else channel_desc,
                    'catogory': channel_cats,
                    'images': channel_images[:1] if channel_images else []
                }
                programs.append(program)
        
        return programs
    
    def format_time(self, time_str):
        if not time_str:
            return ""
        try:
            dt = datetime.fromisoformat(time_str.replace('.000Z', '').replace('Z', '+00:00'))
            return dt.strftime('%Y%m%d%H%M%S +0000')
        except:
            return ""
    
    def get_image_url(self, path):
        if not path:
            return ""
        if path.startswith('/'):
            path = path[1:]
        return f"{self.image_base}{path}"
    
    def create_xml(self, channels):
        tv = Element('tv')
        tv.set('generator-info-name', 'DishHomeGo EPG')
        tv.set('generator-info-url', 'https://storefront.dishhomego.com.np')
        
        for channel in channels:
            chan_id = str(channel.get('epgId') or channel.get('id', ''))
            chan_elem = SubElement(tv, 'channel')
            chan_elem.set('id', chan_id)
            
            name = SubElement(chan_elem, 'display-name')
            name.text = channel.get('title', '')
            
            images = channel.get('images', [])
            if images:
                icon = SubElement(chan_elem, 'icon')
                icon.set('src', self.get_image_url(images[0].get('path', '')))
        
        total_programs = 0
        
        for channel in channels:
            chan_id = str(channel.get('epgId') or channel.get('id', ''))
            
            # Get programs - real or fallback
            if 'epgPrograms' in channel and 'list' in channel['epgPrograms'] and channel['epgPrograms']['list']:
                programs = channel['epgPrograms']['list']
            else:
                # Create fallback programs using channel's own data
                programs = self.create_fallback_programs(channel)
            
            for idx, prog in enumerate(programs):
                start = self.format_time(prog.get('start'))
                stop = self.format_time(prog.get('stop'))
                
                if not start or not stop:
                    continue
                
                total_programs += 1
                
                programme = SubElement(tv, 'programme')
                programme.set('start', start)
                programme.set('stop', stop)
                programme.set('channel', chan_id)
                programme.set('catchup-id', f"{datetime.now().strftime('%d%m%y')}{chan_id[:6]}{idx:03d}")
                
                # Title - use channel title as fallback
                title_text = prog.get('title') or channel.get('title', 'Programme')
                SubElement(programme, 'title').text = title_text
                
                # Description - use program or channel description
                desc_text = prog.get('fullSynopsis') or channel.get('fullSynopsis', '')
                SubElement(programme, 'desc').text = desc_text
                
                # Category
                category = SubElement(programme, 'category')
                cats = prog.get('catogory', []) or channel.get('catogory', ['General'])
                category.text = str(cats[0]) if cats else 'General'
                
                # Date
                try:
                    prog_date = datetime.fromisoformat(prog.get('start', '').replace('.000Z', '').replace('Z', '+00:00'))
                    SubElement(programme, 'date').text = prog_date.strftime('%Y%m%d')
                except:
                    SubElement(programme, 'date').text = datetime.now().strftime('%Y%m%d')
                
                # Icon - use program image or channel image
                prog_images = channel.get('images', [])
                if prog_images:
                    icon = SubElement(programme, 'icon')
                    icon.set('src', self.get_image_url(prog_images[0].get('path', '')))
                else:
                    channel_images = channel.get('images', [])
                    if channel_images:
                        icon = SubElement(programme, 'icon')
                        icon.set('src', self.get_image_url(channel_images[0].get('path', '')))
                
                # Sub-title
                sub_text = prog.get('shortSynopsis', '') or desc_text[:100] + '...' if len(desc_text) > 100 else desc_text
                SubElement(programme, 'sub-title').text = sub_text
        
        return tv, total_programs
    
    def save_xml(self, xml_element):
        xml_str = minidom.parseString(tostring(xml_element, 'utf-8')).toprettyxml(indent='\t')
        xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_str.split('\n', 1)[1]
        
        with open('gotv.xml', 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        return os.path.getsize('gotv.xml')
    
    def compress(self):
        with open('gotv.xml', 'rb') as f_in:
            with gzip.open('gotv.xml.gz', 'wb') as f_out:
                f_out.write(f_in.read())
        
        return os.path.getsize('gotv.xml.gz')
    
    def run(self):
        print("DishHomeGo EPG Generator")
        print("=" * 40)
        
        print("Fetching data...")
        channels = self.fetch_data()
        
        if not channels:
            print("No data fetched")
            return
        
        # Count channels without EPG
        no_epg_count = 0
        for channel in channels:
            if not ('epgPrograms' in channel and 'list' in channel['epgPrograms'] and channel['epgPrograms']['list']):
                no_epg_count += 1
        
        print(f"Found {len(channels)} channels ({no_epg_count} without EPG)")
        
        print("Generating XML...")
        xml, program_count = self.create_xml(channels)
        
        print("Saving files...")
        xml_size = self.save_xml(xml)
        gz_size = self.compress()
        
        print("\n" + "=" * 40)
        print("EPG Generation Complete")
        print("=" * 40)
        print(f"Channels: {len(channels)}")
        print(f"  - With EPG: {len(channels) - no_epg_count}")
        print(f"  - With fallback: {no_epg_count}")
        print(f"Total programs: {program_count}")
        print(f"Files: gotv.xml ({xml_size/1024:.1f} KB)")
        print(f"       gotv.xml.gz ({gz_size/1024:.1f} KB)")
        print(f"Compression: {(1 - (gz_size / xml_size)) * 100:.1f}%")

def main():
    DishHomeGoEPG().run()

if __name__ == '__main__':
    main()
