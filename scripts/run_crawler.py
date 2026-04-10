from app import create_app
from app.crawlers.mee_crawler import MEEPublicReportCrawler


app = create_app()


with app.app_context():
    result = MEEPublicReportCrawler().run()
    print(result)
