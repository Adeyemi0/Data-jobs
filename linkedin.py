import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import random
import re
import pandas as pd
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import requests  # For sending HTTP requests to Telegram API

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Remove this line to run the browser in normal mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')

# Function to convert "Time Posted" string to elapsed seconds
def parse_time_posted(time_str):
    if time_str == "N/A":
        return float('inf')  # Treat missing data as very old (large value)
    
    # Define regex patterns for extracting numbers and units
    match = re.match(r'(\d+)\s+(\w+)\s+ago', time_str)
    if not match:
        return float('inf')  # Invalid format treated as very old
    
    num = int(match.group(1))
    unit = match.group(2).lower()
    
    # Convert to seconds based on the unit (limited to seconds, minutes, and hours)
    if unit in ['second', 'seconds']:
        return num
    elif unit in ['minute', 'minutes']:
        return num * 60
    elif unit in ['hour', 'hours']:
        return num * 3600
    else:
        return float('inf')  # Unknown unit treated as very old

# Function to extract job listings from Google search results
def extract_jobs(driver, location, job, start):
    base_url = "https://www.google.com/search?q=site:linkedin.com/jobs+%22{}%22+and+%22jobs%22+and+%22{}%22&tbs=qdr:d&start={}"
    search_url = base_url.format(job.replace(" ", "+"), location.replace(" ", "+"), start)
    
    print(f"Searching: {search_url}")
    driver.get(search_url)
    time.sleep(random.uniform(3, 5))  # Add initial sleep to let the page load
    
    # Check for multiple possible selectors to handle potential Google layout changes
    selectors = ['div.MjjYud', 'div.g', 'div.Gx5Zad', 'div.tF2Cxc']
    
    element_found = False
    for selector in selectors:
        try:
            print(f"Trying selector: {selector}")
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            results = driver.find_elements(By.CSS_SELECTOR, selector)
            if results:
                print(f"Found {len(results)} results with selector: {selector}")
                element_found = True
                break
        except TimeoutException:
            print(f"Timeout with selector: {selector}")
            continue
    
    # If no elements found with any selector, log the error but don't save files
    if not element_found:
        print(f"ERROR: No results found with any selector for {location}, {job}, start={start}")
        return []
    
    all_data = []
    for result in results:
        try:
            title_tag = result.find_element(By.TAG_NAME, 'a')
            title = title_tag.text.strip()
            link = title_tag.get_attribute('href')
            
            # If we couldn't extract a proper title, try another approach
            if not title:
                h3_tag = result.find_element(By.TAG_NAME, 'h3')
                title = h3_tag.text.strip()
        except NoSuchElementException:
            title = "N/A"
            link = "N/A"
        
        try:
            # Look for the time posted information without storing the description
            description_tag = None
            for desc_selector in ['div.VwiC3b', 'div.IsZvec', 'span.aCOpRe']:
                try:
                    description_tag = result.find_element(By.CSS_SELECTOR, desc_selector)
                    if description_tag:
                        break
                except:
                    continue
            
            # Extract time posted from the description element if found
            time_posted = "N/A"
            if description_tag:
                description_text = description_tag.text.strip()
                time_match = re.search(r'\d+\s\w+\sago', description_text)
                time_posted = time_match.group() if time_match else "N/A"
        except:
            time_posted = "N/A"

        # Only add entries that have valid data AND contain 'https://www.linkedin.com/jobs' in the link
        if title != "N/A" and link != "N/A" and 'https://www.linkedin.com/jobs' in link:
            # Filter titles based on keywords in the 'jobs' list
            if any(keyword.lower() in title.lower() for keyword in jobs):
                all_data.append({
                    "Title": title,
                    "Location": location,
                    "Link": link,
                    "Time Posted": time_posted
                })
    
    return all_data

# Main scraping logic
locations = ['United States']
jobs = [
    'machine-learning',
    'data-analyst',
    'data-scientist',
    'data-engineer',
    'business-intelligence analyst',
    'big-data-engineer',
    'database-administrator',
    'data-visualization-specialist',
    'quantitative-analyst',
    'natural-language-processing-(NLP)-engineer',
    'computer-vision-engineer']

all_data = []

# Initialize undetected Chrome driver
try:
    driver = uc.Chrome(options=chrome_options)
    
    for location in locations:
        for job in jobs:
            for start in [0, 10, 20]:
                try:
                    job_data = extract_jobs(driver, location, job, start)
                    all_data.extend(job_data)
                    
                    # Log status but don't save interim files
                    print(f"Collected {len(job_data)} jobs for {job} in {location} (start={start})")
                    print(f"Total jobs collected so far: {len(all_data)}")
                    
                    # Longer wait between requests to reduce the chance of being rate-limited
                    wait_time = random.uniform(15, 30)
                    print(f"Waiting {wait_time:.2f} seconds before next request")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    print(f"Error processing {job} in {location} at start={start}: {str(e)}")
                    # Continue with next search instead of stopping the entire script
                    continue
                    
finally:
    # Make sure to close the driver even if an exception occurs
    try:
        driver.quit()
    except:
        pass

# Save complete data to CSV
if all_data:
    df = pd.DataFrame(all_data)
    # Additional verification to ensure all links have 'https://www.linkedin.com/jobs'
    df = df[df['Link'].str.contains('https://www.linkedin.com/jobs')]
    df['Title'] = df['Title'].apply(lambda x: re.split(r'\.\.\.', x)[0])
    df['Title'] = df['Title'].apply(lambda x: x.split('\n')[0])
    
    # Parse "Time Posted" and add a new column for elapsed seconds
    df['Elapsed Seconds'] = df['Time Posted'].apply(parse_time_posted)
    
    # Sort the DataFrame by elapsed seconds (ascending order: newest first)
    df = df.sort_values(by='Elapsed Seconds')
    # Drop the temporary "Elapsed Seconds" column (optional)
    df = df.drop(columns=['Elapsed Seconds'])

    df = df.drop_duplicates(subset=['Link'], keep='first')
    # Exclude the 'Job' column from the final DataFrame
    df = df.drop(columns=['Job'], errors='ignore')
    
    df.to_json('jobs_data.json', orient='records', indent=4)
    print("Data saved to jobs_data.json")
else:
    print("No data was collected")

# Send job postings to Telegram
telegram_url_template = 'https://api.telegram.org/bot7173983862:AAFRR1WfQghxg9kfAYx83yVyPYJYcazjiwg/sendMessage?chat_id=-1002164889618&text="{}"'

if not df.empty:
    for _, row in df.iterrows():
        title = row['Title']
        location = row['Location']
        link = row['Link']
        posted_time = row['Time Posted']
        
        # Format the message
        message = f"{title} is hiring. {location}. Posted {posted_time}. {link}"
        
        # URL encode the message
        encoded_message = message.replace('"', '\\"')  # Escape double quotes
        
        # Construct the full Telegram API URL
        telegram_url = telegram_url_template.format(encoded_message)
        
        # Send the message to Telegram
        try:
            response = requests.get(telegram_url)
            if response.status_code == 200:
                print(f"Successfully sent message to Telegram: {message}")
            else:
                print(f"Failed to send message to Telegram: {response.text}")
        except Exception as e:
            print(f"Error sending message to Telegram: {str(e)}")
else:
    print("No data to send to Telegram.")
