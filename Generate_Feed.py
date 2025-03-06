
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import csv

# Constants
FEED_LIMIT = 50  # Limit the feed to the most recent 50 items

# Function to load case details from CSV
def load_case_details(csv_file):
    case_details = {}
    with open(csv_file, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            case_details[row['case_number']] = {
                'case_name': row['case_name'],
                'job_number': row['job_number'],
                'project_manager': row['project_manager']
            }
    return case_details

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}

# Load case details
case_details = load_case_details('case_names.csv')

# Step 1: Open the login page and get the login form
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_page = session.get(login_url)
soup = BeautifulSoup(login_page.content, 'html.parser')

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

# Load the last processed date
last_processed_date = None
if os.path.exists('last_processed_date.txt'):
    with open('last_processed_date.txt', 'r') as f):
        last_processed_date = datetime.strptime(f.read().strip(), '%Y-%m-%d %H:%M:%S%z')
    print(f"Loaded last processed date: {last_processed_date}")
else:
    print("last_processed_date.txt not found, starting fresh")

new_titles = []
for row in rows:
    cells = row.find_all('td')
    if cells:
        action_date = cells[1].text.strip()
        case_number = cells[2].text.strip()
        action_type = cells[3].text.strip()
        action_status = cells[4].text.strip()
        subject = cells[5].text.strip()
        
        # Lookup case details from the CSV file
        case_detail = case_details.get(case_number, {
            'case_name': 'Unknown Case Name',
            'job_number': 'Unknown Job Number',
            'project_manager': 'Unknown Project Manager'
        })
        
        title = f"{case_number} - {case_detail['case_name']} - {action_type} - {action_status} - {subject} - {action_date}"
        description = f"{case_number} - {case_detail['case_name']} - {case_detail['job_number']} - {case_detail['project_manager']} - {action_type} - {action_status} - {subject} - {action_date}"
        
        if title not in existing_titles:
            try:
                # Parse the date and convert to local time (CST)
                date_obj = datetime.strptime(action_date, '%m/%d/%Y')
                date_obj = date_obj.replace(tzinfo=timezone(timedelta(hours=-6)))  # CST without changing the date
                
                print(f"Parsed date: {date_obj} for action_date: {action_date}")  # Debug statement
                
                if not last_processed_date or date_obj > last_processed_date:
                    new_titles.append((title, description, date_obj))
            except ValueError:
                print(f"Skipping invalid date format: {action_date}")
                continue

# Sort new titles by date (newest first)
new_titles.sort(key=lambda x: x[2], reverse=True)

# Limit the number of items in the feed
new_titles = new_titles[:FEED_LIMIT]

# Step 7: Generate RSS feed manually
rss = ET.Element('rss', version='2.0', nsmap={'atom': 'http://www.w3.org/2005/Atom'})
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Case Actions Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
ET.SubElement(channel, 'description').text = 'Feed of case actions from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

# Add atom:link element
atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
atom_link.set('href', 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx')
atom_link.set('rel', 'self')
atom_link.set('type', 'application/rss+xml')

for title, description, date_obj in new_titles:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
    ET.SubElement(item, 'description').text = description
    
    # Create a unique GUID using a hash
    guid = hashlib.md5(title.encode()).hexdigest()
    ET.SubElement(item, 'guid').text = guid
    
    ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S %z')

rss_feed_path = 'case_actions_feed.xml'
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

# Save new titles to the processed items file
if new_titles:
    with open('processed_items.txt', 'a') as f:
        for title, _, _ in new_titles:
            f.write(title + '\n')
    print(f"Added {len(new_titles)} new titles to processed_items.txt")

# Update the last processed date
if new_titles:
    latest_date = new_titles[0][2]
    with open('last_processed_date.txt', 'w') as f:
        f.write(latest_date.strftime('%Y-%m-%d %H:%M:%S%z'))
    print(f"Updated last processed date to: {latest_date}")

print("RSS feed generated successfully")
