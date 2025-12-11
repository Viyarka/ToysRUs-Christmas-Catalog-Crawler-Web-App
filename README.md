# ToysRUs Toy Catalog Crawler & Flask Web App

This project is a tool that scrapes toy data from the ToysRUs website using **regular expressions**, stores the results in a **SQLite database**, and displays them through a clean **Flask web interface** with filters.  
Optionally, it includes an **AI-based recommender** that suggests toys similar to a user description (requires OpenAI API key).

---

## Features
- Web crawler that extracts:
  - Name, price, brand, category, age range, product URL, image URL  
- Regex-based HTML parsing (no external scrapers needed)
- SQLite database for persistent storage and filtering
- Flask web interface with category, brand, age, and price filters
- Optional AI recommender using OpenAI GPT models

---

## How to Use
1) Run the crawler (build the database)
python crawler.py

This creates toysrus.db with all scraped toys.

2) Start the Flask web server
python app.py

3) Open in your browser: (ctrl+click) link provided in your terminal.

---

## Requirements
Install dependencies:

```bash
pip install flask requests python-dotenv openai
