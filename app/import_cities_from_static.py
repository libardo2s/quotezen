import csv
import os
from flask import Flask
from app.config import Config
from app.database import db
from app.models.city import City  # adjust this import if needed

# Init app
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def import_cities():
    csv_path = os.path.join(app.root_path, 'static', 'address_info.csv')
    with app.app_context():
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            cities = []

            for row in reader:
                city = City(
                    country_name=row['CountryName'],
                    postal_code=row['PostalCode'],
                    postal_type=row.get('PostalType'),
                    city_name=row['CityName'],
                    city_type=row.get('CityType'),
                    county_name=row.get('CountyName'),
                    county_fips=row.get('CountyFIPS'),
                    province_name=row.get('ProvinceName'),
                    province_abbr=row.get('ProvinceAbbr'),
                    state_fips=row.get('StateFIPS'),
                    msa_code=row.get('MSACode'),
                    area_code=row.get('AreaCode'),
                    time_zone=row.get('TimeZone'),
                    utc=row.get('UTC'),
                    dst=row.get('DST'),
                    latitude=float(row['Latitude']) if row.get('Latitude') else None,
                    longitude=float(row['Longitude']) if row.get('Longitude') else None
                )
                cities.append(city)

            db.session.bulk_save_objects(cities)
            db.session.commit()
            print(f"✅ Imported {len(cities)} cities from address_info.csv.")

if __name__ == '__main__':
    import_cities()
