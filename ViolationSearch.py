import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import time

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}

# Step 1: Open the login page and get the login form
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_page = session.get(login_url)

if login_page.status_code != 200:
    print('Failed to fetch login page')
    exit()

print('Login page fetched')
soup = BeautifulSoup(login_page.content, 'html.parser')

# Find the hidden input fields and add them to login_data
hidden_inputs = soup.find_all('input', type='hidden')
for hidden_input in hidden_inputs:
    login_data[hidden_input['name']] = hidden_input['value']

# Step 3: Submit the login form
response = session.post(login_url, data=login_data)

if response.status_code != 200:
    print('Login failed')
    exit()

print('Logged in successfully')

# Step 4: Function to navigate pages and scrape data
def scrape_data(page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    search_data = {
        'DateRangeFrom': date_14_days_ago,
        'DateRangeTo': date_14_days_ago,
        'btnSubmitDateSearch': 'Search by Date Range',
        'pageNumber': page_number
    }
    url = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
    
    response = session.post(url, data=search_data)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return []

    print(f'Navigated to page {page_number}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')

    results = []
    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else []

        # Process each row
        for row in rows:
            columns = row.find_all('td')
            if len(columns) > 3:
                description = columns[2].text.strip()
                print(f'Description: {description}')  # Debug column content
                if any(keyword in description for keyword in ['NOV', 'NOCR', 'SOR']):
                    entry = {
                        'id': columns[1].text.strip(),
                        'description': description,
                        'date': columns[3].text.strip()
                    }
                    results.append(entry)

    return results

all_results = []
# Loop through the first 6 pages
for page in range(6):
    page_results = scrape_data(page)
    all_results.extend(page_results)
    time.sleep(5)  # Wait between page requests to avoid rate limiting

print(f'Total data scraped: {len(all_results)} entries')

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

# Define the path to the root directory of your GitHub repository
main_directory = os.path.join(os.path.dirname(__file__), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(main_directory, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {main_directory}")
