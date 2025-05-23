from flask import Flask
from app.config import Config
from app.database import db
from app.models.rate_type import RateType
from app.models.mode import Mode
from app.models.equipment_type import EquipmentType
from app.models.accessorial import Accessorial
import pandas as pd
from app.models.city import City
from app.models.user import User


# Initialize Flask App
app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

def create_data():
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

        accesorials = [
            "Drop Trailer ", "Non-reimbursed Lumper", "Pallet Exchange",
            "E - track and Straps", "Additional Load Locks",  "Dunnage",
            "Hazmat", "TWIC", "Liftgate",
            "Pallet Jack", "Inside Delivery", "Residential",
            "Driver Assist", "Bulkhead", "Wood Floors",
            "Mesh Air - chute", "Blind Shipment", "Empty Scale Ticket",
            "Team Drivers", "Top Ice", "Cycle Reefer",
            "Continuous Reefer"
        ]

        for accesorial in accesorials:
            accesorial_item = Accessorial(
                name=accesorial
            )
            db.session.add(accesorial_item)
            db.session.commit()
            print("Accessorial added")

        # 1. Leer el archivo CSV
        df = pd.read_csv("/home/ubuntu/flask_app/app/static/address_info.csv")

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

        existing_user = User.query.filter_by(email='adriana@quotezen.com').first()

        if not existing_user:
            new_user = User(
                first_name='Admin',
                last_name='Quotezen',
                email='adriana@quotezen.com',
                phone='1234567890',
                address='123 Test Street',
                role='Admin'  # or 'Carrier', 'Shipper', etc.
            )
            db.session.add(new_user)
            db.session.commit()
            print("User created successfully.")
        else:
            print("User already exists.")


