import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import os
import hashlib
import time

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

# Step 4: Function to navigate pages and scrape data
def scrape_data(page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    url = f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange&DateRangeFrom={date_14_days_ago}&DateRangeTo={date_14_days_ago}&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}'
    response = session.get(url)
    print(f'Navigated to page {page_number}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')

    results = []
    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else []
        for row in rows[:3]:  # Print first 3 rows
            columns = row.find_all('td')
            print(f'Row columns: {[col.text.strip() for col in columns]}')

        for row in rows:
            columns = row.find_all('td')
            if columns and len(columns) > 3:
                description = columns[2].text.strip()
                print(f'Description: {description}')  # Debug column content
                if 'NOV' in description or 'NOCR' in description or 'SOR' in description:
                    entry = {
                        'id': columns[1].text.strip(),
                        'description': description,
                        'date': columns[3].text.strip()
                    }
                    results.append(entry)

    return results

all_results = []

# Loop through pages until no more data is found
page = 0
while True:
    page_results = scrape_data(page)
    if not page_results:
        break
    all_results.extend(page_results)
    page += 1
    time.sleep(10)  # Wait between page requests to avoid rate limiting

print(f'Total data scraped: {all_results}')

# Step 5: Generate RSS feed
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Violation Search Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
ET.SubElement(channel, 'description').text = 'Feed of violations from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

for entry in all_results:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
    ET.SubElement(item, 'description').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    guid = hashlib.md5(f"{entry['id']} - {entry['description']} - {entry['date']}".encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    date_obj = datetime.strptime(entry['date'], '%m/%d/%Y')
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Define the path to the main directory
rss_feed_path = os.path.join(os.getcwd(), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {rss_feed_path}")
