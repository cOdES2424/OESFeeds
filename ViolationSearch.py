import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import os
import hashlib

# Step 1: Open the login page and get the login form
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_page = session.get(login_url)
soup = BeautifulSoup(login_page.content, 'html.parser')

# Step 2: Fill in the login form with correct field locators
login_data = {
    'UserName': 'bolzmi@hotmail.com',
    'Password': 'redfred4'
}

# Find the hidden input fields and add them to login_data
hidden_inputs = soup.find_all('input', type='hidden')
for hidden_input in hidden_inputs:
    login_data[hidden_input['name']] = hidden_input['value']

# Step 3: Submit the login form
session.post(login_url, data=login_data)

# Step 4: Navigate to the target page
target_url = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
response = session.get(target_url)
soup = BeautifulSoup(response.content, 'html.parser')

# Step 5: Click the "Search by Date Range" tab
search_by_date_url = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/SearchByDateRange'
session.get(search_by_date_url)

# Step 6: Set the date range and submit the search form
date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
search_data = {
    'DateRangeFrom': date_14_days_ago,
    'DateRangeTo': date_14_days_ago,
    'btnSubmitDateSearch': 'Search by Date Range'
}
search_result = session.post(search_by_date_url, data=search_data)
soup = BeautifulSoup(search_result.content, 'html.parser')

# Step 7: Scrape data and handle pagination
def scrape_current_page(soup):
    table_rows = soup.select('table#tablePublicImagingSearchResults tr')
    results = []
    for row in table_rows:
        columns = row.find_all('td')
        data = [col.text.strip() for col in columns]
        if any(keyword in data for keyword in ['NOV', 'NOCR', 'SOR']):
            results.append(data)
    return results

results = scrape_current_page(soup)

# Handle pagination
while True:
    next_button = soup.find('button', {'id': 'nextPage'})
    if next_button and 'disabled' not in next_button.get('class', ''):
        next_page_url = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/SearchByDateRange'  # Adjust if necessary
        search_result = session.post(next_page_url, data=search_data)
        soup = BeautifulSoup(search_result.content, 'html.parser')
        results.extend(scrape_current_page(soup))
    else:
        break

# Step 8: Generate RSS feed
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Violation Search Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
ET.SubElement(channel, 'description').text = 'Feed of violations from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

for data in results:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = ' - '.join(data)
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
    ET.SubElement(item, 'description').text = ' - '.join(data)
    guid = hashlib.md5(' - '.join(data).encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    date_obj = datetime.strptime(data[-1], '%m/%d/%Y')
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

rss_feed_path = 'violation_search_feed.xml'
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {rss_feed_path}")
