# Lovable-cloner

A comprehensive website scraper that extracts HTML, CSS, JavaScript, and other resources from websites while maintaining functional navigation.

## Features

- Extracts complete websites including subpages
- Downloads and processes CSS, JavaScript, and image resources
- Fixes relative links and navigation paths
- Creates supporting files like sitemap.xml and robots.txt
- Handles button functionality with JavaScript fixes
- Creates a ZIP archive of the extracted site

## Requirements

- Python 3.6+
- Selenium WebDriver
- BeautifulSoup4
- Requests

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python website_scraper_completo.py [URL] [OPTIONS]
```

### Options

- `--output`, `-o`: Directory to save extracted files (default: "extracted_site")
- `--max-pages`, `-m`: Maximum number of pages to extract (default: 20)
- `--include-subdomains`, `-s`: Include subdomains in scraping
- `--create-zip`, `-z`: Create ZIP archive of extracted site

### Example

```bash
python website_scraper_completo.py https://example.com --output my_site --max-pages 50 --include-subdomains --create-zip
```

## How It Works

1. The scraper starts with the base URL and extracts all content
2. It follows links within the same domain to extract subpages
3. All resources (CSS, JS, images, fonts) are downloaded and saved
4. Links and references are updated to work locally
5. Additional files are created for better functionality
6. The entire site is packaged as a ZIP archive

## License

MIT
