import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import random
import re
import pandas as pd
import os
import requests

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode to avoid opening a browser window
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Function to extract job listings from Google search results
def extract_jobs(driver, location, job, start):
    base_url = "https://www.google.com/search?q=site:linkedin.com/jobs+%22{}%22+and+%22jobs%22+and+%22{}%22&tbs=qdr:d&start={}"
    search_url = base_url.format(job.replace(" ", "+"), location.replace(" ", "+"), start)
    
    driver.get(search_url)
    time.sleep(random.uniform(5, 8))  # Randomized sleep to mimic human browsing behavior
    
    # Extract job results from the page
    results = driver.find_elements(By.CSS_SELECTOR, 'div.MjjYud')
    
    all_data = []
    for result in results:
        try:
            title_tag = result.find_element(By.TAG_NAME, 'a')
            title = title_tag.text.strip()
            link = title_tag.get_attribute('href')
            
            # Remove everything from "\n" till the end
            title = re.sub(r'\n.*', '', title)
        except:
            title = "N/A"
            link = "N/A"
        
        try:
            description_tag = result.find_element(By.CSS_SELECTOR, 'div.VwiC3b')
            description = description_tag.text.strip()
            time_posted = re.search(r'\d+\s\w+\sago', description)
            time_posted = time_posted.group() if time_posted else "N/A"
        except:
            description = "N/A"
            time_posted = "N/A"

        all_data.append({
            "Title": title,
            "Location": location,
            "Job": job,
            "Link": link,
            "Time Posted": time_posted
        })
    
    return all_data

# Function to send message to Telegram
def send_to_telegram(df):
    telegram_url_template = os.getenv("TELEGRAM_URL")
    for _, row in df.iterrows():
        message = f"{row['Title']}. Location: {row['Location']}. Link: {row['Link']}"
        telegram_url = telegram_url_template.format(message)
        requests.get(telegram_url)

# Main scraping logic
locations = ['United States', 'India', 'United Kingdom', 'Nigeria', 'Canada', 'United Arab Emirates']
jobs = ['machine learning', 'data analyst', 'data scientist', 'data engineer', 'business intelligence analyst']
all_data = []

# Initialize undetected Chrome driver
driver = uc.Chrome(options=chrome_options)

for location in locations:
    for job in jobs:
        for start in [1, 10]:
            job_data = extract_jobs(driver, location, job, start)
            all_data.extend(job_data)
            
            # Longer wait between requests to reduce the chance of being rate-limited
            time.sleep(random.uniform(10, 20))

# Close the driver
driver.quit()

# Save data to CSV
df = pd.DataFrame(all_data)
df.to_csv("linkedin_jobs_with_time.csv", index=False)

# Send the results to Telegram
send_to_telegram(df)
