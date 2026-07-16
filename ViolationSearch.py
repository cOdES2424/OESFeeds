import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import time
import urllib.parse

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}


def login(session):
    login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'

    login_page = session.get(login_url)
    soup = BeautifulSoup(login_page.content, 'html.parser')

    # Find hidden input fields and add them to login_data
    hidden_inputs = soup.find_all('input', type='hidden')
    for hidden_input in hidden_inputs:
        login_data[hidden_input['name']] = hidden_input.get('value', '')

    print('Login data loaded')

    response = session.post(login_url, data=login_data)

    if response.url == login_url:
        raise ValueError("Login failed. Please check your credentials.")

    print('Logged in successfully')
    return session


# Initialize session and login
session = requests.Session()
session = login(session)


def scrape_data(session, page_number):
    # Search date = 14 days ago
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    encoded_date = urllib.parse.quote(date_14_days_ago)

    url = (
        f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
        f'&DateRangeFrom={encoded_date}'
        f'&DateRangeTo={encoded_date}'
        f'&btnSubmitDateSearch=Search+by+Date+Range'
        f'&pageNumber={page_number}'
    )

    print(f'Navigating to URL: {url}')

    response = session.get(url)

    # If OCC dumps us back to login, log back in and retry
    if 'login' in response.text.lower():
        print('Detected login page. Logging in again...')
        session = login(session)
        response = session.get(url)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return []

    print(f'Navigated to page {page_number}')

    soup = BeautifulSoup(response.content, 'html.parser')

    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})

    print(f'Table found on page {page_number}: {table is not None}')

    results = []

    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else []

        for row in rows:
            columns = row.find_all('td')

            # New OCC table format
            if len(columns) > 5:
                image_id = columns[1].get_text(strip=True)
                facility_number = columns[2].get_text(strip=True)
                description = columns[3].get_text(strip=True)
                image_date = columns[4].get_text(strip=True)

                print(f'Description: {description}')

                if any(keyword in description.upper() for keyword in ['NOV', 'NOCR', 'SOR']):
                    results.append({
                        'id': facility_number,
                        'image_id': image_id,
                        'description': description,
                        'date': image_date
                    })

    return results


all_results = []

# Loop through pages
for page in range(25):
    page_results = scrape_data(session, page)
    all_results.extend(page_results)
    time.sleep(6)

print(f'Total data scraped: {len(all_results)} entries')

# Build RSS feed
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')

ET.SubElement(channel, 'title').text = 'Violation Search Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
ET.SubElement(channel, 'description').text = 'Feed of violations from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(
    timezone.utc
).strftime('%a, %d %b %Y %H:%M:%S %z')

for entry in all_results:
    item = ET.SubElement(channel, 'item')

    ET.SubElement(
        item,
        'title'
    ).text = f"{entry['id']} - {entry['description']} - {entry['date']}"

    ET.SubElement(
        item,
        'link'
    ).text = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'

    ET.SubElement(
        item,
        'description'
    ).text = f"{entry['id']} - {entry['description']} - {entry['date']}"

    guid = hashlib.md5(
        f"{entry['id']} - {entry['description']} - {entry['date']}".encode()
    ).hexdigest()

    ET.SubElement(item, 'guid').text = guid

    # OCC now appears to return dates as YYYY-MM-DD
    date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
    date_obj = date_obj.replace(tzinfo=timezone.utc)

    ET.SubElement(
        item,
        'pubDate'
    ).text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Write RSS file
main_directory = os.path.join(
    os.path.dirname(__file__),
    'violation_search_feed.xml'
)

tree = ET.ElementTree(rss)
tree.write(
    main_directory,
    encoding='utf-8',
    xml_declaration=True
)

print(f"RSS feed generated successfully at {main_directory}")
