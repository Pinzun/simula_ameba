
# io_utils/hydro.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
from collections import defaultdict
import subprocess

def log_hydro_info(hd: dict,
                   inflow_node: dict,
                   irr: dict,
                   logger,
                   *,
                   sample: int = 3,
                   project_root: Path | None = None,
                   png_relpath: str = "outputs/diagrams/hydro_basins.png",
                   html_relpath: str | None = None):
    """
    Logs KISS de la parte hídrica y dispara el plot externo.

    Parámetros
    ----------
    hd: dict de load_hydro_structures(...)
    inflow_node: dict[(node,stage,block)->Hm3]
    irr: dict con 'irr_required_node' -> dict[(node,stage,block)->Hm3]
    logger: logging.Logger
    sample: muestras head/tail
    project_root: raíz del proyecto para armar rutas de salida y ubicar el script
    png_relpath: ruta relativa del PNG de salida
    html_relpath: ruta relativa del HTML (opcional; requiere pyvis)
    """
    lg = logger
    HN = hd["hydro_nodes"]
    DAMS = hd["dams"]
    GENS = hd["gens"]
    ARCS = hd["arcs"]
    dam_node = hd["dam_node"]
    gen_node = hd["gen_node"]
    gen_dam  = hd["gen_dam"]

    lg.info("hidro: nodes=%d, dams=%d, gens=%d, arcs=%d",
            len(HN), len(DAMS), len(GENS), len(ARCS))

    # --- Muestras (head/tail)
    for title, seq in [("nodes", HN), ("dams", DAMS), ("gens", GENS), ("arcs", ARCS)]:
        if seq:
            head = list(seq)[:sample]
            tail = list(seq)[-sample:]
            lg.info("%s head: %s", title, head)
            lg.info("%s tail: %s", title, tail)

    # --- Chequeos simples de referencias
    missing_dam_nodes = sorted({d for d,n in dam_node.items() if n not in HN})
    missing_gen_nodes = sorted({g for g,n in gen_node.items() if n not in HN})
    missing_gen_dams  = sorted({g for g,d in gen_dam.items() if (d not in DAMS and d not in (None,""))})

    if missing_dam_nodes:
        lg.warning("Embalses con nodo inexistente (%d): %s", len(missing_dam_nodes), missing_dam_nodes[:sample])
    if missing_gen_nodes:
        lg.warning("Generadores con nodo inexistente (%d): %s", len(missing_gen_nodes), missing_gen_nodes[:sample])
    if missing_gen_dams:
        lg.warning("Generadores con 'dam' inexistente (%d): %s", len(missing_gen_dams), missing_gen_dams[:sample])

    # --- Arcos con extremos faltantes
    bad_arcs = [(i,j) for (i,j) in ARCS if (i not in HN or j not in HN)]
    if bad_arcs:
        lg.warning("Conexiones con extremos inexistentes (%d): %s", len(bad_arcs), bad_arcs[:sample])

    # --- Inflows / Riego: conteos
    lg.info("inflows: %d entradas (node,stage,block)", len(inflow_node))
    irr_node = irr.get("irr_required_node", {})
    lg.info("irrigation: %d entradas (node,stage,block)", len(irr_node))

    # --- Componentes (si networkx está disponible)
    try:
        import networkx as nx
        G = nx.DiGraph()
        G.add_nodes_from(HN)
        G.add_edges_from(ARCS)
        comps = list(nx.weakly_connected_components(G))
        lg.info("cuencas (componentes débiles): %d", len(comps))
        if comps:
            sizes = sorted((len(c) for c in comps), reverse=True)
            lg.info("tamaño de cuencas (top 5): %s", sizes[:5])

        # Ciclos (ojo: puede ser costoso si el grafo es grande; mostramos 1 si existe)
        try:
            cyc = next(nx.simple_cycles(G), None)
            if cyc:
                lg.warning("¡Ciclo detectado en conexiones hídricas! ejemplo: %s", cyc)
            else:
                lg.info("no se detectaron ciclos dirigidos en conexiones hídricas (DAG).")
        except StopIteration:
            lg.info("no se detectaron ciclos dirigidos en conexiones hídricas (DAG).")
    except Exception as e:
        lg.info("networkx no disponible o falló análisis de componentes: %s", e)

    # --- Disparo del plot externo
    try:
        import sys
        base = project_root or Path(".")
        script = base / "scripts" / "plot_hydro_graph.py"
        if not script.exists():
            lg.warning("No se encontró %s; omito diagrama.", script)
            return

        png_out = base / png_relpath
        cmd = [sys.executable, str(script), "--project-root", str(base), "--png", str(png_out)]
        if html_relpath:
            html_out = base / html_relpath
            cmd += ["--html", str(html_out)]

        subprocess.run(cmd, check=True)
        lg.info("Diagrama hídrico guardado en %s", png_out)
        if html_relpath:
            lg.info("Diagrama interactivo (HTML) guardado en %s", html_out)
    except subprocess.CalledProcessError as e:
        lg.error("Fallo al generar diagrama hídrico (plot_hydro_graph.py): %s", e)
    except FileNotFoundError as e:
        lg.error("No se pudo ejecutar el generador de diagramas: %s", e)



def load_hydro_structures(
    hydro_node_csv: Path,
    dam_csv: Path,
    conn_csv: Path,
    hydro_gen_csv: Path,
):
    # --- Hydro nodes ---
    hn = pd.read_csv(hydro_node_csv)
    assert {"name"}.issubset(hn.columns)
    hydro_nodes = sorted(hn["name"].astype(str))

    # --- Dams ---
    dm = pd.read_csv(dam_csv)
    req = {"name","node","vmax","vmin","vini","vend"}
    assert req.issubset(dm.columns), f"Dam.csv debe contener {req}"
    dm["node"] = dm["node"].astype(str)
    dams = sorted(dm["name"].astype(str))
    dam_node = {r.name: r.node for r in dm[["name","node"]].itertuples(index=False)}
    Vmax = {r.name: float(r.vmax) for r in dm.itertuples(index=False)}
    Vmin = {r.name: float(r.vmin) for r in dm.itertuples(index=False)}
    Vini = {r.name: float(r.vini) for r in dm.itertuples(index=False)}
    Vend = {r.name: float(r.vend) for r in dm.itertuples(index=False)}

    # --- Connections (node->node) ---
    cn = pd.read_csv(conn_csv)
    # Acepta dos esquemas:
    # A) nuevo: ini_node / end_node
    # B) crudo PNCP: h_type, ini, end, h_max_flow, h_min_flow, h_delay
    has_new = {"ini_node", "end_node", "h_max_flow", "h_min_flow", "h_delay"}.issubset(cn.columns)
    has_raw = {"h_type", "ini", "end", "h_max_flow", "h_min_flow", "h_delay"}.issubset(cn.columns)

    if not (has_new or has_raw):
        raise AssertionError(
            "HydroConnection.csv debe contener "
            "{ini_node,end_node,h_max_flow,h_min_flow,h_delay} "
            "o bien {h_type,ini,end,h_max_flow,h_min_flow,h_delay}"
        )

    if has_raw:
        # Filtra solo arcos de agua (excluye riego aquí)
        cn = cn.loc[~cn["h_type"].str.lower().eq("irrigation")].copy()
        cn = cn.rename(columns={"ini": "ini_node", "end": "end_node"})

    # Normaliza tipos
    for col in ["ini_node", "end_node"]:
        cn[col] = cn[col].astype(str).str.strip()

    cn["h_max_flow"] = pd.to_numeric(cn["h_max_flow"], errors="coerce").fillna(0.0)
    cn["h_min_flow"] = pd.to_numeric(cn["h_min_flow"], errors="coerce").fillna(0.0)
    cn["h_delay"]    = pd.to_numeric(cn["h_delay"], errors="coerce").fillna(0).astype(int)

    # Construye estructuras
    arcs = [(r.ini_node, r.end_node) for r in cn.itertuples(index=False)]
    Fmax = {(r.ini_node, r.end_node): float(r.h_max_flow) for r in cn.itertuples(index=False)}
    Fmin = {(r.ini_node, r.end_node): float(r.h_min_flow) for r in cn.itertuples(index=False)}
    Hdelay_blk = {(r.ini_node, r.end_node): int(r.h_delay) for r in cn.itertuples(index=False)}
    # --- Hydro generators ---
    hg = pd.read_csv(hydro_gen_csv)
    req = {"name","node","dam","rho_mwh_per_hm3","pmax","candidate"}
    assert req.issubset(hg.columns), f"HydroGenerator.csv debe contener {req}"
    hg["node"] = hg["node"].astype(str)
    gens = sorted(hg["name"].astype(str))
    gen_node = {r.name: r.node for r in hg[["name","node"]].itertuples(index=False)}
    gen_dam  = {r.name: (None if (pd.isna(r.dam) or str(r.dam)=="") else str(r.dam))
                for r in hg.itertuples(index=False)}
    Rho  = {r.name: float(r.rho_mwh_per_hm3) for r in hg.itertuples(index=False)}   # MWh/Hm3
    Pmax = {r.name: float(r.pmax) for r in hg.itertuples(index=False)}               # MW
    Cand = {r.name: bool(r.candidate) for r in hg.itertuples(index=False)}

    # Índices derivados
    dams_by_node = defaultdict(list)
    for d, n in dam_node.items():
        dams_by_node[n].append(d)

    gens_by_node = defaultdict(list)
    for g, n in gen_node.items():
        gens_by_node[n].append(g)

    return dict(
        hydro_nodes=hydro_nodes,
        dams=dams,
        gens=gens,
        arcs=arcs,
        dam_node=dam_node,
        gens_by_node=gens_by_node,
        dams_by_node=dams_by_node,
        gen_node=gen_node,
        gen_dam=gen_dam,
        Rho=Rho,
        Pmax=Pmax,
        Cand=Cand,
        Fmax=Fmax,
        Fmin=Fmin,
        Hdelay_blk=Hdelay_blk,
    )

def load_inflows_node(inflows_csv: Path):
    # columnas: node, stage, block, inflow_hm3
    df = pd.read_csv(inflows_csv)
    req = {"node","stage","block","inflow_hm3"}
    assert req.issubset(df.columns), f"inflows_qm3.csv debe contener {req}"
    df["node"]  = df["node"].astype(str)
    df["stage"] = df["stage"].astype(int)
    df["block"] = df["block"].astype(int)
    inflow = {(r.node, r.stage, r.block): float(r.inflow_hm3) for r in df.itertuples(index=False)}
    return inflow

def load_irrigation(irr_points_csv: Path, irr_req_csv: Path):
    # IrrigationPoint.csv: [name,node]
    ip = pd.read_csv(irr_points_csv)
    assert {"name","node"}.issubset(ip.columns)
    ip["node"] = ip["node"].astype(str)
    point_node = {r.name: r.node for r in ip.itertuples(index=False)}
    # irrigations_qm3.csv: [name,stage,block,irr_hm3]
    rq = pd.read_csv(irr_req_csv)
    assert {"name","stage","block","irr_hm3"}.issubset(rq.columns)
    rq["stage"] = rq["stage"].astype(int)
    rq["block"] = rq["block"].astype(int)

    # agregamos por nodo
    irr_node = defaultdict(float)
    for r in rq.itertuples(index=False):
        nd = point_node[r.name]
        irr_node[(nd, r.stage, r.block)] += float(r.irr_hm3)

    return dict(irr_required_node=dict(irr_node), point_node=point_node)

# --- NUEVO: grupos hídricos -----------------------------------------------
def load_hydro_groups(hydro_group_csv: Path, hydro_gen_csv: Path):
    """
    Carga grupos hídricos y el mapeo generador->grupo.
    HydroGroup.csv: name, start_time, end_time, report, hg_sp_min, hg_sp_max
    HydroGenerator.csv: ... , (columna 'group' o 'hydro_group_name')
    """

    hg = pd.read_csv(hydro_group_csv)
    req = {"name","hg_sp_min","hg_sp_max"}
    assert req.issubset(hg.columns), f"HydroGroup.csv debe contener {req}"

    groups = sorted(hg["name"].astype(str))
    Gmin = {r.name: float(r.hg_sp_min) for r in hg.itertuples(index=False)}
    Gmax = {r.name: float(r.hg_sp_max) for r in hg.itertuples(index=False)}

    gen = pd.read_csv(hydro_gen_csv)
    gen_cols = set(gen.columns)
    group_col = "group" if "group" in gen_cols else ("hydro_group_name" if "hydro_group_name" in gen_cols else None)
    gen_to_group = {}
    if group_col:
        for r in gen.itertuples(index=False):
            gname = str(getattr(r, "name"))
            ggrp  = getattr(r, group_col)
            gen_to_group[gname] = (None if pd.isna(ggrp) or str(ggrp)=="" else str(ggrp))
    else:
        # si no hay columna de grupo, no asignamos
        pass

    return dict(
        groups=groups,
        group_min=Gmin,
        group_max=Gmax,
        gen_to_group=gen_to_group
    )


# --- NUEVO: catálogo de inflows -------------------------------------------
def load_inflow_catalog(inflow_catalog_csv: Path):
    """
    Inflow.csv: name,start_time,end_time,report,inflows_qm3,plp_indep_hydro
    Devuelve escala (multiplicador) y flag por inflow.
    """
    import pandas as pd
    cat = pd.read_csv(inflow_catalog_csv)
    assert {"name","inflows_qm3","plp_indep_hydro"}.issubset(cat.columns)
    scale = {str(r.name): float(r.inflows_qm3) for r in cat.itertuples(index=False)}
    indep = {str(r.name): bool(r.plp_indep_hydro) for r in cat.itertuples(index=False)}
    return dict(scale=scale, independent=indep)

def load_inflow_map(inflow_map_csv: Path):
    """
    InflowMap.csv: inflow_name,node[,dam]
    """
    import pandas as pd
    mp = pd.read_csv(inflow_map_csv)
    assert {"inflow_name","node"}.issubset(mp.columns)
    mp["inflow_name"] = mp["inflow_name"].astype(str)
    mp["node"] = mp["node"].astype(str)
    has_dam = "dam" in mp.columns
    inflow_to_node = {r.inflow_name: r.node for r in mp.itertuples(index=False)}
    inflow_to_dam  = ({r.inflow_name: (None if (not has_dam or pd.isna(r.dam) or str(r.dam)=="") else str(r.dam))
                       for r in mp.itertuples(index=False)} if True else {})
    return inflow_to_node, inflow_to_dam

def build_node_inflows_from_wide_inflows_qm3(
    inflows_wide_csv: Path,
    inflow_catalog_csv: Path,
    inflow_map_csv: Path,
    blocks_csv: Path,
):
    """
    Transforma inflows wide (Afl_*) en dict[(node,stage,block)] = Hm3,
    usando el calendario blocks.csv para mapear 'time' a (stage,block).
    Aplica escala desde Inflow.csv si existe (multiplica).
    """
    import pandas as pd

    # 1) Leer wide
    df = pd.read_csv(inflows_wide_csv)
    assert "time" in df.columns, "inflows_qm3.csv debe tener columna 'time'"
    # columnas Afl_*
    afl_cols = [c for c in df.columns if c.startswith("Afl_")]
    if not afl_cols:
        raise ValueError("inflows_qm3.csv no tiene columnas 'Afl_*'")

    # 2) Leer catálogo (escala) y mapa a nodos
    cat = load_inflow_catalog(inflow_catalog_csv)
    inflow_to_node, inflow_to_dam = load_inflow_map(inflow_map_csv)

    # 3) Leer blocks para mapear time->(stage,block)
    b = pd.read_csv(blocks_csv)
    # esperamos columnas: stage, block, start_time, (duration_h)
    assert {"stage","block","start_time"}.issubset(b.columns)
    b["stage"] = b["stage"].astype(int)
    b["block"] = b["block"].astype(int)

    # normalizamos el 'time' de inflows a datetime y unimos por start_time
    df["_time_dt"] = pd.to_datetime(df["time"], format="%Y-%m-%d-%H:%M", errors="coerce")
    b["_start_dt"] = pd.to_datetime(b["start_time"], format="%Y-%m-%d-%H:%M", errors="coerce")

    # Unimos por timestamp exacto (tu blocks ya está a 1h por fila)
    mrg = b.merge(df, left_on="_start_dt", right_on="_time_dt", how="left")

    # 4) Pasar a largo por inflow
    long = mrg.melt(
        id_vars=["stage","block"],
        value_vars=afl_cols,
        var_name="inflow_name",
        value_name="hm3_raw"
    ).fillna(0.0)

    # 5) Escala desde catálogo
    long["scale"] = long["inflow_name"].map(cat["scale"]).fillna(1.0)
    long["hm3"]   = long["hm3_raw"] * long["scale"]

    # 6) Map inflow -> node y agregamos por nodo
    long["node"] = long["inflow_name"].map(inflow_to_node)
    missing = sorted(long.loc[long["node"].isna(),"inflow_name"].unique().tolist())
    if missing:
        # no abortamos; loggeamos arriba (desde run), pero acá limpiamos
        long = long.dropna(subset=["node"]).copy()

    # 7) Agregación por (node,stage,block)
    agg = long.groupby(["node","stage","block"], as_index=False)["hm3"].sum()

    # 8) Dict final
    inflow_node = {(r.node, int(r.stage), int(r.block)): float(r.hm3) for r in agg.itertuples(index=False)}
    return inflow_node, missing

# ------------ catálogo de riego con VOLI ------------------------------------
def load_irrigation_catalog(irrigation_catalog_csv: Path):
    """
    Irrigation.csv: name,start_time,end_time,report,irrigations_qm3,voli
    """
    import pandas as pd
    ic = pd.read_csv(irrigation_catalog_csv)
    assert {"name","voli"}.issubset(ic.columns)
    voli_by_point = {str(r.name): float(r.voli) for r in ic.itertuples(index=False)}
    return voli_by_point

def project_voli_to_nodes(voli_by_point: dict, point_node: dict, reduce="max"):
    """
    Proyecta VOLI (por punto) a VOLI por nodo hídrico (scalar).
    reduce: 'max' (default) o 'mean'
    """
    from collections import defaultdict
    tmp = defaultdict(list)
    for p, v in voli_by_point.items():
        n = point_node.get(p, None)
        if n is not None:
            tmp[n].append(v)
    if reduce == "max":
        voli_node = {n: max(vs) for n, vs in tmp.items()}
    else:
        voli_node = {n: sum(vs)/len(vs) for n, vs in tmp.items()}
    return voli_node