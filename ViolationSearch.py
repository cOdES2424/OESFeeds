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

# Step 4: Navigate to the target page
date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
target_url = f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home#SearchByDate'
response = session.get(target_url)
print('Navigated to target page')
soup = BeautifulSoup(response.content, 'html.parser')

# Step 5: Set the date range and submit the search form
search_data = {
    'DateRangeFrom': date_14_days_ago,
    'DateRangeTo': date_14_days_ago,
    'btnSubmitDateSearch': 'Search by Date Range'
}
search_result = session.post(target_url, data=search_data)
print('Search form submitted')
soup = BeautifulSoup(search_result.content, 'html.parser')

# Step 6: Scrape data and handle pagination
def scrape_current_page(soup):
    print(soup.prettify())  # Print the entire page content for debugging
    table_rows = soup.select('table#tablePublicImagingSearchResults tr')
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
    return results

results = scrape_current_page(soup)
print(f'Initial data scraped: {results}')

# Handle pagination
while True:
    next_button = soup.find('button', {'id': 'nextPage'})
    if next_button and 'disabled' not in next_button.get('class', ''):
        next_page_number = int(next_button.get('data-page-number')) + 1
        next_page_url = f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home#SearchByDate&pageNumber={next_page_number}'
        search_result = session.get(next_page_url)
        soup = BeautifulSoup(search_result.content, 'html.parser')
        results.extend(scrape_current_page(soup))
        print(f'Data after pagination: {results}')
    else:
        break

# Step 7: Generate RSS feed
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
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Define the path to the main directory
rss_feed_path = os.path.join(os.getcwd(), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {rss_feed_path}")
