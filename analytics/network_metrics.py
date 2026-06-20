"""
analytics/network_metrics.py — passing-network builders + centrality.

build_network() turns a team's passes into:
  - nodes: one row per player with average pitch position, total passes (size)
    and betweenness centrality (colour) — the key connector lights up.
  - edges: one row per player pair with combined pass count (thickness) and
    completion % (hover).

Betweenness is computed on an undirected graph where edge weight is 1/count, so
frequently-combining pairs are "closer" — the standard distance convention.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def build_network(passes: pd.DataFrame, min_pair: int = 2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    passes: output of transforms.get_passes for one team (cols: player,
    pass_recipient, x, y, end_x, end_y, completed).
    Returns (nodes, edges). Empty frames if there is nothing to draw.
    """
    empty = pd.DataFrame()
    if passes is None or passes.empty:
        return empty, empty

    attempts = passes[passes["pass_recipient"].notna()].copy()
    completed = attempts[attempts["completed"]].copy()
    if completed.empty:
        return empty, empty

    # average position: blend where a player passes from and receives the ball
    as_passer = completed[["player", "x", "y"]].rename(columns={"player": "p"})
    as_recv = completed[["pass_recipient", "end_x", "end_y"]].rename(
        columns={"pass_recipient": "p", "end_x": "x", "end_y": "y"})
    pos = pd.concat([as_passer, as_recv]).groupby("p")[["x", "y"]].mean()

    made = attempts.groupby("player").size().rename("passes")

    # unordered pair aggregation
    completed["pair"] = [_pair(a, b) for a, b in zip(completed["player"], completed["pass_recipient"])]
    attempts["pair"] = [_pair(a, b) for a, b in zip(attempts["player"], attempts["pass_recipient"])]
    pair_count = completed.groupby("pair").size().rename("count")
    pair_att = attempts.groupby("pair").size().rename("attempts")

    edges = pd.concat([pair_count, pair_att], axis=1).reset_index()
    edges["count"] = edges["count"].fillna(0).astype(int)
    edges["a"] = edges["pair"].str[0]
    edges["b"] = edges["pair"].str[1]
    edges["completion"] = edges["count"] / edges["attempts"]
    edges = edges[edges["count"] >= min_pair].reset_index(drop=True)

    # betweenness on the thresholded graph
    g = nx.Graph()
    for e in edges.itertuples():
        g.add_edge(e.a, e.b, weight=1.0 / e.count)
    bc = nx.betweenness_centrality(g, weight="weight") if g.number_of_nodes() else {}

    nodes = pos.join(made).reset_index().rename(columns={"p": "player"})
    nodes["passes"] = nodes["passes"].fillna(0).astype(int)
    nodes["betweenness"] = nodes["player"].map(bc).fillna(0.0)
    return nodes, edges
