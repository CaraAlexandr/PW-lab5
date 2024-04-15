#!/usr/bin/env python3

import os
import ssl
import pickle
import sys
import socket
import json
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
from pygments import highlight, lexers, formatters

CACHE_FILE = "cache.pkl"

def readCache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    return {}

def writeCache(cache):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)

def makeHttpRequest(host, path, redirectCount=0, maxRedirects=5):
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
        responseLines = responseStr.split("\r\n")
        headers = responseLines[:responseLines.index('')]
        body = '\r\n'.join(responseLines[responseLines.index('')+1:])

        if responseLines[0].startswith("HTTP/1.1 3"):
            for line in headers:
                if line.startswith("Location:"):
                    newLocation = line.split(": ", 1)[1]
                    newLocation = newLocation.strip()
                    newHost = urlparse(newLocation).netloc
                    newPath = urlparse(newLocation).path
                    return makeHttpRequest(newHost, newPath, redirectCount + 1, maxRedirects)

        for line in headers:
            if line.lower().startswith("content-type:") and "application/json" in line.lower():
                json_data = json.loads(body)
                formatted_json = json.dumps(json_data, indent=4)
                colorful_json = highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())
                return colorful_json

        soup = BeautifulSoup(body, 'html.parser')
        return soup, soup.get_text(strip=True)
    except Exception as e:
        return f"Error: {str(e)}"

def parseAndPrintElements(soup):
    if isinstance(soup, str) and soup.strip().startswith('{'):  # Check if the input is a string formatted JSON
        print(soup)  # Print the already formatted and colored JSON
    else:
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'ul', 'li']):
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                print('\n' + element.text)
                print('-' * len(element.text))
            elif element.name == 'p':
                print('\n' + element.text)
            elif element.name == 'a':
                print(f"\nURL: {element.get('href')}")
            elif element.name in ['ul', 'li']:
                if element.name == 'li':
                    print(f"  - {element.text}")
                else:
                    print(element.text)
def searchWithGoogle(searchTerm, cache):
    if searchTerm in cache:
        return cache[searchTerm]
    try:
        host = "www.google.com"
        searchQuery = quote(searchTerm)
        path = f"/search?q={searchQuery}"
        soup, body = makeHttpRequest(host, path)
        if soup:
            links = soup.find_all('a')
            searchResults = []
            for link in links:
                href = link.get('href')
                if href.startswith('/url?q='):
                    url = href.split('/url?q=')[1].split('&')[0]
                    searchResults.append(url)
                    if len(searchResults) >= 10:
                        break
            cache[searchTerm] = searchResults
            writeCache(cache)
            return searchResults
        else:
            return "Error: Failed to fetch search results"
    except Exception as e:
        return f"Error: {str(e)}"

def printHelp():
    print("Usage:")
    print("  go2web -u <URL>            Make an HTTP request to the specified <URL> and print the response")
    print("  go2web -s <search-term>    Make an HTTP request to search the <search-term> using Google and print top 10 results")
    print("  go2web -h                  List available commands")

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
        response = makeHttpRequest(host, path)
        if isinstance(response, tuple):
            soup, _ = response
            parseAndPrintElements(soup)  # Call the parsing function here
        else:
            print(response)
    elif sys.argv[1] == '-s':
        search_term = ' '.join(sys.argv[2:])
        search_results = searchWithGoogle(search_term, cache)
        print(search_results)
        if isinstance(search_results, list):
            for i, url in enumerate(search_results, start=1):
                print(f"{i}. {url}")
        else:
            print(search_results)
    elif sys.argv[1] == '-h':
        printHelp()
    else:
        print("Invalid option. Use '-h' for help.")

if __name__ == "__main__":
    main()