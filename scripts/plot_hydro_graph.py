# -*- coding: utf-8 -*-
"""
scripts/plot_hydro_graph.py

Genera un diagrama de cuencas a partir de:
- data/processed/HydroNode.csv        (cols: name[, region])
- data/processed/Dam.csv              (cols: name, node, vmax, vmin, vini, vend)
- data/processed/HydroConnection.csv  (cols: name, ini_node, end_node, h_max_flow, h_min_flow, h_delay[, h_type])
- data/processed/HydroGenerator.csv   (cols: name, node, dam, rho_mwh_per_hm3, pmax, candidate)
- data/processed/IrrigationPoint.csv  (cols: name, node)

Salida:
- outputs/diagrams/hydro_basins.png
- (opcional) outputs/diagrams/hydro_basins.html (si usas --html y tienes pyvis)
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import networkx as nx
import matplotlib
import matplotlib.pyplot as plt

# Asegura soporte de UTF-8 en labels (acentos)
matplotlib.rcParams["axes.unicode_minus"] = False

# --------------------------
# Carga y normalización
# --------------------------
def _col_like(df: pd.DataFrame, name: str) -> str:
    for c in df.columns:
        if c.lower() == name.lower():
            return c
    raise KeyError(name)

def load_tables(base: Path):
    hn = pd.read_csv(base / "data/processed/HydroNode.csv", encoding="utf-8")
    dm = pd.read_csv(base / "data/processed/Dam.csv", encoding="utf-8", dtype=str)
    cn = pd.read_csv(base / "data/processed/HydroConnection.csv", encoding="utf-8")
    hg = pd.read_csv(base / "data/processed/HydroGenerator.csv", encoding="utf-8", dtype=str)

    # normaliza HydroConnection (ini_node/end_node)
    cols = {c.lower(): c for c in cn.columns}
    has_new = {"ini_node", "end_node"}.issubset(cols.keys())
    has_raw = {"ini", "end"}.issubset(cols.keys())

    if has_new:
        ini_col = _col_like(cn, "ini_node")
        end_col = _col_like(cn, "end_node")
    elif has_raw:
        ini_col = _col_like(cn, "ini")
        end_col = _col_like(cn, "end")
        cn.rename(columns={ini_col: "ini_node", end_col: "end_node"}, inplace=True)
        ini_col, end_col = "ini_node", "end_node"
    else:
        raise AssertionError("HydroConnection.csv debe tener (ini_node,end_node,...) o (ini,end,...)")

    for need, default in [
        ("h_type", "waterway"),
        ("h_max_flow", 0.0),
        ("h_min_flow", 0.0),
        ("h_delay", 0),
    ]:
        if not any(c.lower() == need for c in cn.columns):
            cn[need] = default

    # Tipos/limpieza
    for c in ("ini_node", "end_node"):
        cn[c] = cn[c].astype(str).str.strip()
    cn["h_type"] = cn["h_type"].astype(str).str.lower()
    cn["h_max_flow"] = pd.to_numeric(cn["h_max_flow"], errors="coerce").fillna(0.0)
    cn["h_min_flow"] = pd.to_numeric(cn["h_min_flow"], errors="coerce").fillna(0.0)
    cn["h_delay"]    = pd.to_numeric(cn["h_delay"], errors="coerce").fillna(0).astype(int)

    # Normaliza otras tablas
    if "name" in hn.columns:
        hn["name"] = hn["name"].astype(str).str.strip()
    if "name" in dm.columns:
        dm["name"] = dm["name"].astype(str).str.strip()
        if "node" in dm.columns:
            dm["node"] = dm["node"].astype(str).str.strip()
    if "name" in hg.columns:
        hg["name"] = hg["name"].astype(str).str.strip()
        if "node" in hg.columns:
            hg["node"] = hg["node"].astype(str).str.strip()
        if "dam" in hg.columns:
            hg["dam"] = hg["dam"].astype(str).fillna("").str.strip()

    ip_path = base / "data/processed/IrrigationPoint.csv"
    if ip_path.exists():
        ip = pd.read_csv(ip_path, encoding="utf-8", dtype=str)
        for c in ("name", "node"):
            if c in ip.columns:
                ip[c] = ip[c].astype(str).str.strip()
    else:
        ip = pd.DataFrame(columns=["name", "node"])

    return hn, dm, cn, hg, ip

# --------------------------
# Grafo + lógica anti-duplicado
# --------------------------
def build_graph(hn, dm, cn, hg, ip) -> nx.DiGraph:
    """
    Construye el grafo hidráulico para el diagrama de cuencas.

    - Los embalses (Dam) se muestran una sola vez como nodos de tipo 'dam'.
    - Si un embalse aparece también como extremo en HydroConnection, se usa
      el mismo nodo (es parte del tránsito del agua).
    - No se modifican los archivos ni las relaciones del modelo: solo el gráfico.
    """
    G = nx.DiGraph()

    # --- Conjuntos base ---
    dam_names = set(dm["name"].astype(str).str.strip())
    hydro_nodes_all = set(hn["name"].astype(str).str.strip())

    def node_id_for(name: str) -> str:
        """Devuelve el id de nodo unificado: DAM: si es embalse, HN: en caso contrario."""
        return f"DAM:{name}" if name in dam_names else f"HN:{name}"

    # --- 1) Agregar embalses (Dam) ---
    for r in dm.itertuples(index=False):
        dam_name = str(r.name).strip()
        dam_id = f"DAM:{dam_name}"
        G.add_node(dam_id, label=dam_name, kind="dam")

    # --- 2) Agregar nodos hidráulicos (HydroNode) no duplicados ---
    for r in hn.itertuples(index=False):
        name = str(r.name).strip()
        if name in dam_names:
            continue  # se dibuja solo como DAM
        G.add_node(f"HN:{name}", label=name, kind="hydro_node")

    # --- 3) Generadores (GEN) ---
    for r in hg.itertuples(index=False):
        gen_name = str(r.name).strip()
        gen_id = f"GEN:{gen_name}"
        G.add_node(gen_id, label=gen_name, kind="gen")

        # Enlazar al nodo o embalse al que pertenece
        if hasattr(r, "node"):
            node_name = str(r.node).strip()
            host_id = node_id_for(node_name)
            if G.has_node(host_id):
                G.add_edge(gen_id, host_id, kind="at_node")

        # Enlazar al embalse del que depende, si aplica
        if hasattr(r, "dam") and str(getattr(r, "dam") or "").strip():
            dam_name = str(r.dam).strip()
            dam_id = f"DAM:{dam_name}"
            if G.has_node(dam_id):
                G.add_edge(dam_id, gen_id, kind="feeds")

    # --- 4) Puntos de riego (IRR) ---
    if not ip.empty:
        for r in ip.itertuples(index=False):
            irr_name = str(r.name).strip()
            irr_id = f"IRR:{irr_name}"
            G.add_node(irr_id, label=irr_name, kind="irr")
            if hasattr(r, "node"):
                node_name = str(r.node).strip()
                host_id = node_id_for(node_name)
                if G.has_node(host_id):
                    G.add_edge(host_id, irr_id, kind="irrigates")

    # --- 5) Conexiones hidráulicas (ríos) ---
    # Acepta nombres de columnas raw (ini/end) o normalizados (ini_node/end_node)
    ini_col = "ini_node" if "ini_node" in cn.columns else ("ini" if "ini" in cn.columns else None)
    end_col = "end_node" if "end_node" in cn.columns else ("end" if "end" in cn.columns else None)
    if not ini_col or not end_col:
        raise AssertionError("HydroConnection.csv debe tener columnas ini_node/end_node (o ini/end).")

    for r in cn.itertuples(index=False):
        ini = str(getattr(r, ini_col)).strip()
        end = str(getattr(r, end_col)).strip()
        u = node_id_for(ini)
        v = node_id_for(end)
        if G.has_node(u) and G.has_node(v):
            G.add_edge(
                u, v,
                kind="river",
                delay=getattr(r, "h_delay", 0),
                fmax=getattr(r, "h_max_flow", None),
                fmin=getattr(r, "h_min_flow", None),
            )

    return G

# --------------------------
# Estilos y layout
# --------------------------
def _style_for(node_kind: str, has_dam: bool = False):
    # Para HN con embalse fusionado, usamos rombo
    if node_kind == "hydro_node" and has_dam:
        return dict(node_color="#2D6CB1", node_shape="D")  # azul, rombo
    if node_kind == "hydro_node":
        return dict(node_color="#4C78A8", node_shape="s")  # azul, cuadrado
    if node_kind == "dam":
        return dict(node_color="#F58518", node_shape="o")  # naranjo
    if node_kind == "gen":
        return dict(node_color="#54A24B", node_shape="^")  # verde
    if node_kind == "irr":
        return dict(node_color="#B279A2", node_shape="v")  # púrpura
    return dict(node_color="#9e9e9e", node_shape="o")

def hierarchical_layout_or_fallback(G: nx.DiGraph):
    try:
        from networkx.drawing.nx_agraph import graphviz_layout
        try:
            return graphviz_layout(G, prog="dot")
        except Exception as e:
            print(f"[WARN] graphviz_layout no disponible ({e}); usando kamada_kawai_layout.")
            return nx.kamada_kawai_layout(G)
    except Exception as e:
        print(f"[WARN] nx_agraph no disponible ({e}); usando spring_layout.")
        return nx.spring_layout(G, k=0.7, seed=42)

def draw_hydro_graph(G: nx.DiGraph, out_png: Path, figsize=(16, 10)):
    pos = hierarchical_layout_or_fallback(G)
    plt.figure(figsize=figsize)
    ax = plt.gca()
    ax.set_title("Diagrama de cuencas (nodos hídricos, embalses, generadores y riego)")

    # Agrupa por tipo
    kinds = ["hydro_node", "dam", "gen", "irr"]
    for k in kinds:
        if k == "hydro_node":
            nodes_k = [n for n, d in G.nodes(data=True) if d.get("kind") == k and not d.get("has_dam", False)]
            if nodes_k:
                style = _style_for("hydro_node", has_dam=False)
                nx.draw_networkx_nodes(G, pos, nodelist=nodes_k,
                                       node_color=style["node_color"], node_shape=style["node_shape"],
                                       node_size=420, alpha=0.95, ax=ax)
            nodes_kd = [n for n, d in G.nodes(data=True) if d.get("kind") == k and d.get("has_dam", False)]
            if nodes_kd:
                style = _style_for("hydro_node", has_dam=True)
                nx.draw_networkx_nodes(G, pos, nodelist=nodes_kd,
                                       node_color=style["node_color"], node_shape=style["node_shape"],
                                       node_size=520, alpha=0.98, ax=ax)
        else:
            nodes_k = [n for n, d in G.nodes(data=True) if d.get("kind") == k]
            if nodes_k:
                style = _style_for(k)
                nx.draw_networkx_nodes(G, pos, nodelist=nodes_k,
                                       node_color=style["node_color"], node_shape=style["node_shape"],
                                       node_size=380, alpha=0.95, ax=ax)

    river_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "river"]
    other_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") != "river"]

    nx.draw_networkx_edges(G, pos, edgelist=other_edges, width=1.0, alpha=0.3, edge_color="#999999", arrows=True, ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=river_edges, width=2.0, alpha=0.9, edge_color="#2F4B7C", arrows=True, ax=ax)

    # Etiquetas: para HN con embalse mostramos “<nodo> (Embalse)”
    labels = {}
    for n, d in G.nodes(data=True):
        lab = d.get("label", str(n))
        if d.get("kind") == "hydro_node" and d.get("has_dam", False):
            # si hay lista de embalses fusionados, puedes agregarla si quieres:
            # dams = d.get("dam_list", [])
            lab = f"{lab} (Embalse)"
        labels[n] = lab

    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_color="#222222", ax=ax)

    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color="#4C78A8", label="HydroNode (cuenca)"),
        mpatches.Patch(color="#2D6CB1", label="HydroNode con Embalse"),
        mpatches.Patch(color="#F58518", label="Dam (embalse aparte)"),
        mpatches.Patch(color="#54A24B", label="Gen (hidro)"),
        mpatches.Patch(color="#B279A2", label="Riego"),
        mpatches.Patch(color="#2F4B7C", label="Conexión hídrica (río)"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", frameon=False)
    ax.axis("off")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()

# --------------------------
# HTML interactivo (pyvis)
# --------------------------
def export_html_pyvis(G: nx.DiGraph, out_html: Path):
    from pyvis.network import Network
    out_html.parent.mkdir(parents=True, exist_ok=True)

    net = Network(height="800px", width="100%", directed=True, notebook=False)
    # opciones básicas (JSON válido)
    net.set_options('{"interaction":{"hover":true},"physics":{"enabled":true}}')

    for n, d in G.nodes(data=True):
        kind = d.get("kind")
        has_dam = d.get("has_dam", False)
        label = d.get("label", str(n))
        if kind == "hydro_node" and has_dam:
            label = f"{label} (Embalse)"
        color = _style_for(kind, has_dam)["node_color"]
        shape_map = {"s":"box","D":"diamond","o":"dot","^":"triangle","v":"triangleDown"}
        shape = shape_map[_style_for(kind, has_dam)["node_shape"]]
        net.add_node(str(n), label=label, title=label, color=color, shape=shape)

    for u, v, d in G.edges(data=True):
        color = "#2F4B7C" if d.get("kind") == "river" else "#999999"
        width = 2 if d.get("kind") == "river" else 1
        net.add_edge(str(u), str(v), color=color, width=width, arrows="to")

    net.write_html(str(out_html), open_browser=False, notebook=False)

# --------------------------
# main
# --------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--png", type=str, default="outputs/diagrams/hydro_basins.png")
    parser.add_argument("--html", type=str, default="", help="ruta HTML opcional (requiere pyvis)")
    args = parser.parse_args()

    base = Path(args.project_root)
    hn, dm, cn, hg, ip = load_tables(base)
    G = build_graph(hn, dm, cn, hg, ip)

    out_png = base / args.png
    draw_hydro_graph(G, out_png)
    print(f"[OK] PNG escrito en: {out_png}")

    if args.html:
        out_html = base / args.html
        export_html_pyvis(G, out_html)
        print(f"[OK] HTML escrito en: {out_html}")

if __name__ == "__main__":
    main()