# analyzer/scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time, requests, re
import urllib.parse
import sys # For better error handling/logging to stderr

def scrape_businesses(city, keyword):
    print("--- Starting scrape_businesses function ---", file=sys.stderr) # Log to stderr
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # Keep headless for Streamlit deployment, but comment out for local debugging
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized') # Maximize window to ensure elements are visible
    options.add_argument('--disable-gpu') # Often helps in headless mode on some systems
    options.add_argument('--window-size=1920,1080') # Set a specific window size
    print("WebDriver options set.", file=sys.stderr)

    try:
        # Use a more recent ChromeDriverManager version or ensure it's up-to-date
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        print("WebDriver initialized.", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Could not initialize WebDriver. Is Chrome installed? Driver path correct? Error: {e}", file=sys.stderr)
        return []

    query = f"{keyword} in {city}"
    encoded_query = urllib.parse.quote_plus(query)
    # Using a direct Google Maps URL for search
    url = f"https://www.google.com/maps/search/{encoded_query}" # Changed to standard Google Maps search URL pattern
    print(f"Navigating to URL: {url}", file=sys.stderr)
    driver.get(url)
    print("Page loaded. Waiting for initial elements...", file=sys.stderr)

    try:
        # Wait for the main results list to appear
        WebDriverWait(driver, 30).until( # Increased timeout
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.Nv2PK"))
        )
        print("Initial business cards (div.Nv2PK) found.", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Initial business cards not found within timeout. Page might not have loaded correctly or selectors are wrong. Error: {e}", file=sys.stderr)
        # Try to save a screenshot for debugging if it fails here
        driver.save_screenshot("error_initial_load.png")
        driver.quit()
        return []

    time.sleep(5) # Increased sleep after initial load
    print("Initial sleep done. Starting business processing loop.", file=sys.stderr)

    businesses = []
    seen_names = set()
    index = 0
    max_scroll_attempts = 10 # Increased max scrolls

    # Find the scrollable results panel
    scrollable_div = None
    try:
        # This selector is crucial. 'div[aria-label^="Results for"]' is good.
        # Sometimes it's a div with role="main" and a scrollbar.
        scrollable_div = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[aria-label^="Results for"]'))
        )
        print("Scrollable results div found.", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Could not find the main scrollable results div with aria-label. Falling back to an alternative. Error: {e}", file=sys.stderr)
        # Fallback to a common scrollable div or body if specific aria-label isn't found
        try:
            scrollable_div = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="main"][tabindex="-1"]')) # Another common selector
            )
            print("Found fallback scrollable div.", file=sys.stderr)
        except:
            print("Could not find common scrollable divs. Will try to scroll document body.", file=sys.stderr)
            scrollable_div = driver.find_element(By.TAG_NAME, 'body') # Fallback to scrolling body


    while len(businesses) < 5: # Aim for 10 businesses
        print(f"\nLoop iteration: {len(businesses)} businesses found so far. Processing card index: {index}", file=sys.stderr)
        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
        print(f"Currently found {len(cards)} cards on page.", file=sys.stderr)

        # If we've processed all currently loaded cards, try to scroll
        if index >= len(cards):
            if max_scroll_attempts <= 0:
                print("Max scroll attempts reached. Ending scrape.", file=sys.stderr)
                break
            
            print(f"No more visible cards to process. Attempting to scroll. Scrolls left: {max_scroll_attempts}", file=sys.stderr)
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(5) # Increased wait time after scroll
            
            new_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
            print(f"After scroll, found {len(new_cards)} cards.", file=sys.stderr)
            
            # If no new cards loaded after scroll, break
            if len(new_cards) == len(cards):
                print("No new cards loaded after scrolling. Ending scrape.", file=sys.stderr)
                break
            
            cards = new_cards # Update cards list
            max_scroll_attempts -= 1
            
            # Reset index to find new unseen cards. Start from 0 to ensure all new cards are checked.
            index = 0
            found_next_card_after_scroll = False
            for i in range(len(cards)):
                try:
                    # Attempt to get name from card preview (qBF1Pd is common for title in card)
                    name_elem_preview = cards[i].find_element(By.CSS_SELECTOR, "div.qBF1Pd").text
                    if name_elem_preview and name_elem_preview not in seen_names: # Check for non-empty name
                        index = i
                        found_next_card_after_scroll = True
                        break
                except Exception as e:
                    # print(f"Warning: Could not get preview name for card {i}: {e}", file=sys.stderr)
                    pass # Ignore if preview name isn't immediately available

            if not found_next_card_after_scroll:
                print("No new unseen cards found after scroll. Ending scrape.", file=sys.stderr)
                break


        card = cards[index]
        # Get the name from the card preview before clicking, for better logging
        card_preview_name = "N/A"
        try:
            card_preview_name = card.find_element(By.CSS_SELECTOR, "div.qBF1Pd").text
        except:
            pass
        print(f"Processing card {index}: '{card_preview_name}'", file=sys.stderr)
        
        driver.execute_script("arguments[0].scrollIntoView();", card)

        try:
            print(f"Attempting to click card {index} ({card_preview_name})...", file=sys.stderr)
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(card))
            card.click()
            print(f"Card {index} ({card_preview_name}) clicked successfully.", file=sys.stderr)
        except Exception as e:
            print(f"ERROR clicking card {index} ({card_preview_name}) directly: {e}. Trying JS click...", file=sys.stderr)
            try:
                driver.execute_script("arguments[0].click();", card) # Fallback to JavaScript click
                print(f"Card {index} ({card_preview_name}) clicked via JS.", file=sys.stderr)
            except Exception as js_e:
                print(f"FATAL: Could not click card {index} ({card_preview_name}) even with JS: {js_e}. Skipping this card.", file=sys.stderr)
                index += 1
                continue # Skip to next card if click fails

        time.sleep(3) # Give more time for the details pane to load
        soup = BeautifulSoup(driver.page_source, "html.parser")
        print("Page source parsed with BeautifulSoup for details.", file=sys.stderr)

        # Extract business name from the detail pane
        name_elem = soup.select_one("h1.DUwDvf.lfPIob") # This is a common class for the primary business name on details page.
        if not name_elem:
            name_elem = soup.select_one("h1") # Fallback to generic h1
        if not name_elem: # Another common selector if the above fails
            name_elem = soup.find("div", class_="lMbqxd")
            if name_elem:
                name_elem = name_elem.find("h1")
        
        name = name_elem.get_text(strip=True) if name_elem else "N/A"
        print(f"Extracted Detail Name: {name}", file=sys.stderr)

        if name == "N/A" or name in seen_names:
            print(f"Skipping (N/A name or already seen): {name}", file=sys.stderr)
            index += 1
            # Go back immediately if skipping to avoid getting stuck on a detail page
            try:
                back_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Back']"))
                )
                back_button.click()
                time.sleep(2)
            except:
                driver.back()
                time.sleep(3)
            continue
        seen_names.add(name)

        phone = None
        phone_elem = soup.find("button", {"data-item-id": re.compile(r"phone")})
        if phone_elem:
            raw_phone = phone_elem.get_text(strip=True)
            phone = re.sub(r"[^\d+ -]", "", raw_phone)
        print(f"Extracted Phone: {phone}", file=sys.stderr)

        website = None
        # Attempt to find the website link more robustly
        website_elem = soup.find("a", {"data-tooltip-id": "tooltip_aria_label_website"})
        if not website_elem:
            website_elem = soup.find("a", {"aria-label": re.compile(r"website|Visit website", re.IGNORECASE), "target": "_blank"})
        if not website_elem:
            website_elem = soup.find("a", class_=lambda x: x and ("website" in x.lower() or "AB7Lab" in x))
        if not website_elem: # General link search for "website" text
            for a_tag in soup.find_all('a', href=True):
                if 'website' in a_tag.get_text(strip=True).lower():
                    website_elem = a_tag
                    break
        
        if website_elem:
            href = website_elem.get("href", "")
            # More comprehensive filter for valid external websites
            if href.startswith("http") and not any(f"google.com/{s}" in href for s in ["maps", "place", "search", "business"]) and "gstatic.com" not in href:
                if not any(social_site in href for social_site in ["facebook.com", "linkedin.com", "twitter.com", "instagram.com", "youtube.com", "tripadvisor."]):
                    website = href
        print(f"Extracted Website: {website}", file=sys.stderr)
        
        linkedin = find_linkedin_profile(name, city)
        print(f"Extracted LinkedIn: {linkedin}", file=sys.stderr)

        businesses.append({
            "name": name,
            "contact": phone or "N/A",
            "website": website or "Not found",
            "linkedin": linkedin or "Not found"
        })

        # Print to standard output as well, for Streamlit to potentially capture if not too much.
        # Streamlit's st.spinner will show basic console output.
        print(f"[{len(businesses)}] {name} | {phone} | {website} | {linkedin}", file=sys.stdout)
        
        # --- CRUCIAL: Go back to the search results page ---
        try:
            back_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Back']")) # Google Maps back button
            )
            back_button.click()
            print("Clicked back button to return to results.", file=sys.stderr)
            time.sleep(2) # Give time to load back to results
        except Exception as e:
            print(f"WARNING: Could not find or click back button after processing {name}. Might be stuck on detail page. Error: {e}. Trying driver.back()...", file=sys.stderr)
            driver.back() # Fallback
            time.sleep(3)


        index += 1

    driver.quit()
    print(f"--- Scraping finished. Total businesses scraped: {len(businesses)} ---", file=sys.stderr)
    return businesses


def find_linkedin_profile(business_name, city):
    print(f"Searching LinkedIn for: {business_name} in {city}", file=sys.stderr)
    time.sleep(2) # Increased sleep for Google search
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    encoded_query = urllib.parse.quote_plus(f"{business_name} {city} site:linkedin.com")
    url = f"https://www.google.com/search?q={encoded_query}"

    try:
        resp = requests.get(url, headers=headers, timeout=15) # Increased timeout for requests
        resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        # Check for Google's anti-bot pages (common phrases)
        if "unusual traffic" in resp.text.lower() or "captcha" in resp.text.lower() or "prove you're not a robot" in resp.text.lower():
            print("[WARNING] Google is blocking LinkedIn searches (unusual traffic/captcha detected).", file=sys.stderr)
            return "Blocked by Google" # Return a specific message
        
        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "linkedin.com/in/" in href or "linkedin.com/company/" in href:
                # Clean the URL to remove Google's redirection parameters
                if href.startswith("/url?q="):
                    clean_href = href.split("&sa=")[0].replace("/url?q=", "")
                    print(f"Found LinkedIn: {clean_href}", file=sys.stderr)
                    return clean_href
                else:
                    print(f"Found LinkedIn: {href}", file=sys.stderr)
                    return href
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] LinkedIn search HTTP request failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] LinkedIn search parsing failed: {e}", file=sys.stderr)

    return "Not found" # Return "Not found" if nothing is identified