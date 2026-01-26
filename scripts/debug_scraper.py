
import requests
from bs4 import BeautifulSoup

def debug_scrape(query):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    url = f"https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"
    
    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Length: {len(response.text)}")
    
    with open('debug_ebay_output.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    s_items = soup.select('.s-item__wrapper')
    s_cards = soup.select('.s-card')
    
    print(f"Found .s-item__wrapper count: {len(s_items)}")
    print(f"Found .s-card count: {len(s_cards)}")
    
    title_items = soup.select('.s-item__title')
    title_cards = soup.select('.s-card__title')
    
    print(f"Found .s-item__title count: {len(title_items)}")
    print(f"Found .s-card__title count: {len(title_cards)}")

if __name__ == "__main__":
    debug_scrape("vintage camera")
