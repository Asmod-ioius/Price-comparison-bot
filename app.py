from flask import Flask, render_template, jsonify, request
from working_scraper import WorkingPriceComparisonScraper

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    product = data.get('product', '').strip()
    include_secondhand = data.get('secondhand', False)
    include_industrial = data.get('industrial', False)

    if not product:
        return jsonify({'error': 'Product name required'}), 400

    try:
        scraper = WorkingPriceComparisonScraper()
        results = scraper.scrape_prices(product, include_secondhand, include_industrial)
        
        if not results:
            return jsonify([{
                "website": "Info",
                "title": "No results found - websites may be blocking requests",
                "price_display": "Try different search terms",
                "link": "#"
            }])
            
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
