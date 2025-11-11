from __future__ import annotations
import pandas as pd
from pathlib import Path

base_dir = Path(__file__).parent.parent
data_raw_dir = base_dir / Path("data/raw")
file_name="blocks.csv"
blocks_csv_path = data_raw_dir / file_name
out_path = base_dir / Path("data/processed/blocks.csv")

blocks=pd.read_csv(blocks_csv_path,sep=",", encoding="latin-1")
blocks["duration_h"]=int(1)
blocks.rename(columns={"time": "start_time"}, inplace=True)
# asegurar que 'stage' sea numérica y filtrar por <= 132
blocks['stage'] = pd.to_numeric(blocks['stage'], errors='coerce')
blocks = blocks[blocks['stage'] <= 132]
blocks.to_csv(out_path, sep=",", encoding= "utf-8", index=False)