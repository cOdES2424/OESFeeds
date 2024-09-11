import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta

# Step 1: Log in to the website
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_payload = {
    'UserName': 'bolzmi@hotmail.com',
    'Password': 'redfred4'
}
session.post(login_url, data=login_payload)

# Step 2: Navigate to the Case Actions page
case_actions_url = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
response = session.get(case_actions_url)

# Step 3: Parse the page with BeautifulSoup
soup = BeautifulSoup(response.content, 'html.parser')

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

# Step 4: Generate feed with Feedgen
fg = FeedGenerator()
fg.title('Case Actions Feed')
fg.link(href='https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx')
fg.description('Feed of case actions from the Oklahoma Corporation Commission')

for title in filtered_titles:
    fe = fg.add_entry()
    fe.title(title)
    fe.link(href='https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx')
    fe.description(title)

# Save the feed to a file
rss_feed_path = 'case_actions_feed.xml'
fg.rss_file(rss_feed_path)

print("RSS feed generated successfully")

# Step 5: Generate OPML file
opml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head>
    <title>Case Actions Feed</title>
    <ownerName>OES</ownerName>
  </head>
  <body>
    <outline text="Case Actions Feed" type="rss" xmlUrl="https://your-github-username.github.io/CaseActions/case_actions_feed.xml" htmlUrl="https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx"/>
  </body>
</opml>
"""

with open('case_actions_feed.opml', 'w') as f:
    f.write(opml_content)

print("OPML file generated successfully")
