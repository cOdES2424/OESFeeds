import os
import time
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Load login information from environment variables
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')

# Initialize Selenium WebDriver
driver = webdriver.Chrome()  # Ensure ChromeDriver is in your PATH
driver.get('https://apps.occ.ok.gov/PSTPortal/Account/Login')

# Log in
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'UserName'))).send_keys(username)
driver.find_element(By.NAME, 'Password').send_keys(password)
driver.find_element(By.XPATH, '//button[@type="submit"]').click()

# Function to navigate pages and scrape data
def scrape_data(page_number):
    date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
    url = (f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange'
           f'&DateRangeFrom={date_14_days_ago}&DateRangeTo={date_14_days_ago}'
           f'&btnSubmitDateSearch=Search+by+Date+Range&pageNumber={page_number}')
    
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'tablePublicImagingSearchResults')))
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
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

# Close the WebDriver
driver.quit()
