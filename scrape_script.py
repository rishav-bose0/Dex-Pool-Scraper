from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import time
import csv

import constants

PAGE_THRESHOLD = 5


def scrape_pools(network):
    pg_no = 1
    data_list = {}
    token_count = 0
    token_address = {}

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--lang=en_US")
    chrome_options.add_argument("--window-size=1200,842")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36")

    exception_count = 0
    while pg_no <= PAGE_THRESHOLD:
        print(f"For Page {pg_no}")
        time.sleep(1)
        try:
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

            url = constants.GECKO_BASE_URL + f"{network}/pools?networks={network}&liquidity%5Bgte%5D=40000&pool_creation_hours_ago%5Bgte%5D=1104&page={pg_no}"
            driver.get(url)
            driver.implicitly_wait(13)

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr.group.text-sm.text-gray-300"))
            )
        except Exception as e:
            print(f"Error occured in selenium {e} for pg {pg_no}. Skipping this page")
            if exception_count == 0:
                exception_count += 1
            else:
                pg_no += 1
            continue

        # Scroll the page in increments to load all dynamic content
        last_height = driver.get_window_size()["height"]
        step = 0
        exceed_times = 0
        # Reset exception.
        exception_count = 0

        def convert_to_int(value_str):
            value_str = value_str[1:]
            if 'K' in value_str:
                return int(float(value_str.replace('K', '')) * 1000)
            elif 'M' in value_str:
                return int(float(value_str.replace('M', '')) * 1000000)
            elif 'B' in value_str:
                return int(float(value_str.replace('B', '')) * 1000000000)
            else:
                return int(value_str.replace('$', '').replace(',', ''))

        while True:
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Find all <tr> tags
            tr_tags = soup.find_all('tr', class_='group text-sm text-gray-300')

            # Print the content of each <tr> tag (or you can process it as needed)
            for tr in tr_tags:
                # Extract the href value
                a_tag = tr.find('a', href=True, title=True)
                href = a_tag['href'] if a_tag else None
                pool_link = f"https://www.geckoterminal.com/{href}"
                if href is not None:
                    href = href.removeprefix(f"/{network}/pools/")
                symbol = a_tag['title']
                base_token = symbol.split('/')[0]

                # Extract the monetary values
                tds = tr.find_all('td',
                                  class_='bg-black px-4 py-1 font-normal transition-all ease-in-out group-hover:bg-gray-900 whitespace-nowrap border-b border-gray-800/80 first:border-l last:border-r h-[3.375rem] md:py-[0.3125rem] xl:h-[2.8125rem] text-right tabular-nums')
                if not tds:
                    tds = tr.find_all('td',
                                      class_='bg-black px-4 py-1 font-normal transition-all ease-in-out group-hover:bg-gray-900 whitespace-nowrap border-b border-gray-800/80 first:border-l last:border-r first:rounded-bl last:rounded-br h-[3.375rem] md:py-[0.3125rem] xl:h-[2.8125rem] text-right tabular-nums')

                if len(tds) >= 3:
                    try:
                        liquidity_usd = convert_to_int(tds[-2].text.strip())
                    except Exception as e:
                        print(f"Error occured {e} for {symbol}")
                        continue
                    if liquidity_usd < 40000:
                        continue
                else:
                    liquidity_usd = None
                if href is None or liquidity_usd is None:
                    print(f"ERROR {symbol} {href} {liquidity_usd}")
                    continue
                # Print or store the extracted values
                if href and liquidity_usd is not None:
                    if data_list.get(base_token) is None:
                        data_list[base_token] = {
                            "network": f"{network}",
                            "base_token": base_token,
                            "pool_link": pool_link,
                            "pool_name": symbol,
                            "pool_address": href,
                            constants.LIQUIDITY_USD: liquidity_usd
                        }
                    elif data_list.get(base_token).get("liquidity_in_usd") < liquidity_usd:
                        data_list[base_token]["pool_address"] = href
                        data_list[base_token][constants.LIQUIDITY_USD] = liquidity_usd

                    if token_address.get(href) is None:
                        token_count += 1
                        token_address[href] = 1

            driver.execute_script("window.scrollBy(0, 500);")
            step += 200
            # Wait for new content to load
            time.sleep(1)
            if step >= last_height:
                if exceed_times == 2:
                    break
                exceed_times += 1

        driver.quit()
        pg_no += 1

    print(f"Total tokens {token_count}")
    write_to_file(network, data_list)
    return data_list


def write_to_file(network, data_info):
    # Write the data to a CSV file
    csv_file = f"{network}_pool_data.csv"
    csv_columns = ["network", "base_token", "pool_name", "pool_link", "pool_address", "liquidity_in_usd"]

    try:
        with open(csv_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in data_info.values():
                writer.writerow(data)
    except IOError:
        print("I/O error")

    print(f"Data has been written to {csv_file}")


print("Starting")
pools_for_trade_bsc = scrape_pools(constants.BNB_CHAIN)
# Add 1minute gap.
time.sleep(61)
pools_for_trade_arb = scrape_pools(constants.ARBITRUM)
