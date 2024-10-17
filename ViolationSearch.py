import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import os
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException

# Step 1: Initialize the webdriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# Step 2: Login using Selenium
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
driver.get(login_url)
username = driver.find_element(By.NAME, 'UserName')
password = driver.find_element(By.NAME, 'Password')
username.send_keys('bolzmi@hotmail.com')
password.send_keys('redfred4')
submit_button = driver.find_element(By.XPATH, '//button[@type="submit"]')
submit_button.click()

# Step 3: Navigate to the target page
target_url = 'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home'
driver.get(target_url)
search_by_date_tab = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//a[@href="#SearchByDate"]')))
search_by_date_tab.click()

# Step 4: Set the date range
date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
date_from_field = driver.find_element(By.ID, 'DateRangeFrom')
date_to_field = driver.find_element(By.ID, 'DateRangeTo')
date_from_field.send_keys(date_14_days_ago)
date_to_field.send_keys(date_14_days_ago)
search_button = driver.find_element(By.ID, 'btnSubmitDateSearch')
search_button.click()

# Step 5: Scrape data across pages and filter by keywords
def scrape_current_page():
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table_rows = soup.select('table#tablePublicImagingSearchResults tr')
    for row in table_rows:
        columns = row.find_all('td')
        data = [col.text.strip() for col in columns]
        if any(keyword in data for keyword in ['NOV', 'NOCR', 'SOR']):
            print(data)  # Replace this with processing the data as required

# Initial scrape
scrape_current_page()

# Pagination loop
while True:
    try:
        next_button = driver.find_element(By.ID, 'nextPage')
        if 'disabled' in next_button.get_attribute('class'):
            break
        next_button.click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'resultsTable')))
        scrape_current_page()
    except NoSuchElementException:
        break

# Step 6: Parse and filter data to generate RSS feed
# (Reuse your existing parsing and RSS generation code here)

# Shutdown the driver
driver.quit()
