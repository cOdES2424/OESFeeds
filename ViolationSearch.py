import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import time
import urllib.parse
from urllib.parse import urljoin

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}

def login(session):
    # Step 1: Open the login page and get the login form
    login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
    login_page = session.get(login_url)
    soup = BeautifulSoup(login_page.content, 'html.parser')

    # Find the hidden input fields and add them to login_data
    hidden_inputs = soup.find_all('input', type='hidden')
    for hidden_input in hidden_inputs:
        login_data[hidden_input['name']] = hidden_input['value']

    # Print the login data for debugging
    print('Login data:', login_data)

    # Step 3: Submit the login form
    response = session.post(login_url, data=login_data)

    # Verify login was successful
    if response.url == login_url:
        raise ValueError("Login failed. Please check your credentials.")

    print('Logged in successfully')
    return session

# Initialize session and login
session = requests.Session()
session = login(session)

# Step 4: Function to navigate pages and scrape data
def scrape_data(session, page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    encoded_date = urllib.parse.quote(date_14_days_ago)
    url = (f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
           f'&DateRangeFrom={encoded_date}&DateRangeTo={encoded_date}'
           f'&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}')
    
    print(f'Navigating to URL: {url}')  # Debug URL

    response = session.get(url)

    # Check if the page contains the word "login"
    if 'login' in response.text.lower():
        print('Detected login page, attempting to log in again...')
        session = login(session)
        response = session.get(url)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return []

    print(f'Navigated to page {page_number}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Print out the HTML content for debugging
    print(soup.prettify())

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')

    if table:
        print(table.prettify())  # Print the table HTML for debugging

    results = []
    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else []

        # Current table columns:
        # 0 = details link, 1 = image/document ID, 2 = facility ID,
        # 3 = description, 4 = posted/scanned date, 5 = document date.
        for row in rows:
            columns = row.find_all('td', recursive=False)
            if len(columns) < 6:
                print(f'Skipping unexpected row with {len(columns)} columns')
                continue

            description = columns[3].get_text(" ", strip=True)
            print(f'Description: {description}')

            if any(keyword in description.upper() for keyword in ('NOV', 'NOCR', 'SOR')):
                details_anchor = columns[0].find('a', href=True)
                details_url = (
                    urljoin(response.url, details_anchor['href'])
                    if details_anchor else response.url
                )

                results.append({
                    'id': columns[1].get_text(" ", strip=True),
                    'facility_id': columns[2].get_text(" ", strip=True),
                    'description': description,
                    'date': columns[5].get_text(" ", strip=True),
                    'link': details_url,
                })

    return results

all_results = []
# Loop through the pages
for page in range(25):
    page_results = scrape_data(session, page)
    all_results.extend(page_results)
    time.sleep(6)  # Wait between page requests to avoid rate limiting

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
    ET.SubElement(item, 'link').text = entry['link']
    ET.SubElement(item, 'description').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    guid = hashlib.md5(f"{entry['id']} - {entry['description']} - {entry['date']}".encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Define the path to the root directory of your GitHub repository
main_directory = os.path.join(os.path.dirname(__file__), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(main_directory, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {main_directory}")

Library
/
ViolationSearch_fixed.py
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import time
import urllib.parse
from urllib.parse import urljoin

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}

def login(session):
    # Step 1: Open the login page and get the login form
    login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
    login_page = session.get(login_url)
    soup = BeautifulSoup(login_page.content, 'html.parser')

    # Find the hidden input fields and add them to login_data
    hidden_inputs = soup.find_all('input', type='hidden')
    for hidden_input in hidden_inputs:
        login_data[hidden_input['name']] = hidden_input['value']

    # Print the login data for debugging
    print('Login data:', login_data)

    # Step 3: Submit the login form
    response = session.post(login_url, data=login_data)

    # Verify login was successful
    if response.url == login_url:
        raise ValueError("Login failed. Please check your credentials.")

    print('Logged in successfully')
    return session

# Initialize session and login
session = requests.Session()
session = login(session)

# Step 4: Function to navigate pages and scrape data
def scrape_data(session, page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    encoded_date = urllib.parse.quote(date_14_days_ago)
    url = (f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
           f'&DateRangeFrom={encoded_date}&DateRangeTo={encoded_date}'
           f'&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}')
    
    print(f'Navigating to URL: {url}')  # Debug URL

    response = session.get(url)

    # Check if the page contains the word "login"
    if 'login' in response.text.lower():
        print('Detected login page, attempting to log in again...')
        session = login(session)
        response = session.get(url)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return []

    print(f'Navigated to page {page_number}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Print out the HTML content for debugging
    print(soup.prettify())

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')

    if table:
        print(table.prettify())  # Print the table HTML for debugging

    results = []
    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else []

        # Current table columns:
        # 0 = details link, 1 = image/document ID, 2 = facility ID,
        # 3 = description, 4 = posted/scanned date, 5 = document date.
        for row in rows:
            columns = row.find_all('td', recursive=False)
            if len(columns) < 6:
                print(f'Skipping unexpected row with {len(columns)} columns')
                continue

            description = columns[3].get_text(" ", strip=True)
            print(f'Description: {description}')

            if any(keyword in description.upper() for keyword in ('NOV', 'NOCR', 'SOR')):
                details_anchor = columns[0].find('a', href=True)
                details_url = (
                    urljoin(response.url, details_anchor['href'])
                    if details_anchor else response.url
                )

                results.append({
                    'id': columns[1].get_text(" ", strip=True),
                    'facility_id': columns[2].get_text(" ", strip=True),
                    'description': description,
                    'date': columns[5].get_text(" ", strip=True),
                    'link': details_url,
                })

    return results

all_results = []
# Loop through the pages
for page in range(25):
    page_results = scrape_data(session, page)
    all_results.extend(page_results)
    time.sleep(6)  # Wait between page requests to avoid rate limiting

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
    ET.SubElement(item, 'link').text = entry['link']
    ET.SubElement(item, 'description').text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    guid = hashlib.md5(f"{entry['id']} - {entry['description']} - {entry['date']}".encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Define the path to the root directory of your GitHub repository
main_directory = os.path.join(os.path.dirname(__file__), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(main_directory, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {main_directory}")
