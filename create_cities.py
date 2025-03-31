import pandas as pd
from database import db
from models.city import City  # Asegúrate de importar tu modelo desde donde lo tengas definido

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