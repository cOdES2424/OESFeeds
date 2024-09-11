from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta

# Set up the Selenium WebDriver (e.g., Chrome)
driver = webdriver.Chrome()  # Ensure ChromeDriver is in PATH

# Step 1: Open the login page
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
driver.get(login_url)

# Step 2: Fill in the login form with correct field locators
username = driver.find_element(By.NAME, 'UserName')
password = driver.find_element(By.NAME, 'Password')

# Enter your login credentials
username.send_keys('bolzmi@hotmail.com')
password.send_keys('redfred4')

# Step 3: Submit the login form
password.send_keys(Keys.RETURN)

# Give the page some time to load after login
time.sleep(5)

# Step 4: Navigate to the intermediary page
intermediate_url = 'https://apps.occ.ok.gov/PSTPortal/CorrectiveAction/Forward?Length=16'
driver.get(intermediate_url)

# Wait for the intermediate page to load
time.sleep(5)

# Step 5: Navigate to the Case Actions page
case_actions_url = 'https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx'
driver.get(case_actions_url)

# Wait for the Case Actions page to load
time.sleep(5)

# Step 6: Parse the page with BeautifulSoup
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

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

# Step 7: Generate feed with Feedgen
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

# Step 8: Generate OPML file
opml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head>
    <title>Case Actions Feed</title>
    <ownerName>OES</ownerName>
  </head>
  <body>
    <outline text="Case Actions Feed" type="rss" xmlUrl="{rss_feed_path}" htmlUrl="https://apps.occ.ok.gov/LicenseePortal/CaseActions.aspx"/>
  </body>
</opml>
"""

with open('case_actions_feed.opml', 'w') as f:
    f.write(opml_content)

print("OPML file generated successfully")

# Step 9: Close the WebDriver
driver.quit()