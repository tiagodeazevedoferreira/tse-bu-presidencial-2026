#!/usr/bin/env python3
"""Generate the standalone BU issue/reception hourly dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO",
]
INPUT = Path("data/processed/votacao_presidencial_por_secao_2026.csv")
DEFAULT_OUTPUT = Path("data/processed/dashboard_timeline_recebimento_bu_2026.html")
CHUNK_SIZE = 100_000
EVENT_FIELDS = {
    "DT_EMISSAO_BU": "BU Emitido",
    "DT_BU_RECEBIDO": "BU Recebido",
}
VOTE_FIELDS = [
    "VOTOS_FLAVIO_BOLSONARO",
    "VOTOS_LULA",
    "VOTOS_BRANCO_PRES",
    "VOTOS_NULO_PRES",
]
ALL_FIELDS = VOTE_FIELDS + ["TOTAL_PRESIDENTE"]


def detect_separator(path: Path) -> str:
    """Support both the repository's semicolon CSV and tab-separated CSVs."""
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        header = handle.readline()
    if "\t" in header:
        return "\t"
    return ";"


def combine_timestamp(date_series: pd.Series, time_series: pd.Series, field: str) -> pd.Series:
    """Combine correlated date/time columns into a full timestamp.

    Missing pairs are ignored. Non-empty malformed pairs are rejected so a
    bad source value cannot silently move a BU to another hour.
    """
    date_text = date_series.fillna("").astype(str).str.strip()
    time_text = time_series.fillna("").astype(str).str.strip()
    combined = date_text.where(date_text.eq(""), date_text + " " + time_text)
    parsed = pd.to_datetime(combined, errors="coerce", dayfirst=True)
    missing_pair = date_text.eq("") | time_text.eq("")
    invalid = (~missing_pair) & parsed.isna()
    if invalid.any():
        bad = list(zip(date_series.loc[invalid].head(5), time_series.loc[invalid].head(5)))
        raise ValueError(f"{field} + HH inválido. Exemplos: {bad}")
    return parsed


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")


def build_analysis_data(path: Path) -> dict:
    usecols = [
        "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO",
        "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO",
        "DT_EMISSAO_BU", "HH_EMISSAO_BU",
        "DT_BU_RECEBIDO", "HH_BU_RECEBIDO",
        *VOTE_FIELDS,
    ]
    hours = {event: [] for event in EVENT_FIELDS}
    municipalities = {uf: {} for uf in UFS}
    vote_totals = {}
    min_ts = None
    max_ts = None
    sep = detect_separator(path)

    for chunk in pd.read_csv(
        path, sep=sep, encoding="utf-8-sig", dtype=str,
        usecols=usecols, chunksize=CHUNK_SIZE,
    ):
        bad_ufs = sorted(set(chunk["SG_UF"].dropna()) - set(UFS))
        if bad_ufs:
            raise ValueError(f"UF inesperada no nacional: {bad_ufs}")

        for uf, group in chunk.groupby("SG_UF", sort=False):
            for code, name in group[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates().itertuples(index=False):
                if pd.notna(code):
                    municipalities[uf][str(code)] = "" if pd.isna(name) else str(name)

        for col in VOTE_FIELDS:
            chunk[col] = numeric(chunk[col])
        chunk["TOTAL_PRESIDENTE"] = chunk["VOTOS_FLAVIO_BOLSONARO"] + chunk["VOTOS_LULA"]

        for (uf, mun), group in chunk.groupby(["SG_UF", "CD_MUNICIPIO"], dropna=False, sort=False):
            key = f"{uf}|{mun}"
            vals = vote_totals.setdefault(key, [0, 0, 0, 0, 0])
            vals[0] += int(group["VOTOS_FLAVIO_BOLSONARO"].sum())
            vals[1] += int(group["VOTOS_LULA"].sum())
            vals[2] += int(group["VOTOS_BRANCO_PRES"].sum())
            vals[3] += int(group["VOTOS_NULO_PRES"].sum())
            vals[4] += int(group["TOTAL_PRESIDENTE"].sum())

        timestamps = {
            "DT_EMISSAO_BU": combine_timestamp(
                chunk["DT_EMISSAO_BU"], chunk["HH_EMISSAO_BU"], "DT_EMISSAO_BU"
            ),
            "DT_BU_RECEBIDO": combine_timestamp(
                chunk["DT_BU_RECEBIDO"], chunk["HH_BU_RECEBIDO"], "DT_BU_RECEBIDO"
            ),
        }
        for event, ts in timestamps.items():
            valid = ts.notna()
            if not valid.any():
                continue
            work = chunk.loc[valid, ["SG_UF", "CD_MUNICIPIO", *VOTE_FIELDS]].copy()
            work["timestamp"] = ts.loc[valid].dt.floor("h")
            work["TOTAL_PRESIDENTE"] = work["VOTOS_FLAVIO_BOLSONARO"] + work["VOTOS_LULA"]
            grouped = work.groupby(["SG_UF", "CD_MUNICIPIO", "timestamp"], dropna=False).agg(
                count=("timestamp", "size"),
                flavio=("VOTOS_FLAVIO_BOLSONARO", "sum"),
                lula=("VOTOS_LULA", "sum"),
                branco=("VOTOS_BRANCO_PRES", "sum"),
                nulo=("VOTOS_NULO_PRES", "sum"),
                total=("TOTAL_PRESIDENTE", "sum"),
            ).reset_index()
            for row in grouped.itertuples(index=False):
                stamp = row.timestamp.strftime("%Y-%m-%dT%H:00:00")
                hours[event].append([
                    str(row.SG_UF), str(row.CD_MUNICIPIO), stamp,
                    int(row.count), int(row.flavio), int(row.lula),
                    int(row.branco), int(row.nulo), int(row.total),
                ])
            local_min, local_max = ts.min(), ts.max()
            min_ts = local_min if min_ts is None or local_min < min_ts else min_ts
            max_ts = local_max if max_ts is None or local_max > max_ts else max_ts

    # Chunks are disjoint in source rows but a municipality/hour can span chunks.
    # Re-aggregate the compact hourly rows to prevent duplicate points.
    compact = {}
    for event, rows in hours.items():
        acc = {}
        for uf, mun, stamp, count, vf, vl, vb, vn, total in rows:
            key = (uf, mun, stamp)
            item = acc.setdefault(key, [0, 0, 0, 0, 0, 0])
            item[0] += count
            item[1] += vf
            item[2] += vl
            item[3] += vb
            item[4] += vn
            item[5] += total
        compact[event] = [
            [uf, mun, stamp, *values] for (uf, mun, stamp), values in sorted(acc.items())
        ]

    return {
        "hours": compact,
        "municipalities": {
            uf: [{"code": code, "name": name}
                 for code, name in sorted(values.items(), key=lambda x: x[1])]
            for uf, values in municipalities.items()
        },
        "vote_totals": vote_totals,
        "range": [
            None if min_ts is None else min_ts.strftime("%Y-%m-%dT%H:00:00"),
            None if max_ts is None else max_ts.strftime("%Y-%m-%dT%H:00:00"),
        ],
    }


def prepare_analysis_payload(data: dict) -> dict:
    return data


HTML_TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recebimento de Boletins de Urna — Eleições 2026</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#18212b;--muted:#65727f;--line:#dce3e9;--shadow:0 8px 26px rgba(24,33,43,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}.wrap{max-width:1500px;margin:auto;padding:24px}
.hero{margin-bottom:18px}h1{font-size:29px;margin:0 0 6px}.sub,.note{color:var(--muted)}.note{font-size:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:18px;margin-bottom:16px}
.toolbar{display:flex;gap:14px;align-items:end;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:16px;box-shadow:var(--shadow)}
label{display:flex;flex-direction:column;gap:5px;font-weight:700}select,input{min-width:210px;padding:9px;border:1px solid #cbd4dc;border-radius:8px;background:#fff;font:inherit}.cutoff{min-width:130px}
.kpis{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}.kpi{min-width:170px;padding:13px 15px;border:1px solid var(--line);border-radius:10px;background:#fbfcfd}.kpi .name{font-size:12px;color:var(--muted)}.kpi .value{font-size:23px;font-weight:750;font-variant-numeric:tabular-nums;margin-top:2px}
.controls{display:grid;grid-template-columns:1fr 2fr;gap:20px;margin-top:14px}.group{display:flex;gap:16px;flex-wrap:wrap}.check{display:inline-flex;flex-direction:row;align-items:center;gap:7px;font-weight:600}.check input{min-width:auto;padding:0}
.chart-wrap{overflow:auto}.chart{width:100%;min-width:1000px;height:650px}.legend{display:flex;gap:15px;flex-wrap:wrap;margin-top:8px;color:var(--muted);font-size:12px}.legend i{display:inline-block;width:22px;height:3px;margin-right:5px;vertical-align:middle}
table{border-collapse:collapse;width:100%}.data-table{min-width:850px}.table-wrap{overflow:auto;margin-top:12px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}th{font-size:12px;color:var(--muted)}td{font-variant-numeric:tabular-nums}.num{text-align:right}
@media(max-width:850px){.wrap{padding:14px}.controls{grid-template-columns:1fr}h1{font-size:24px}}
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
<h1>Recebimento acumulado de Boletins de Urna</h1>
<div class="sub">Emissão e recebimento são eventos independentes. Os timestamps são formados exclusivamente por <b>DT_EMISSAO_BU + HH_EMISSAO_BU</b> e <b>DT_BU_RECEBIDO + HH_BU_RECEBIDO</b>. <b>DT_ENCERRAMENTO</b> e <b>HH_ENCERRAMENTO</b> não são utilizados.</div>
</header>

<div class="toolbar">
<label>UF<select id="uf"></select></label>
<label>Município<select id="municipio"></select></label>
<label class="cutoff">Horário de corte<input id="cutoff" type="text" value="19:12" maxlength="5" inputmode="numeric" pattern="[0-9]{2}:[0-9]{2}"></label>
</div>

<section class="card">
<h2>KPIs</h2>
<div class="sub">Os KPIs respeitam UF e município e aparecem somente para as métricas marcadas abaixo.</div>
<div id="kpis" class="kpis"></div>
</section>

<section class="card">
<h2>Controles do gráfico</h2>
<div class="controls">
<div><b>Eventos</b><div class="group">
<label class="check"><input id="eventEmitido" type="checkbox" checked> BU Emitido</label>
<label class="check"><input id="eventRecebido" type="checkbox" checked> BU Recebido</label>
</div></div>
<div><b>Métricas de votos</b><div class="group">
<label class="check"><input class="metric" data-m="VOTOS_FLAVIO_BOLSONARO" type="checkbox" checked> Votos Flávio Bolsonaro</label>
<label class="check"><input class="metric" data-m="VOTOS_LULA" type="checkbox" checked> Votos Lula</label>
<label class="check"><input class="metric" data-m="VOTOS_BRANCO_PRES" type="checkbox"> Votos Brancos</label>
<label class="check"><input class="metric" data-m="VOTOS_NULO_PRES" type="checkbox"> Votos Nulos</label>
<label class="check"><input class="metric" data-m="TOTAL_PRESIDENTE" type="checkbox" checked> Total Presidente</label>
</div></div>
</div>
</section>

<section class="card">
<h2>Emissão × recebimento × votos por hora</h2>
<div class="sub">Cada ponto representa uma hora cheia. A série de BUs usa o eixo esquerdo; as métricas de votos usam o eixo direito. O eixo temporal é contínuo e preserva a mudança de dia.</div>
<div class="chart-wrap"><svg id="chart" class="chart" viewBox="0 0 1400 650" preserveAspectRatio="none"></svg></div>
<div id="legend" class="legend"></div>
<div class="note">A linha vertical tracejada representa o horário informado em <b>04/10/2026</b>. O tooltip de cada ponto informa data, hora, evento, quantidade de BUs, métrica e valor.</div>
</section>

<section class="card">
<h2>Dados agregados por hora</h2>
<div class="table-wrap"><table class="data-table"><thead><tr><th>Data</th><th>Hora</th><th>Evento</th><th class="num">BUs</th><th>Métrica</th><th class="num">Valor</th></tr></thead><tbody id="detail"></tbody></table></div>
</section>
</div>
<script>
const DATA=__DATA__;
const UFS=__UFS__;
const METRICS={
 VOTOS_FLAVIO_BOLSONARO:"Votos Flávio Bolsonaro",
 VOTOS_LULA:"Votos Lula",
 VOTOS_BRANCO_PRES:"Votos Brancos",
 VOTOS_NULO_PRES:"Votos Nulos",
 TOTAL_PRESIDENTE:"Total Presidente"
};
const EVENTS={DT_EMISSAO_BU:"BU Emitido",DT_BU_RECEBIDO:"BU Recebido"};
const EVENT_KEYS=["DT_EMISSAO_BU","DT_BU_RECEBIDO"];
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat("pt-BR").format(n);
const pad=n=>String(n).padStart(2,"0");
const cutoffDate="2026-10-04";
const cutoffInput=()=>{const v=$("cutoff").value.trim();return /^([01]\d|2[0-3]):[0-5]\d$/.test(v)?v:null};
function esc(v){return String(v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}
function selectedMetrics(){return [...document.querySelectorAll(".metric:checked")].map(x=>x.dataset.m)}
function selectedEvents(){return EVENT_KEYS.filter((e,i)=>$(i?"eventRecebido":"eventEmitido").checked)}
function populateUF(){ $("uf").innerHTML='<option value="BR">Total</option>'+UFS.map(u=>'<option>'+u+'</option>').join("");$("uf").onchange=()=>{populateMunicipios();render()}; }
function populateMunicipios(){
 const uf=$("uf").value, list=uf==="BR"?Object.values(DATA.municipalities).flat():[...(DATA.municipalities[uf]||[])];
 const uniq=new Map(list.map(x=>[x.code,x.name]));
 $("municipio").innerHTML='<option value="ALL">Todos</option>'+[...uniq.entries()].sort((a,b)=>a[1].localeCompare(b[1],"pt-BR")).map(x=>'<option value="'+esc(x[0])+'">'+esc(x[1])+'</option>').join("");
 $("municipio").disabled=false;
}
function activeKeys(){
 const uf=$("uf").value,mun=$("municipio").value;
 return new Set(Object.entries(DATA.municipalities).flatMap(([u,list])=>list.filter(x=>(uf==="BR"||u===uf)&&(mun==="ALL"||x.code===mun)).map(x=>u+"|"+x.code));
}
function aggregate(){
 const keys=activeKeys(), out={};
 for(const event of selectedEvents()){
  const acc={};
  for(const r of DATA.hours[event]||[]){
   if(!keys.has(r[0]+"|"+r[1]))continue;
   const a=acc[r[2]]||(acc[r[2]]={count:0,vals:{VOTOS_FLAVIO_BOLSONARO:0,VOTOS_LULA:0,VOTOS_BRANCO_PRES:0,VOTOS_NULO_PRES:0,TOTAL_PRESIDENTE:0}});
   a.count+=r[3];a.vals.VOTOS_FLAVIO_BOLSONARO+=r[4];a.vals.VOTOS_LULA+=r[5];a.vals.VOTOS_BRANCO_PRES+=r[6];a.vals.VOTOS_NULO_PRES+=r[7];a.vals.TOTAL_PRESIDENTE+=r[8];
  }
  out[event]=acc;
 }
 return out;
}
function kpiTotals(){
 const keys=activeKeys(),v=[0,0,0,0,0];
 for(const [key,vals] of Object.entries(DATA.vote_totals)){if(keys.has(key)){for(let i=0;i<5;i++)v[i]+=vals[i]}}
 return v;
}
function drawKPIs(){
 const vals=kpiTotals(), ms=selectedMetrics();
 $("kpis").innerHTML=ms.map(m=>'<div class="kpi"><div class="name">'+METRICS[m]+'</div><div class="value">'+fmt(vals[["VOTOS_FLAVIO_BOLSONARO","VOTOS_LULA","VOTOS_BRANCO_PRES","VOTOS_NULO_PRES","TOTAL_PRESIDENTE"].indexOf(m)])+'</div></div>').join("")||'<div class="note">Selecione ao menos uma métrica.</div>';
}
function render(){
 drawKPIs();drawChart();
}
function parseDate(s){return new Date(s+"Z")}
function range(agg){
 const all=selectedEvents().flatMap(e=>Object.keys(agg[e]||{})).sort();
 if(!all.length)return [new Date(cutoffDate+"T00:00:00Z"),new Date(cutoffDate+"T23:00:00Z")];
 return [parseDate(all[0]),parseDate(all[all.length-1])];
}
function aggregateAll(event){const o={};for(const r of DATA.hours[event]||[]){const a=o[r[2]]||(o[r[2]]={count:0});a.count+=r[3]}return o}
function drawChart(){
 const svg=$("chart");svg.innerHTML="";const agg=aggregate(),metrics=selectedMetrics(),events=selectedEvents(),[minD,maxD]=range(agg);
 const W=1400,H=650,L=75,R=78,T=42,B=72,pw=W-L-R,ph=H-T-B;
 const points=[];for(const e of events)for(const t of Object.keys(agg[e]||{}))points.push({t,e});
 for(const e of events)for(const t of Object.keys(agg[e]||{}))for(const m of metrics)points.push({t,e,m});
 let min=minD.getTime(),max=maxD.getTime();if(max<=min)max=min+3600000;
 const cutoff=Date.parse(cutoffDate+"T"+(cutoffInput()||"19:12")+":00Z");
 const x=t=>L+(t-min)/(max-min)*pw;
 const valsBU=events.flatMap(e=>Object.values(agg[e]||{}).map(x=>x.count));
 const valsV=events.flatMap(e=>Object.values(agg[e]||{}).flatMap(x=>metrics.map(m=>x.vals[m])));
 const maxBU=Math.max(...valsBU,1),maxV=Math.max(...valsV,1);
 const yBU=v=>T+ph-v/maxBU*ph,yV=v=>T+ph-v/maxV*ph;
 const el=(tag,a,text)=>{const n=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.entries(a||{}).forEach(([k,v])=>n.setAttribute(k,v));if(text!=null)n.textContent=text;return n};
 svg.append(el("rect",{x:L,y:T,width:pw,height:ph,fill:"#fff"}));
 for(let i=0;i<=5;i++){const yy=T+ph*i/5;svg.append(el("line",{x1:L,x2:W-R,y1:yy,y2:yy,stroke:"#e5e9ed"}));svg.append(el("text",{x:L-10,y:yy+4,"text-anchor":"end",fill:"#65727f","font-size":"11"},fmt(Math.round(maxBU*(5-i)/5)));svg.append(el("text",{x:W-R+10,y:yy+4,fill:"#65727f","font-size":"11"},fmt(Math.round(maxV*(5-i)/5)));}
 const lineX=x(cutoff);if(cutoff>=min&&cutoff<=max){svg.append(el("line",{x1:lineX,x2:lineX,y1:T-5,y2:T+ph,stroke:"#222","stroke-width":"2","stroke-dasharray":"7 5"}));svg.append(el("text",{x:Math.min(W-R-55,Math.max(L+55,lineX)),y:22,"text-anchor":"middle","font-size":"12","font-weight":"700",fill:"#222"},"Corte 04/10 "+(cutoffInput()||"19:12")))}
 const colors=["#1769aa","#d97706","#7c3aed","#059669","#dc2626"];
 let ci=0;
 for(const e of events){
  const color=e==="DT_EMISSAO_BU"?"#1769aa":"#d97706";
  const rows=Object.entries(agg[e]||{}).sort((a,b)=>a[0].localeCompare(b[0]));
  let d="";rows.forEach(([t,a],i)=>{d+=(i?" L":"M")+x(parseDate(t).getTime())+" "+yBU(a.count)});
  if(d){svg.append(el("path",{d,fill:"none",stroke:color,"stroke-width":"3"}));rows.forEach(([t,a])=>{const c=el("circle",{cx:x(parseDate(t).getTime()),cy:yBU(a.count),r:"4",fill:color});const title=el("title",{},new Date(t+"Z").toLocaleString("pt-BR",{timeZone:"UTC",dateStyle:"short",timeStyle:"short"})+" • "+EVENTS[e]+" • "+fmt(a.count)+" BUs");c.append(title);svg.append(c)})}
  for(const m of metrics){
   const color=colors[ci++%colors.length], r=rows.filter(x=>x[1].vals[m]!=null);let path="";r.forEach(([t,a],i)=>{path+=(i?" L":"M")+x(parseDate(t).getTime())+" "+yV(a.vals[m])});
   if(path){svg.append(el("path",{d:path,fill:"none",stroke:color,"stroke-width":"2"}));r.forEach(([t,a])=>{const c=el("circle",{cx:x(parseDate(t).getTime()),cy:yV(a.vals[m]),r:"3",fill:color});c.append(el("title",{},new Date(t+"Z").toLocaleString("pt-BR",{timeZone:"UTC",dateStyle:"short",timeStyle:"short"})+" • "+EVENTS[e]+" • "+METRICS[m]+" • "+fmt(a.vals[m])));svg.append(c)})}
  }
 }
 const ticks=Math.min(12,Math.max(2,Math.floor((max-min)/3600000)+1));for(let i=0;i<ticks;i++){const t=min+(max-min)*i/(ticks-1),xx=x(t);svg.append(el("line",{x1:xx,x2:xx,y1:T+ph,y2:T+ph+6,stroke:"#9aa6b2"}));svg.append(el("text",{x:xx,y:H-35,"text-anchor":"middle","font-size":"11",fill:"#4d5965"},new Date(t).toLocaleString("pt-BR",{timeZone:"UTC",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})));}
 svg.append(el("text",{x:L,y:16,"font-size":"12","font-weight":"700",fill:"#1769aa"},"BUs"));svg.append(el("text",{x:W-R,y:16,"text-anchor":"end","font-size":"12","font-weight":"700",fill:"#7c3aed"},"Votos"));
 const legend=[];events.forEach(e=>legend.push('<span><i style="background:'+(e==="DT_EMISSAO_BU"?"#1769aa":"#d97706")+'"></i>'+EVENTS[e]+' (BUs)</span>'));metrics.forEach((m,i)=>events.forEach(e=>legend.push('<span><i style="background:'+colors[i%colors.length]+'"></i>'+EVENTS[e]+" × "+METRICS[m]+"</span>")));
 $("legend").innerHTML=legend.join("");
 drawDetail(agg,metrics);
}
function drawDetail(agg,metrics){
 const rows=[];for(const e of selectedEvents())for(const [t,a] of Object.entries(agg[e]||{}).sort())for(const m of metrics)rows.push('<tr><td>'+new Date(t+"Z").toLocaleDateString("pt-BR",{timeZone:"UTC"})+'</td><td>'+new Date(t+"Z").toLocaleTimeString("pt-BR",{timeZone:"UTC",hour:"2-digit",minute:"2-digit"})+'</td><td>'+EVENTS[e]+'</td><td class="num">'+fmt(a.count)+'</td><td>'+METRICS[m]+'</td><td class="num">'+fmt(a.vals[m])+'</td></tr>');
 $("detail").innerHTML=rows.join("")||'<tr><td colspan="6" class="note">Nenhum dado para os filtros selecionados.</td></tr>';
}
function validateCutoff(){const v=cutoffInput();if(v==null){$("cutoff").setCustomValidity("Use HH:MM, por exemplo 19:12.");$("cutoff").reportValidity();return false}$("cutoff").setCustomValidity("");return true}
$("cutoff").addEventListener("input",()=>{if(validateCutoff())render()});
$("municipio").addEventListener("change",render);
document.querySelectorAll(".metric,#eventEmitido,#eventRecebido").forEach(x=>x.addEventListener("change",render));
populateUF();populateMunicipios();render();
</script>
</body>
</html>
"""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    path, output = Path(args.input), Path(args.output)
    if not path.exists():
        raise SystemExit(f"Input not found: {path}")
    payload = prepare_analysis_payload(build_analysis_data(path))
    output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__UFS__", json.dumps(UFS))
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard: {output}")

if __name__ == "__main__":
    main()
