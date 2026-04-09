from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..config import Config
from ..extensions import db
from ..models import CrawlArtifact, CrawlTaskLog


class MEEPublicReportCrawler:
    source_name = "生态环境部"
    target_url = "https://www.mee.gov.cn/hjzl/dqhj/cskqzlzkyb/"

    def __init__(self, timeout=None):
        self.timeout = timeout or Config.CRAWLER_TIMEOUT

    def fetch_monthly_reports(self, limit=8):
        response = requests.get(
            self.target_url,
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 AirQualitySystem/1.0"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        records = []

        for link in soup.select("a"):
            title = link.get_text(" ", strip=True)
            href = link.get("href")
            if not title or not href:
                continue
            if "空气质量" not in title and "月报" not in title:
                continue
            article_url = urljoin(self.target_url, href)
            records.append(
                {
                    "source_name": self.source_name,
                    "category": "月报",
                    "title": title,
                    "article_url": article_url,
                    "published_at": "",
                }
            )
            if len(records) >= limit:
                break
        return records

    def run(self):
        run_at = datetime.now()
        try:
            records = self.fetch_monthly_reports()
            for item in records:
                exists = CrawlArtifact.query.filter_by(
                    title=item["title"], article_url=item["article_url"]
                ).first()
                if not exists:
                    db.session.add(
                        CrawlArtifact(
                            source_name=item["source_name"],
                            category=item["category"],
                            title=item["title"],
                            article_url=item["article_url"],
                            published_at=item["published_at"],
                            crawled_at=run_at,
                        )
                    )

            db.session.add(
                CrawlTaskLog(
                    task_name="城市空气质量月报采集",
                    source_name=self.source_name,
                    target_url=self.target_url,
                    status="success",
                    records_count=len(records),
                    message="成功抓取公开月报列表。",
                    run_at=run_at,
                )
            )
            db.session.commit()
            return {"status": "success", "records_count": len(records), "run_at": run_at.strftime("%Y-%m-%d %H:%M")}
        except Exception as exc:
            db.session.add(
                CrawlTaskLog(
                    task_name="城市空气质量月报采集",
                    source_name=self.source_name,
                    target_url=self.target_url,
                    status="failed",
                    records_count=0,
                    message=str(exc)[:250],
                    run_at=run_at,
                )
            )
            db.session.commit()
            return {"status": "failed", "records_count": 0, "run_at": run_at.strftime("%Y-%m-%d %H:%M"), "message": str(exc)}
