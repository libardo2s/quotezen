from flask import Flask
from config import Config
from database import db
from models.rate_type import RateType
from models.mode import Mode
from models.equipment_type import EquipmentType
from models.accessorial import Accessorial
import pandas as pd
from models.city import City

# Initialize Flask App
app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

with app.app_context():
    for rate_type in ["All-in", "Linehaul only"]:
        rate = RateType(
            name=rate_type
        )
        db.session.add(rate)
        db.session.commit()
        print("Rate Type added")

    for mode in ["FTL", "LTL", "Dray"]:
        mode_record = Mode(
            name=mode
        )
        db.session.add(mode_record)
        db.session.commit()
        print("Mode added")

    for equipment in ["R", "V", "53' Chasis"]:
        equipment_type = EquipmentType(
            name=equipment
        )
        db.session.add(equipment_type)
        db.session.commit()
        print("Equipment Type added")

    for accesorial in ["Accesorial1", "Accesorial2", "Accesorial3"]:
        accesorial_item = Accessorial(
            name=accesorial
        )
        db.session.add(accesorial_item)
        db.session.commit()
        print("Accessorial added")

    # 1. Leer el archivo CSV
    df = pd.read_csv("/Users/kandreyrosales/Desktop/quotezen/USA 5-digit & Canadian 6-digit.csv")

    # 2. Limpiar los datos
    df = df.fillna("")
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    # 3. Insertar en la base de datos
    cities = []
    for _, row in df.iterrows():
        city = City(
            country_name=row['CountryName'],
            postal_code=str(row['PostalCode']),
            postal_type=row['PostalType'],
            city_name=row['CityName'],
            city_type=row['CityType'],
            county_name=row['CountyName'],
            county_fips=str(row['CountyFIPS']),
            province_name=row['ProvinceName'],
            province_abbr=row['ProvinceAbbr'],
            state_fips=str(row['StateFIPS']),
            msa_code=str(row['MSACode']),
            area_code=row['AreaCode'],
            time_zone=row['TimeZone'],
            utc=str(row['UTC']),
            dst=row['DST'],
            latitude=row['Latitude'],
            longitude=row['Longitude']
        )
        cities.append(city)

    # 4. Guardar en la base de datos
    with db.session.begin():
        db.session.bulk_save_objects(cities)

    print(f"✅ Importadas {len(cities)} ciudades correctamente.")

