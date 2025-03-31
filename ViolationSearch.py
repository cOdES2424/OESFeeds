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

# Function to log in
def login(session):
    login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    login_page = session.get(login_url, headers=headers)

    if login_page.status_code != 200:
        print('Failed to fetch login page')
        return False

    print('Login page fetched')
    soup = BeautifulSoup(login_page.content, 'html.parser')

    # Find the hidden input fields and add them to login_data
    hidden_inputs = soup.find_all('input', type='hidden')
    for hidden_input in hidden_inputs:
        login_data[hidden_input['name']] = hidden_input['value']

    print('Hidden inputs:', hidden_inputs)  # Debug hidden inputs

    # Submit the login form
    response = session.post(login_url, data=login_data, headers=headers)

    if response.status_code != 200:
        print('Login failed')
        return False

    print('Logged in successfully')
    print('Response cookies:', session.cookies.get_dict())  # Debug response cookies
    print('Response headers:', response.headers)  # Debug response headers
    return True

# Function to navigate pages and scrape data
def scrape_data(session, page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    url = (f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
           f'&DateRangeFrom={date_14_days_ago}&DateRangeTo={date_14_days_ago}'
           f'&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = session.get(url, headers=headers)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return []

    print(f'Navigated to page {page_number}')
    print(f'Session cookies: {session.cookies.get_dict()}')  # Debug session cookies
    print(f'Response headers: {response.headers}')  # Debug response headers

    soup = BeautifulSoup(response.content, 'html.parser')

    # Print the HTML content for debugging
    print(f'HTML content on page {page_number}:')
    print(soup.prettify())

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')

    if not table:
        return None  # Indicate that the table was not found

    results = []
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

# Main script
session = requests.Session()
if not login(session):
    exit()

all_results = []
# Loop through the first 6 pages
for page in range(6):
    retries = 3
    while retries > 0:
        page_results = scrape_data(session, page)
        if page_results is not None:
            all_results.extend(page_results)
            break
        else:
            print(f'Retrying page {page}... ({3 - retries + 1}/3)')
            retries -= 1
            if retries == 0:
                print('Logging out and back in...')
                session = requests.Session()
                if not login(session):
                    exit()
    time.sleep(5)  # Wait between page requests to avoid rate limiting

print(f'Total data scraped: {len(all_results)} entries')

# Generate RSS feed
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
