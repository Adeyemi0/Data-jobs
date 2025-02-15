import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import random
import re
import pandas as pd
import os
import requests
import logging
from fake_useragent import UserAgent
from requests.exceptions import RequestException

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Function to configure Chrome options
def configure_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={UserAgent().random}")  # Add a randomized user-agent
    return chrome_options

# Function to extract job listings from LinkedIn
def extract_jobs(location, job, start):
    base_url = "https://www.linkedin.com/jobs/search/?keywords={}&location={}&start={}"
    search_url = base_url.format(job.replace(" ", "%20"), location.replace(" ", "%20"), start)
    
    try:
        # Initialize browser for each iteration
        chrome_options = configure_chrome_options()

        # Force undetected_chromedriver to match your Chrome version (131 in this case)
        driver = uc.Chrome(options=chrome_options, version_main=131)
        driver.get(search_url)
        time.sleep(random.uniform(5, 8))  # Randomized sleep to mimic human browsing behavior
        
        # Extract job results from the page
        results = driver.find_elements(By.CSS_SELECTOR, 'div.job-card-container')
        all_data = []
        for result in results:
            try:
                title_tag = result.find_element(By.TAG_NAME, 'a')
                title = title_tag.text.strip()
                
                # Remove everything after "..." using regex
                title = re.sub(r'\bLinkedIn\b.*', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\bhttps://\b.*', '', title, flags=re.IGNORECASE)
                
                link = title_tag.get_attribute('href')
            except:
                title = "N/A"
                link = "N/A"

            try:
                description_tag = result.find_element(By.CSS_SELECTOR, 'div.job-card-list__footer')
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

        driver.quit()  # Close browser after extracting jobs
        return all_data

    except Exception as e:
        logger.error(f"Error during scraping for {job} in {location} (start={start}): {e}")
        return []

# Function to send messages to Telegram with rate limit handling
def send_to_telegram(df):
    telegram_url_template = os.getenv("TELEGRAM_URL")
    max_messages_per_second = 30
    delay_between_batches = 1  # 1 second delay after sending a batch of messages
    batch_size = max_messages_per_second  # Send messages in batches of 30
    max_retries = 5  # Max retries in case of 429 rate-limiting error
    retry_delay = 2  # Start with a 2-second delay between retries

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        message = f"{row['Title']}. \nLocation: {row['Location']}. \nLink: {row['Link']}. \nTime Posted: {row['Time Posted']}"
        telegram_url = telegram_url_template.format(message)
        retry_count = 0

        while retry_count <= max_retries:
            try:
                response = requests.get(telegram_url, timeout=10)
                if response.status_code == 200:
                    break  # Successful, break the retry loop
                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit (429). Retrying after {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_count += 1
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.warning(f"Failed to send message to Telegram: {response.status_code}")
                    break  # Other error, no retry
            except RequestException as e:
                logger.error(f"Error sending message to Telegram: {e}")
                break  # Network error, stop retrying

        # Pause after each batch of messages to ensure the rate limit is respected
        if i % batch_size == 0:
            time.sleep(delay_between_batches)

# Main scraping logic
locations = ['Nigeria', 'United States', 'United Kingdom', 'Canada']
jobs = ['machine learning', 'data analyst', 'data scientist', 'data engineer', 'business intelligence analyst']
all_data = []

for location in locations:
    for job in jobs:
        for start in [1, 11]:  # Adjust start indices as needed
            logger.info(f"Scraping jobs for '{job}' in '{location}' (start={start})")
            job_data = extract_jobs(location, job, start)
            all_data.extend(job_data)
            
            # Longer wait between requests to reduce the chance of being rate-limited
            time.sleep(random.uniform(10, 20))

# Save results to DataFrame
df = pd.DataFrame(all_data)
df.drop_duplicates(subset=['Title'], inplace=True)  # Remove duplicates

# Send the results to Telegram after scraping is complete
send_to_telegram(df)

logger.info("Scraping completed and results sent to Telegram.")
