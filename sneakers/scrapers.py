import datetime
import json
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from sneakers.exceptions import BrandDoesNotExist
from sneakers.helpers import download_images_by_brand, download_images_by_date


class SneakerScraper:
    BASE_URL: str = "https://solecollector.com"

    def __init__(self):
        self.brands: Dict[str, str] = self.scrap_brands()
        self.sneakers: List = []

    def parse_url(self, url) -> str:
        return self.BASE_URL + url

    def scrap_brands(self) -> Dict:
        """Gets the names of the brands and their links"""
        response = requests.get(self.parse_url("/sd/sole-search-sneaker-database/"))
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="brand-banner brand-item")
        brands: Dict[str, str] = {}
        for brand in items:
            name: str = brand.find("img")["alt"]
            brands[name] = brand.find("a")["href"]
        return brands

    def get_sneakers_by_brand(
        self, brand_id: str, get: int = 100, skip: int = 0
    ) -> requests.Response:
        """
        :param brand_id: brand identifier
        :param get: quantity of items to obtain
        :param skip: items to skip
        """
        api_url = self.parse_url("/api/sneaker-api/releases?")
        url = f"{api_url}asc=0&get={get}&parent_id={brand_id}&skip={skip}&start=1623258117.75"
        return requests.get(url)

    def get_sneakers_by_date(self, year: str, month: str) -> requests.Response:
        url = self.parse_url(
            f"/sneaker-release-dates/all-release-dates/{year}/{month}/"
        )
        return requests.get(url=url)

    @staticmethod
    def get_brand_id(url: str) -> str:
        """The brand id is obtained from the url."""
        return url.split("/")[-3]

    @staticmethod
    def get_original_image(url: str) -> str:
        """Replace the url parameters that modify the image."""
        return url.replace("h_200,", "").replace("w_350", "w_1200")

    def scrap_sneakers_by_brand(
        self, name: str, start: int = 0, limit: int = 0
    ) -> List:
        """
        :param name: brand name
        :param start: number to start getting data on
        :param limit: number of desired sneakers
        """
        if name in self.brands:
            brand_url = self.brands[name]
            brand_id = self.get_brand_id(brand_url)
            is_ok, data, skip = True, True, start

            while (
                is_ok and data and (limit and len(self.sneakers) < limit) or not limit
            ):
                response = self.get_sneakers_by_brand(brand_id=brand_id, skip=skip)
                is_ok, data = response.ok, json.loads(response.text)
                if is_ok:
                    for sneaker in data:
                        if (limit and len(self.sneakers) < limit) or not limit:
                            self.sneakers.append(
                                {
                                    "name": sneaker["name"],
                                    "image": sneaker["hero_image_url"],
                                }
                            )
                skip += 100
            download_images_by_brand(brand=name, sneakers=self.sneakers)
        else:
            raise BrandDoesNotExist(
                "The specified brand name does not exist, please try Nike, Adidas, Reebok, "
                "Puma, Jordan, Converse, Vans, New Balance or ASICS."
            )
        return self.sneakers

    def scrap_sneakers_by_dates(self, after: str, before: Optional[str] = "") -> List:
        after_date = datetime.datetime.strptime(after, "%d/%m/%Y")
        before_date = (
            datetime.datetime.strptime(before, "%d/%m/%Y")
            if before
            else datetime.datetime.today()
        )
        while after_date <= before_date:
            year, month = after_date.strftime("%Y"), after_date.strftime("%m")
            response = self.get_sneakers_by_date(year=year, month=month)
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.find_all("div", class_="sneaker-release-item")
            for sneaker in items:
                self.sneakers.append(
                    {
                        "name": sneaker.find("img")["alt"],
                        "image": self.get_original_image(sneaker.find("img")["src"]),
                    }
                )
            after_date += relativedelta(months=1)
            download_images_by_date(year=year, sneakers=self.sneakers)
        return self.sneakers
