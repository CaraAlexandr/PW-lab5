#!/usr/bin/env python3

import os
import ssl
import pickle
import sys
import socket
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
import json
import logging

CACHE_FILE = "cache.pkl"

def readCache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    return {}

def writeCache(cache):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)

def prettyPrintJson(data):
    print(json.dumps(data, indent=4, ensure_ascii=False))

def makeHttpRequest(host, path, redirectCount=0, maxRedirects=5):
    cache = readCache()
    cache_key = f"{host}_{path}"

    if cache_key in cache:
        logging.info("Using cached data")
        prettyPrintJson(cache[cache_key])
        return cache[cache_key]

    try:
        context = ssl.create_default_context()
        with context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=host) as s:
            s.connect((host, 443))
            request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            s.sendall(request.encode())
            response = b''
            while True:
                data = s.recv(1024)
                if not data:
                    break
                response += data
        responseStr = response.decode("utf-8", errors="ignore")
        responseLines = responseStr.split("\r\n\r\n", 1)

        headers = responseLines[0].split("\r\n")
        body = responseLines[1] if len(responseLines) > 1 else ""

        # Handling redirects
        if "HTTP/1.1 3" in headers[0] and redirectCount < maxRedirects:
            for line in headers:
                if line.startswith("Location:"):
                    newLocation = line.split(": ", 1)[1]
                    newUrl = urlparse(newLocation)
                    newHost = newUrl.netloc
                    newPath = newUrl.path
                    if not newHost:
                        newHost = host
                    if not newPath:
                        newPath = '/'
                    return makeHttpRequest(newHost, newPath, redirectCount + 1, maxRedirects)

        contentType = next((line.split(": ", 1)[1].strip() for line in headers if line.lower().startswith("content-type:")), "")

        if "application/json" in contentType:
            jsonData = json.loads(body)
            prettyPrintJson(jsonData)
            cache[cache_key] = jsonData
            writeCache(cache)
            return jsonData
        else:
            soup = BeautifulSoup(body, 'html.parser')
            links = [a['href'] for a in soup.find_all('a', href=True) if 'http' in a['href']]

            # Saving only essential data
            essential_data = {
                'links': links,
                'text': soup.get_text(strip=True)[:100]  # Sample of response text for brevity
            }

            cache[cache_key] = essential_data
            writeCache(cache)
            prettyPrintJson(essential_data)
            return essential_data
    except Exception as e:
        logging.error("Failed to make HTTP request", exc_info=True)
        return None


def searchWithGoogle(searchTerm, cache):
    cache_key = f"search_{searchTerm}"
    if cache_key in cache:
        logging.info("Using cached data for Google search")
        prettyPrintJson(cache[cache_key])
        return cache[cache_key]

    try:
        host = "www.google.com"
        searchQuery = quote(searchTerm)
        path = f"/search?q={searchQuery}"
        response = makeHttpRequest(host, path)

        if response:
            # Assume response is the essential_data dictionary
            searchResults = response['links'][:10]  # Limit to top 10 results

            cache[cache_key] = searchResults
            writeCache(cache)
            prettyPrintJson(searchResults)
            return searchResults
        else:
            return "Error: Failed to fetch search results"
    except Exception as e:
        logging.error(f"Failed to search for {searchTerm}", exc_info=True)
        return f"Error: {str(e)}"
def parseAndPrintElements(result):
    if result:
        soup, _ = result
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'ul', 'li']):
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                print('\n' + element.text)
                print('-' * len(element.text))  # Underline for headers
            elif element.name == 'p':
                print('\n' + element.text)
            elif element.name == 'a':
                print(f"\nURL: {element.get('href')}")
            elif element.name in ['ul', 'li']:
                if element.name == 'li':
                    print(f"  - {element.text}")
                else:
                    print(element.text)
    else:
        print("Error retrieving or parsing the webpage.")

def printHelp():
    print("Usage:")
    print("  search -u <URL>            Make an HTTP request to the specified <URL> and print the response")
    print("  search -s <search-term>    Make an HTTP request to search the <search-term> using Google and print top 10 results")
    print("  search -h                  List available commands")


def main():
    cache = readCache()
    if len(sys.argv) < 3:
        printHelp()
        return

    if sys.argv[1] == '-u':
        url = sys.argv[2]
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        path = parsed_url.path if parsed_url.path else '/'
        makeHttpRequest(host, path)
    elif sys.argv[1] == '-s':
        search_term = ' '.join(sys.argv[2:])
        searchWithGoogle(search_term, cache)
    elif sys.argv[1] == '-h':
        printHelp()
    else:
        print("Invalid option. Use '-h' for help.")

if __name__ == "__main__":
    main()