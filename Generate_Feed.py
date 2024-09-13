import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import os
import subprocess

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

filtered_titles = []
for row in rows:
    cells = row.find_all('td')
    if cells:
        action_date = cells[1].text.strip()
        case_number = cells[2].text.strip()
        action_type = cells[3].text.strip()
        action_status = cells[4].text.strip()
        subject = cells[5].text.strip()
        
        # Assuming you want to filter by date (e.g., last 30 days)
        try:
            date_obj = datetime.strptime(action_date, '%m/%d/%Y')
            if date_obj >= datetime.now() - timedelta(days=30):
                title = f"{case_number} - {action_type} - {action_status} - {subject} - {action_date}"
                filtered_titles.append(title)
        except ValueError:
            continue  # Skip rows where the date format is incorrect

# Reverse the order of filtered titles to show newest first
filtered_titles.reverse()

# Step 7: Generate RSS feed manually
rss = ET.Element('rss', version='2.0', attrib={'xmlns:atom': 'http://www.w3.org/2005/Atom'})
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Case Actions Feed'
ET.SubElement(channel, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
ET.SubElement(channel, 'description').text = 'Feed of case actions from the Oklahoma Corporation Commission'
ET.SubElement(channel, 'language').text = 'en-US'
ET.SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')
ET.SubElement(channel, 'atom:link', href="https://raw.githubusercontent.com/bolzmi/CaseActions/main/case_actions_feed.xml", rel="self", type="application/rss+xml")

for idx, title in enumerate(filtered_titles):
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
    ET.SubElement(item, 'description').text = title
    ET.SubElement(item, 'guid').text = f"unique-identifier-{idx}"
    ET.SubElement(item, 'pubDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')

rss_feed_path = 'case_actions_feed.xml'
tree = ET.ElementTree(rss)
tree.write(rss_feed_path, encoding='utf-8', xml_declaration=True)

print("RSS feed generated successfully")

# Step 8: Generate OPML file
opml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head>
    <title>Case Actions Feed</title>
    <ownerName>OES</ownerName>
  </head>
  <body>
    <outline text="Case Actions Feed" type="rss" xmlUrl="https://raw.githubusercontent.com/bolzmi/CaseActions/main/case_actions_feed.xml" htmlUrl="https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx"/>
  </body>
</opml>
"""

with open('case_actions_feed.opml', 'w') as f:
    f.write(opml_content)

print("OPML file generated successfully")

# Step 9: Check for changes and commit if there are any
try:
    subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions'], check=True)
    subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions@github.com'], check=True)
    subprocess.run(['git', 'add', 'case_actions_feed.xml', 'case_actions_feed.opml'], check=True)
    result = subprocess.run(['git', 'commit', '-m', 'Update RSS feed'], capture_output=True, text=True)
    if 'No changes to commit' in result.stdout:
        print("No new changes to commit")
    else:
        subprocess.run(['git', 'push'], check=True)
        print("Changes committed and pushed")
except subprocess.CalledProcessError as e:
    print(f"Error during git operations: {e}")
