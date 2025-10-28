# /duracion_bloque_hr.py    

'''
Script que calcular la duración de cada bloque horario por mes a partir del archivo blocks
que corresponde a una entrada del modelo de simulación ejecutado en AMEBA para la determinación del plan
indicativo de obras 
'''
import pandas as pd 
from pathlib import Path

ruta_base= Path(__file__).parent.parent.parent
ruta_blocks= ruta_base /"data"/ "demanda"/ "blocks.csv"
ruta_resultados= ruta_base / "resultados"
nombre_resultado= "duracion_bloque_hr_ameba.xlsx"
ruta_archivo_salida= ruta_resultados/nombre_resultado 


blocks=pd.read_csv(ruta_blocks, sep=",", encoding= "utf-8")
# convertir la columna 'time' a datetime con el formato AAAA-MM-DD-HH:MM
blocks['time'] = pd.to_datetime(blocks['time'], format='%Y-%m-%d-%H:%M', errors='raise')
renombrar_columnas= {
    "stage": "stage(mes)",
    "block": "block(bloque_hr)"
}
blocks=blocks.rename(columns=renombrar_columnas)
#meses_interes=range(1,13)
#blocks=blocks[blocks["stage(mes)"].isin(meses_interes)]
# Calcular la duración de cada stage-block
blocks['duration'] = blocks['time'].diff().dt.total_seconds().fillna(0)

# Crear la tabla de doble entrada
tabla_doble_entrada = blocks.pivot_table(index='stage(mes)', columns='block(bloque_hr)', values='duration', aggfunc='count', fill_value=0)

# Filtrar los bloques en dos rangos|    
tabla_1_12 = tabla_doble_entrada.loc[:, tabla_doble_entrada.columns[0:12]]
tabla_13_24 = tabla_doble_entrada.loc[:, tabla_doble_entrada.columns[12:24]]
# Calcular el factor por fila (suma de todos los bloques)
duracion_anual_bloque = tabla_doble_entrada.sum(axis=1)

# Dividir cada celda por el factor correspondiente a su fila
tabla_1_12_porcentual = tabla_1_12.div(duracion_anual_bloque, axis=0)
tabla_13_24_porcentual = tabla_13_24.div(duracion_anual_bloque, axis=0)


# Guardar las tablas en diferentes hojas del archivo Excel
with pd.ExcelWriter(ruta_archivo_salida) as writer:
    tabla_1_12_porcentual.to_excel(writer, sheet_name='% bloques por día hábil')
    tabla_13_24_porcentual.to_excel(writer, sheet_name='% bloques por día inhábil')
    tabla_1_12.to_excel(writer, sheet_name='Total de bloques por día hábil')
    tabla_13_24.to_excel(writer, sheet_name='Total de bloques por inhabil')
    

print("Ejecución de código finalizada")