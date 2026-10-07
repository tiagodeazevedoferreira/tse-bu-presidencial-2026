#!/usr/bin/env python3
"""Generate an offline HTML dashboard for BU reception timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
INPUT = Path("data/processed/votacao_presidencial_por_secao_2026.csv")
DEFAULT_OUTPUT = Path("data/processed/dashboard_timeline_recebimento_bu_2026.html")
CHUNK_SIZE = 100_000
BIN_MINUTES = 5


def build_series(path: Path) -> tuple[dict, dict]:
    counts: dict[str, dict[str, int]] = {uf: {} for uf in UFS}
    totals = {uf: 0 for uf in UFS}

    for chunk in pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        usecols=["SG_UF", "DT_BU_RECEBIDO"],
        dtype=str,
        chunksize=CHUNK_SIZE,
    ):
        parsed = pd.to_datetime(
            chunk["DT_BU_RECEBIDO"],
            errors="coerce",
            dayfirst=True,
        )
        if parsed.isna().any():
            bad = chunk.loc[parsed.isna(), "DT_BU_RECEBIDO"].head(5).tolist()
            raise ValueError(f"DT_BU_RECEBIDO inválido. Exemplos: {bad}")

        bucket = parsed.dt.floor(f"{BIN_MINUTES}min")
        tmp = pd.DataFrame({"uf": chunk["SG_UF"], "bucket": bucket})
        grouped = tmp.groupby(["uf", "bucket"], sort=False).size()

        for (uf, stamp), count in grouped.items():
            if uf not in counts:
                raise ValueError(f"UF inesperada no nacional: {uf}")
            key = stamp.strftime("%Y-%m-%dT%H:%M")
            counts[uf][key] = counts[uf].get(key, 0) + int(count)
            totals[uf] += int(count)

    all_counts = {uf: counts[uf] for uf in UFS}
    merged: dict[str, int] = {}
    for uf in UFS:
        for stamp, count in counts[uf].items():
            merged[stamp] = merged.get(stamp, 0) + count
    all_counts["BR"] = merged
    totals["BR"] = sum(merged.values())
    return all_counts, totals


def prepare_payload(counts: dict[str, dict[str, int]], totals: dict[str, int]) -> dict:
    series = {}
    kpis = {}

    for uf, raw in counts.items():
        ordered = sorted(raw.items())
        cumulative = 0
        points = []
        for stamp, count in ordered:
            cumulative += count
            points.append({
                "t": stamp,
                "n": count,
                "cum": cumulative,
                "pct": round(cumulative * 100 / totals[uf], 4),
            })

        stamps = [p["t"] for p in points]
        kpis[uf] = {
            "sections": totals[uf],
            "first": stamps[0] if stamps else None,
            "last": stamps[-1] if stamps else None,
            "duration_min": (
                int((pd.Timestamp(stamps[-1]) - pd.Timestamp(stamps[0])).total_seconds() / 60)
                if len(stamps) > 1 else 0
            ),
        }
        series[uf] = points

    return {"bin_minutes": BIN_MINUTES, "series": series, "kpis": kpis}


HTML_TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linha do tempo — recebimento dos BUs | Eleições 2026</title>
<style>
:root{--bg:#f5f7fa;--card:#fff;--ink:#17202a;--muted:#65717e;--line:#dfe5eb;--accent:#1769aa;--accent2:#0f8b8d;--shadow:0 8px 28px rgba(23,32,42,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}
.wrap{max-width:1400px;margin:auto;padding:28px}.hero{margin-bottom:22px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font-size:30px;line-height:1.15;margin:5px 0 8px}h2{font-size:18px;margin:0 0 4px}.sub{color:var(--muted);max-width:900px}
.toolbar,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
.toolbar{padding:14px 16px;display:flex;gap:16px;align-items:end;flex-wrap:wrap;margin-bottom:16px}
label{display:flex;flex-direction:column;gap:5px;font-weight:600;color:#34404b}select{min-width:220px;padding:9px 11px;border:1px solid #cbd4dd;border-radius:8px;background:#fff;font:inherit}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.kpi{padding:16px}.kpi .label{color:var(--muted);font-size:12px}.kpi .value{font-size:21px;font-weight:750;margin-top:4px}
.card{padding:18px;margin-bottom:16px}.chart-wrap{width:100%;overflow:hidden}.chart{width:100%;height:390px}.legend{display:flex;gap:18px;color:var(--muted);font-size:12px;margin-top:8px}
.note{font-size:12px;color:var(--muted);padding-top:8px}.foot{color:var(--muted);font-size:12px;margin-top:20px}
svg text{font-family:inherit;fill:#66727e;font-size:11px}.grid{stroke:#e8edf2}.axis{stroke:#b9c3cc}.curve{fill:none;stroke:var(--accent);stroke-width:2.5}.bar{fill:var(--accent2);opacity:.75}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.chart{height:320px}}@media(max-width:560px){.wrap{padding:16px}.kpis{grid-template-columns:1fr 1fr}h1{font-size:24px}}
</style>
</head>
<body>
<div class="wrap">
<section class="hero">
<div class="eyebrow">TSE • 1º turno • 2026</div>
<h1>Linha do tempo de recebimento dos Boletins de Urna</h1>
<div class="sub">Distribuição temporal dos BUs registrados no campo <b>DT_BU_RECEBIDO</b>. A visão é por UF e usa blocos de 5 minutos para tornar a progressão comparável.</div>
</section>
<div class="toolbar">
<label>Unidade da Federação
<select id="uf"></select></label>
<div class="note">“Brasil” mostra o agregado das 27 UFs. O horário é apresentado como registrado na fonte; não é feita conversão de fuso.</div>
</div>
<div class="kpis" id="kpis"></div>
<section class="card">
<h2>Recebimento acumulado</h2>
<div class="sub">Percentual de seções cujo BU já havia sido recebido até cada intervalo.</div>
<div class="chart-wrap"><svg id="cum" class="chart" viewBox="0 0 1100 390" preserveAspectRatio="none"></svg></div>
<div class="legend">Linha = percentual acumulado de BUs recebidos.</div>
</section>
<section class="card">
<h2>Fluxo de recebimento</h2>
<div class="sub">Quantidade de BUs recebidos em cada bloco de 5 minutos.</div>
<div class="chart-wrap"><svg id="flow" class="chart" viewBox="0 0 1100 390" preserveAspectRatio="none"></svg></div>
</section>
<div class="foot">Fonte: Tribunal Superior Eleitoral (TSE), Boletim de Urna 2026. Este painel analisa recebimento de BU; não deve ser interpretado como instante individual de computação da totalização.</div>
</div>
<script>
const DATA=__DATA__;
const UFS=__UFS__;
const $=id=>document.getElementById(id);
const fmtInt=n=>new Intl.NumberFormat("pt-BR").format(n);
const fmtDate=s=>s?new Date(s).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"—";
function duration(min){return min<60?(min+" min"):(Math.floor(min/60)+"h "+(min%60)+"min")}
function setup(){
 const sel=$("uf");
 sel.innerHTML='<option value="BR">Brasil</option>'+UFS.map(u=>'<option value="'+u+'">'+u+'</option>').join("");
 sel.value="BR";sel.onchange=render;render();
}
function render(){
 const uf=$("uf").value,s=DATA.series[uf]||[],k=DATA.kpis[uf];
 $("kpis").innerHTML=[
  ["Seções",fmtInt(k.sections)],["Primeiro BU",fmtDate(k.first)],
  ["Último BU",fmtDate(k.last)],["Janela observada",duration(k.duration_min)]
 ].map(x=>'<div class="card kpi"><div class="label">'+x[0]+'</div><div class="value">'+x[1]+'</div></div>').join("");
 drawLine($("cum"),s,"pct",100,"%");drawBars($("flow"),s);
}
function scales(svg,s,field){
 const W=1100,H=390,L=62,R=18,T=18,B=44;
 const vals=s.map(p=>p[field]),max=Math.max(...vals,1),minT=new Date(s[0].t).getTime(),maxT=new Date(s[s.length-1].t).getTime();
 return {W,H,L,R,T,B,max,minT,maxT,x:t=>L+(t-minT)/Math.max(maxT-minT,1)*(W-L-R),y:v=>H-B-v/max*(H-T-B)};
}
function clear(svg){svg.innerHTML=""}
function el(tag,a,text){
 const n=document.createElementNS("http://www.w3.org/2000/svg",tag);
 for(const[k,v]of Object.entries(a||{}))n.setAttribute(k,v);
 if(text!=null)n.textContent=text;return n;
}
function drawLine(svg,s,field,maxY,suffix){
 clear(svg);if(!s.length)return;const c=scales(svg,s,field);c.max=maxY;
 for(let i=0;i<=4;i++){const y=c.y(i*maxY/4);svg.append(el("line",{x1:c.L,x2:c.W-c.R,y1:y,y2:y,class:"grid"}));svg.append(el("text",{x:8,y:y+4},Math.round(i*maxY/4)+suffix))}
 const pts=s.map(p=>c.x(new Date(p.t).getTime())+","+c.y(p[field])).join(" ");
 svg.append(el("polyline",{points:pts,class:"curve"}));
 const step=Math.max(1,Math.floor(s.length/7));
 for(let i=0;i<s.length;i+=step){const p=s[i],x=c.x(new Date(p.t).getTime());svg.append(el("line",{x1:x,x2:x,y1:c.H-c.B,y2:c.H-c.B+5,class:"axis"}));svg.append(el("text",{x:x-18,y:c.H-12},fmtDate(p.t).slice(11,16)))}
}
function drawBars(svg,s){
 clear(svg);if(!s.length)return;const c=scales(svg,s,"n"),max=Math.max(...s.map(p=>p.n),1);c.max=max;
 for(let i=0;i<=4;i++){const y=c.y(i*max/4);svg.append(el("line",{x1:c.L,x2:c.W-c.R,y1:y,y2:y,class:"grid"}));svg.append(el("text",{x:8,y:y+4},fmtInt(Math.round(i*max/4))))}
 const barW=Math.max(1,(c.W-c.L-c.R)/s.length);
 s.forEach(p=>{const x=c.x(new Date(p.t).getTime()),y=c.y(p.n);svg.append(el("rect",{x:x,y:y,width:Math.max(1,barW),height:c.H-c.B-y,class:"bar"}))});
 const step=Math.max(1,Math.floor(s.length/7));
 for(let i=0;i<s.length;i+=step){const p=s[i],x=c.x(new Date(p.t).getTime());svg.append(el("text",{x:x-18,y:c.H-12},fmtDate(p.t).slice(11,16)))}
}
setup();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    path = Path(args.input)
    output = Path(args.output)
    if not path.exists():
        raise SystemExit(f"Input not found: {path}")

    counts, totals = build_series(path)
    payload = prepare_payload(counts, totals)
    output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__UFS__", json.dumps(UFS))
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard: {output}")
    print(f"Sections: {totals['BR']:,}")
    print(f"UFs: {len(UFS)}")


if __name__ == "__main__":
    main()
