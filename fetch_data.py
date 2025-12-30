import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import csv
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import os
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def extract_event_urls(url):
    """Extract all event URLs from the 25Live calendar, handling iframe content."""
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")
    
    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    event_links = []
    
    try:
        # Navigate to the calendar URL
        print(f"Navigating to {url}")
        driver.get(url)
        
        # Use a longer wait time for initial load
        print("Waiting for page to load...")
        time.sleep(8)
        
        # Try to find all iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"Found {len(iframes)} iframes")
        
        if len(iframes) >= 4:
            try:
                print("Switching to the target iframe (index 3)")
                driver.switch_to.frame(iframes[3])
                
                # Use a generous wait time to find the event elements
                time.sleep(5)
                
                # Now try to find the event descriptions
                event_descriptions = driver.find_elements(By.CLASS_NAME, "twMonthEventDescription")
                print(f"Found {len(event_descriptions)} event descriptions")
                
                for desc in event_descriptions:
                    try:
                        # Find the link element
                        link_element = desc.find_element(By.TAG_NAME, "a")
                        
                        # Extract event information
                        event_url = link_element.get_attribute("href")
                        event_id = link_element.get_attribute("url.eventid")
                        event_title = link_element.text
                        
                        # Store the information
                        event_links.append({
                            "title": event_title,
                            "url": event_url,
                            "event_id": event_id
                        })
                    except Exception as e:
                        print(f"Error extracting link: {str(e)}")
                        continue
            except Exception as e:
                print(f"Error processing iframe: {str(e)}")
        else:
            print("Not enough iframes found - trying to find events directly")
            try:
                event_descriptions = driver.find_elements(By.CLASS_NAME, "twMonthEventDescription")
                if event_descriptions:
                    print(f"Found {len(event_descriptions)} event descriptions directly")
                    for desc in event_descriptions:
                        try:
                            link_element = desc.find_element(By.TAG_NAME, "a")
                            event_url = link_element.get_attribute("href")
                            event_id = link_element.get_attribute("url.eventid")
                            event_title = link_element.text
                            
                            event_links.append({
                                "title": event_title,
                                "url": event_url,
                                "event_id": event_id
                            })
                        except Exception as e:
                            print(f"Error extracting link: {str(e)}")
                            continue
            except Exception as e:
                print(f"Error finding events directly: {str(e)}")
        
        return event_links
        
    finally:
        # Close the browser
        driver.quit()

def create_session_with_retries():
    """Create a requests session with automatic retries."""
    session = requests.Session()
    
    # Configure automatic retries with backoff
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    # Mount the adapter to both http and https
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set default timeout
    session.timeout = 15
    
    return session

def get_event_description(session, event_info):
    """
    Fetches the event description for a given event using a shared session.
    
    Args:
        session: Requests session with retry configuration
        event_info (dict): Dictionary containing event information.
    
    Returns:
        dict: Updated event info with description.
    """
    event_id = event_info["event_id"]
    url = "https://25livepub.collegenet.com/calendars/25live-woodpec-cal"

    # POST request payload
    payload = {
        "__VIEWSTATE": "/wEPDwULLTEwNTgzNzY1NzBkZDQICa4hMSYrRs4a7jdi+yT15VZN5DU8w0EWlawDPo5a",
        "__VIEWSTATEGENERATOR": "1174A9D5",
        "__EVENTVALIDATION": "/wEdAAIPeOW34H8nx3Ya+gu/JAs/DJWw+FZ24ag06UaD5hLs0Xyi4Le7x6rZnlXPTnb3aKPCeWthpMBAs5uBG5TobT4V"
    }

    # Headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = session.post(f"{url}?eventid={event_id}", headers=headers, data=payload)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            meta_tag = soup.find("meta", {"property": "description"})
            
            if meta_tag and "content" in meta_tag.attrs:
                event_info["description"] = meta_tag["content"]
            else:
                event_info["description"] = "Description not found."
        else:
            event_info["description"] = f"Failed with status code: {response.status_code}"

    except Exception as e:
        event_info["description"] = f"Error occurred: {str(e)}"
    
    return event_info

def process_event_batch(args):
    """Process a batch of events with a shared session."""
    batch_id, event_batch, checkpoint_file = args
    
    # Create a shared session for all requests in this batch
    session = create_session_with_retries()
    
    results = []
    
    # Process each event in the batch with progress bar
    for event in tqdm(event_batch, desc=f"Batch {batch_id}", position=batch_id):
        result = get_event_description(session, event)
        results.append(result)
        
        # Save incremental checkpoint after every 10 events
        if len(results) % 10 == 0:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Final checkpoint save
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def split_into_batches(items, num_batches):
    """Split items into num_batches as evenly as possible."""
    avg_size = len(items) // num_batches
    remainder = len(items) % num_batches
    
    result = []
    start = 0
    
    for i in range(num_batches):
        # Add one extra item to the first 'remainder' batches
        end = start + avg_size + (1 if i < remainder else 0)
        result.append(items[start:end])
        start = end
    
    return result

def process_with_checkpoints(event_links, num_workers=4, checkpoint_dir="checkpoints"):
    """Process events with checkpointing and parallel execution."""
    if not event_links:
        return []
    
    # Create checkpoint directory
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    # Split events into batches for each worker
    batches = split_into_batches(event_links, num_workers)
    
    # Prepare batch arguments with checkpoint files
    batch_args = []
    for i, batch in enumerate(batches):
        checkpoint_file = os.path.join(checkpoint_dir, f"batch_{i}_checkpoint.json")
        batch_args.append((i, batch, checkpoint_file))
    
    # Determine if any checkpoints exist and can be loaded
    checkpoint_exists = False
    for i in range(len(batches)):
        checkpoint_file = os.path.join(checkpoint_dir, f"batch_{i}_checkpoint.json")
        if os.path.exists(checkpoint_file):
            checkpoint_exists = True
            break
        
    # Process batches in parallel
    print(f"Processing {len(event_links)} events in {len(batches)} batches with {num_workers} workers")
    
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all batches
        future_to_batch = {executor.submit(process_event_batch, arg): arg for arg in batch_args}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_batch):
            batch_id = future_to_batch[future][0]
            try:
                batch_results = future.result()
                all_results.extend(batch_results)
                print(f"Completed batch {batch_id} with {len(batch_results)} events")
            except Exception as exc:
                print(f"Batch {batch_id} generated an exception: {exc}")
    
    return all_results

def save_to_csv(event_links, filename="event_links.csv"):
    """Save the extracted event links to a CSV file."""
    if not event_links:
        print("No event links to save.")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ["title", "url", "event_id", "description"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        writer.writeheader()
        for link in event_links:
            writer.writerow(link)
    
    print(f"Saved {len(event_links)} event links to {filename}")

def main():
    # Extract new event links
    url = "https://25livepub.collegenet.com/calendars/25live-woodpec-cal"
    event_links = extract_event_urls(url)
    
    # Save extracted links
    if event_links:
        save_to_csv(event_links, "event_links_no_descriptions.csv")
    
    if event_links:
        print(f"\nProcessing {len(event_links)} events")
        
        # Determine optimal number of workers
        num_workers = 4  # Use 4 cores as requested
        
        # Process event descriptions with checkpointing
        updated_links = process_with_checkpoints(event_links, num_workers)
        
        # Save completed results
        save_to_csv(updated_links)
    else:
        print("No event links were extracted.")

if __name__ == "__main__":
    # Record start time
    start_time = time.time()
    
    main()
    
    # Print execution time
    elapsed_time = time.time() - start_time
    print(f"\nScript completed in {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
