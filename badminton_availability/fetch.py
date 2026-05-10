import concurrent.futures
import csv
import json
import os
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from tqdm import tqdm
from urllib3.util.retry import Retry

from badminton_availability.config import (
    CHECKPOINT_DIR,
    EVENT_LINKS_FILE,
    EVENT_LINKS_NO_DESCRIPTIONS_FILE,
    NUM_WORKERS,
    SOURCE_URL,
)


def extract_event_urls(url):
    """Extract all event URLs from the 25Live calendar, handling iframe content."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)

    event_links = []

    try:
        print(f"Navigating to {url}")
        driver.get(url)

        print("Waiting for page to load...")
        time.sleep(8)

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"Found {len(iframes)} iframes")

        if len(iframes) >= 4:
            try:
                print("Switching to the target iframe (index 3)")
                driver.switch_to.frame(iframes[3])
                time.sleep(5)

                event_descriptions = driver.find_elements(
                    By.CLASS_NAME,
                    "twMonthEventDescription",
                )
                print(f"Found {len(event_descriptions)} event descriptions")

                for desc in event_descriptions:
                    try:
                        link_element = desc.find_element(By.TAG_NAME, "a")
                        event_links.append(
                            {
                                "title": link_element.text,
                                "url": link_element.get_attribute("href"),
                                "event_id": link_element.get_attribute("url.eventid"),
                            }
                        )
                    except Exception as e:
                        print(f"Error extracting link: {str(e)}")
                        continue
            except Exception as e:
                print(f"Error processing iframe: {str(e)}")
        else:
            print("Not enough iframes found - trying to find events directly")
            try:
                event_descriptions = driver.find_elements(
                    By.CLASS_NAME,
                    "twMonthEventDescription",
                )
                if event_descriptions:
                    print(f"Found {len(event_descriptions)} event descriptions directly")
                    for desc in event_descriptions:
                        try:
                            link_element = desc.find_element(By.TAG_NAME, "a")
                            event_links.append(
                                {
                                    "title": link_element.text,
                                    "url": link_element.get_attribute("href"),
                                    "event_id": link_element.get_attribute("url.eventid"),
                                }
                            )
                        except Exception as e:
                            print(f"Error extracting link: {str(e)}")
                            continue
            except Exception as e:
                print(f"Error finding events directly: {str(e)}")

        return event_links
    finally:
        driver.quit()


def create_session_with_retries():
    """Create a requests session with automatic retries."""
    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )

    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = 15

    return session


def get_event_description(session, event_info):
    """Fetch the event description for a given event using a shared session."""
    event_id = event_info["event_id"]

    payload = {
        "__VIEWSTATE": "/wEPDwULLTEwNTgzNzY1NzBkZDQICa4hMSYrRs4a7jdi+yT15VZN5DU8w0EWlawDPo5a",
        "__VIEWSTATEGENERATOR": "1174A9D5",
        "__EVENTVALIDATION": "/wEdAAIPeOW34H8nx3Ya+gu/JAs/DJWw+FZ24ag06UaD5hLs0Xyi4Le7x6rZnlXPTnb3aKPCeWthpMBAs5uBG5TobT4V",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }

    try:
        response = session.post(f"{SOURCE_URL}?eventid={event_id}", headers=headers, data=payload)

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
    session = create_session_with_retries()
    results = []

    for event in tqdm(event_batch, desc=f"Batch {batch_id}", position=batch_id):
        result = get_event_description(session, event)
        results.append(result)

        if len(results) % 10 == 0:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def split_into_batches(items, num_batches):
    """Split items into num_batches as evenly as possible."""
    avg_size = len(items) // num_batches
    remainder = len(items) % num_batches

    result = []
    start = 0

    for i in range(num_batches):
        end = start + avg_size + (1 if i < remainder else 0)
        result.append(items[start:end])
        start = end

    return result


def process_with_checkpoints(event_links, num_workers=NUM_WORKERS, checkpoint_dir=CHECKPOINT_DIR):
    """Process events with checkpointing and parallel execution."""
    if not event_links:
        return []

    os.makedirs(checkpoint_dir, exist_ok=True)
    batches = split_into_batches(event_links, num_workers)

    batch_args = []
    for i, batch in enumerate(batches):
        checkpoint_file = os.path.join(checkpoint_dir, f"batch_{i}_checkpoint.json")
        batch_args.append((i, batch, checkpoint_file))

    print(f"Processing {len(event_links)} events in {len(batches)} batches with {num_workers} workers")

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_batch = {executor.submit(process_event_batch, arg): arg for arg in batch_args}

        for future in concurrent.futures.as_completed(future_to_batch):
            batch_id = future_to_batch[future][0]
            try:
                batch_results = future.result()
                all_results.extend(batch_results)
                print(f"Completed batch {batch_id} with {len(batch_results)} events")
            except Exception as exc:
                print(f"Batch {batch_id} generated an exception: {exc}")

    return all_results


def save_to_csv(event_links, filename):
    """Save the extracted event links to a CSV file."""
    if not event_links:
        print("No event links to save.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as file:
        fieldnames = ["title", "url", "event_id", "description"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        for link in event_links:
            writer.writerow(link)

    print(f"Saved {len(event_links)} event links to {filename}")


def main():
    start_time = time.time()
    event_links = extract_event_urls(SOURCE_URL)

    if event_links:
        save_to_csv(event_links, EVENT_LINKS_NO_DESCRIPTIONS_FILE)
        print(f"\nProcessing {len(event_links)} events")
        updated_links = process_with_checkpoints(event_links, NUM_WORKERS)
        save_to_csv(updated_links, EVENT_LINKS_FILE)
    else:
        print("No event links were extracted.")

    elapsed_time = time.time() - start_time
    print(f"\nScript completed in {elapsed_time:.2f} seconds ({elapsed_time / 60:.2f} minutes)")

