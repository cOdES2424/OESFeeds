import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import os

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

# Step 4: Navigate to the intermediary page
intermediate_url = 'https://apps.occ.ok.gov/PSTPortal/CorrectiveAction/Forward?Length=16'
session.get(intermediate_url)

# Step 5: Navigate to the Case Actions page
case_actions_url = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
case_actions_page = session.get(case_actions_url)

# Step 6: Parse the page with BeautifulSoup
soup = BeautifulSoup(case_actions_page.content, 'html.parser')

# Extract the necessary data from the table
table = soup.find('table', {'class': 'rptGridView'})  # Adjust the class as necessary
if not table:
    raise ValueError("Table not found on the page")

rows = table.find_all('tr')[1:]  # Skip the header row

# Load existing feed items to avoid duplicates
existing_titles = set()
if os.path.exists('processed_items.txt'):
    with open('processed_items.txt', 'r') as f:
        existing_titles = set(line.strip() for line in f)
    print(f"Loaded {len(existing_titles)} existing titles from processed_items.txt")
else:
    print("processed_items.txt not found, starting fresh")

new_titles = []
for row in rows:
    cells = row.find_all('td')
    if cells:
        action_date = cells[1].text.strip()
        case_number = cells[2].text.strip()
        action_type = cells[3].text.strip()
        action_status = cells[4].text.strip()
        subject = cells[5].text.strip()
        
        title = f"{case_number} - {action_type} - {action_status} - {subject} - {action_date}"
        if title not in existing_titles:
            new_titles.append(title)

# Step 7: Generate RSS feed manually
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Case Actions Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
ET.SubElement(channel, 'description').text = 'Feed of case actions from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

for title in new_titles:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
    ET.SubElement(item, 'description').text = title
    ET.SubElement(item, 'guid').text = title
    ET.SubElement(item, 'pubDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

rss_feed_path = 'case_actions_feed.xml'
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

# Save new titles to the processed items file
if new_titles:
    with open('processed_items.txt', 'a') as f:
        for title in new_titles:
            f.write(title + '\n')
    print(f"Added {len(new_titles)} new titles to processed_items.txt")
else:
    print("No new titles to add")

print("RSS feed generated successfully")
