import pandas as pd
import json
ruta = r"C:\Users\pinzunza\projectos_codigos\estudio_PNCP\data\fuel_price.csv"

fuel_price = pd.read_csv(ruta, sep=",", encoding="latin-1")
fuel_price=fuel_price.drop(columns=["scenario"])

fuel_price_long=fuel_price.melt(
    id_vars=['time'],
    var_name='fuel_name',
    value_name='value'
)


fuel_price_long.to_csv(r"C:\Users\pinzunza\projectos_codigos\estudio_PNCP\resultados\fuel_price.csv", sep=",", encoding="latin-1", index= False)