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
    login_page = session.get(login_url, timeout=30)
    login_page.raise_for_status()
    soup = BeautifulSoup(login_page.content, 'html.parser')

    # Find the hidden input fields and add them to login_data
    hidden_inputs = soup.find_all('input', type='hidden')
    for hidden_input in hidden_inputs:
        login_data[hidden_input['name']] = hidden_input['value']

    # Never print credentials or anti-forgery tokens to the Actions log.
    print(f"Submitting OCC login for user: {login_data.get('UserName')!r}", flush=True)

    # Step 3: Submit the login form
    response = session.post(login_url, data=login_data, timeout=30)

    response.raise_for_status()

    # Verify that the POST did not return the login form again.
    response_soup = BeautifulSoup(response.content, 'html.parser')
    password_field = response_soup.find('input', {'type': 'password'})
    still_on_login_url = '/Account/Login' in response.url
    if still_on_login_url or password_field is not None:
        validation = response_soup.select_one('.validation-summary-errors, .text-danger')
        detail = validation.get_text(' ', strip=True) if validation else 'The login form was returned.'
        raise ValueError(f"Login failed: {detail}")

    print(f'Logged in successfully; redirected to {response.url}', flush=True)
    return session

# Initialize session and login
session = requests.Session()
session = login(session)

# Step 4: Function to navigate pages and scrape data
def scrape_data(session, page_number, attempt=1):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    encoded_date = urllib.parse.quote(date_14_days_ago)
    url = (f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
           f'&DateRangeFrom={encoded_date}&DateRangeTo={encoded_date}'
           f'&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}')
    
    print(f'Navigating to page {page_number} (attempt {attempt})', flush=True)

    response = session.get(url, timeout=30)

    # Only treat the response as a login page when it actually contains the
    # login form or redirected to the login URL. The word 'login' can appear
    # harmlessly in navigation, scripts, or page markup.
    response_soup = BeautifulSoup(response.content, 'html.parser')
    login_form = response_soup.find('form', action=lambda value: value and '/Account/Login' in value)
    if '/Account/Login' in response.url or login_form is not None:
        print('Session expired; logging in again...', flush=True)
        session = login(session)
        response = session.get(url, timeout=30)

    if response.status_code != 200:
        print(f'Failed to navigate to page {page_number}')
        return [], 0

    print(f'Navigated to page {page_number}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Avoid dumping the entire page into the GitHub Actions log.
    print(f'Received {len(response.content):,} bytes', flush=True)

    # Confirm table presence
    table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
    print(f'Table found on page {page_number}: {table is not None}')


    results = []
    row_count = 0
    if table:
        tbody = table.find('tbody')
        rows = tbody.find_all('tr', recursive=False) if tbody else []
        row_count = len(rows)
        print(f'Rows returned on page {page_number}: {row_count}', flush=True)

        # Current table columns:
        # 0 = details link, 1 = image/document ID, 2 = facility ID,
        # 3 = description, 4 = posted/scanned date, 5 = document date.
        for row in rows:
            columns = row.find_all('td', recursive=False)
            if len(columns) < 6:
                print(f'Skipping unexpected row with {len(columns)} columns')
                continue

            description = columns[3].get_text(" ", strip=True)

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

    return results, row_count

all_results = []
seen_ids = set()

# The OCC portal can intermittently return a blank page even when results
# exist. Retry blank pages, then continue until several consecutive page
# numbers have remained blank. This preserves redundancy without always
# crawling every possible page.
MAX_PAGES = 25
EMPTY_PAGE_RETRIES = 2
MAX_CONSECUTIVE_EMPTY_PAGES = 3
consecutive_empty_pages = 0

for page in range(MAX_PAGES):
    page_results = []
    row_count = 0

    for attempt in range(1, EMPTY_PAGE_RETRIES + 2):
        page_results, row_count = scrape_data(session, page, attempt)
        if row_count > 0:
            break

        if attempt <= EMPTY_PAGE_RETRIES:
            print(
                f'Page {page} was blank; waiting and retrying '
                f'({attempt}/{EMPTY_PAGE_RETRIES}).',
                flush=True,
            )
            time.sleep(4)

    for entry in page_results:
        if entry['id'] not in seen_ids:
            seen_ids.add(entry['id'])
            all_results.append(entry)

    if row_count == 0:
        consecutive_empty_pages += 1
        print(
            f'Page {page} remained blank after retries. '
            f'Consecutive blank pages: '
            f'{consecutive_empty_pages}/{MAX_CONSECUTIVE_EMPTY_PAGES}',
            flush=True,
        )

        if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY_PAGES:
            print('Blank-page threshold reached; stopping pagination.', flush=True)
            break
    else:
        consecutive_empty_pages = 0

    time.sleep(2)

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
    try:
        date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
    except ValueError:
        date_obj = datetime.strptime(entry['date'], '%m/%d/%Y')
    date_obj = date_obj.replace(tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

# Define the path to the root directory of your GitHub repository
main_directory = os.path.join(os.path.dirname(__file__), 'violation_search_feed.xml')
tree = ET.ElementTree(rss)
tree.write(main_directory, encoding='utf-8', xml_declaration=True)

print(f"RSS feed generated successfully at {main_directory}")
