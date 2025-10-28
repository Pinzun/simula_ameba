from pathlib import Path

ruta_base = Path(__file__).parent.parent.parent
ruta_data = ruta_base / "data"

# Obtiene todos los subdirectorios en la carpeta data
subdirs = [x for x in ruta_data.iterdir() if x.is_dir()]

total_archivos = 0

# Itera en cada directorio
for subdir in subdirs:
    # Reconoce las carpetas dentro de cada subdirectorio
    sub_subdirs = [x for x in subdir.iterdir() if x.is_dir()]
    for sub_subdir in sub_subdirs:
        archivos = list(sub_subdir.glob('*.*'))
        print(f"Subcarpeta en {subdir.name}: {sub_subdir.name}")
        print(f"Total archivos en {sub_subdir.name}: {len(archivos)}")
        # Sumar archivos de subcarpetas al total general
        total_archivos += len(archivos)

    archivos = list(subdir.glob('*.*'))
    print(f"\nArchivos en {subdir.name}:")
    print(f"Total archivos en {subdir.name}: {len(archivos)}")
    for file in archivos:
        print(f"- {file.name}")
    # Sumar archivos del subdirectorio de primer nivel
    total_archivos += len(archivos)

print(f"\nTotal archivos en todas las carpetas: {total_archivos}")