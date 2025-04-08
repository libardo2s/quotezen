from sqlalchemy import Column, Integer, String, Float
from database import db


class City(db.Model):
    __tablename__ = 'cities'

    id = Column(Integer, primary_key=True, autoincrement=True)

    country_name = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    postal_type = Column(String(10), nullable=True)
    city_name = Column(String(100), nullable=False)
    city_type = Column(String(10), nullable=True)
    county_name = Column(String(100), nullable=True)
    county_fips = Column(String(10), nullable=True)
    province_name = Column(String(100), nullable=True)
    province_abbr = Column(String(10), nullable=True)
    state_fips = Column(String(10), nullable=True)
    msa_code = Column(String(10), nullable=True)
    area_code = Column(String(20), nullable=True)
    time_zone = Column(String(50), nullable=True)
    utc = Column(String(10), nullable=True)
    dst = Column(String(5), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    def __repr__(self):
        return f"<City {self.city_name}, {self.province_abbr} ({self.postal_code})>"