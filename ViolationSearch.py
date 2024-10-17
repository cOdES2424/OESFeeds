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
print('Login page fetched')
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
print('Logged in successfully')

# Step 4: Navigate to the target page with search parameters
date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
target_url = f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange&DateRangeFrom={date_14_days_ago}&DateRangeTo={date_14_days_ago}&btnSubmitDateSearch=Search+by+Date+Range&pageNumber=0'
response = session.get(target_url)
print('Navigated to target page')
soup = BeautifulSoup(response.content, 'html.parser')

# Step 5: Scrape data from the specific table
def scrape_current_page(soup):
    print('Scraping current page...')
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    table_rows = table.find_all('tr', class_=lambda x: x in ['odd', 'even'])
    results = []
    for row in table_rows:
        columns = row.find_all('td')
        if columns and len(columns) > 3:
            entry = {
                'id': columns[1].text.strip(),
                'description': columns[2].text.strip(),
                'date': columns[3].text.strip()
            }
            if any(keyword in entry['description'] for keyword in ['NOV', 'NOCR', 'SOR']):
                results.append(entry)
    print(f'Page results: {results}')
    return results

results = scrape_current_page(soup)
print(f'Initial data scraped: {results}')

# Step 6: Generate RSS feed
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Violation Search Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
ET.SubElement(channel, 'description').text = 'Feed of violations from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

for entry in results:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
    ET.SubElement(item, 'description').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    guid = hashlib.md5(f"{entry['id']} - {entry['description']} - {entry['date']}".encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    date_obj = datetime.strptime(entry['date'], '%m/%d/%Y')
    date_obj = date_obj.replace
