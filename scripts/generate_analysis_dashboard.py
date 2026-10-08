#!/usr/bin/env python3
"""Generate an analytical dashboard for BU emission vs reception timing."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

INPUT = Path("data/processed/votacao_presidencial_por_secao_2026.csv")
OUTPUT = Path("data/processed/dashboard_analise_emissao_recebimento_2026.html")
CHUNK = 100_000
CUTOFF = pd.Timestamp("2026-10-04 19:12:00")


def quantile(series: pd.Series, q: float) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return None if s.empty else float(s.quantile(q))


def compact_timeline(df: pd.DataFrame, freq: str = "1min") -> list[dict]:
    d = df.dropna(subset=["emissao", "recebido"]).copy()
    d["bin"] = d["recebido"].dt.floor(freq)
    g = d.groupby("bin", sort=True).agg(
        bu=("bin", "size"),
        flavio=("flavio", "sum"),
        lula=("lula", "sum"),
        emitidos=("emissao", "size"),
    ).reset_index()
    g["flavio_acum"] = g["flavio"].cumsum()
    g["lula_acum"] = g["lula"].cumsum()
    g["bu_acum"] = g["bu"].cumsum()
    g["margem"] = g["flavio_acum"] - g["lula_acum"]
    denom = g["flavio"] + g["lula"]
    g["share_f"] = np.where(denom > 0, g["flavio"] / denom * 100, np.nan)
    return [
        {
            "t": row.bin.strftime("%Y-%m-%dT%H:%M:%S"),
            "bu": int(row.bu),
            "emitidos": int(row.emitidos),
            "flavio": int(row.flavio),
            "lula": int(row.lula),
            "flavioAcum": int(row.flavio_acum),
            "lulaAcum": int(row.lula_acum),
            "buAcum": int(row.bu_acum),
            "margem": int(row.margem),
            "shareF": None if pd.isna(row.share_f) else round(float(row.share_f), 3),
        }
        for row in g.itertuples()
    ]


def stats(d: pd.DataFrame) -> dict:
    lag = d["lag_min"].dropna()
    return {
        "bu": int(len(d)),
        "flavio": int(d["flavio"].sum()),
        "lula": int(d["lula"].sum()),
        "shareF": round(float(d["flavio"].sum() / max(1, d["flavio"].sum() + d["lula"].sum()) * 100), 3),
        "lagMean": round(float(lag.mean()), 3) if not lag.empty else None,
        "lagMedian": round(float(lag.median()), 3) if not lag.empty else None,
        "lagP90": round(quantile(lag, .90), 3) if not lag.empty else None,
        "lagP95": round(quantile(lag, .95), 3) if not lag.empty else None,
    }


def main() -> None:
    required = [
        "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO",
        "DT_EMISSAO_BU", "HH_EMISSAO_BU",
        "DT_BU_RECEBIDO", "HH_BU_RECEBIDO",
        "VOTOS_FLAVIO_BOLSONARO", "VOTOS_LULA",
    ]
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        INPUT, sep=";", encoding="utf-8-sig", dtype=str,
        usecols=required, chunksize=CHUNK,
    ):
        for c in ["VOTOS_FLAVIO_BOLSONARO", "VOTOS_LULA"]:
            chunk[c] = pd.to_numeric(chunk[c], errors="coerce").fillna(0).astype("int64")
        chunk["emissao"] = pd.to_datetime(
            chunk["DT_EMISSAO_BU"].fillna("") + " " + chunk["HH_EMISSAO_BU"].fillna(""),
            errors="coerce", dayfirst=True,
        )
        chunk["recebido"] = pd.to_datetime(
            chunk["DT_BU_RECEBIDO"].fillna("") + " " + chunk["HH_BU_RECEBIDO"].fillna(""),
            errors="coerce", dayfirst=True,
        )
        chunk["flavio"] = chunk["VOTOS_FLAVIO_BOLSONARO"]
        chunk["lula"] = chunk["VOTOS_LULA"]
        chunk["lag_min"] = (chunk["recebido"] - chunk["emissao"]).dt.total_seconds() / 60
        frames.append(chunk[["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "emissao", "recebido", "flavio", "lula", "lag_min"]])

    df = pd.concat(frames, ignore_index=True)
    valid = df["emissao"].notna() & df["recebido"].notna()
    invalid = int((~valid).sum())
    d = df.loc[valid].copy()
    negative = int((d["lag_min"] < 0).sum())
    d = d.loc[d["lag_min"] >= 0].copy()

    d["cut"] = np.where(d["recebido"] <= CUTOFF, "Até 19:12", "Após 19:12")

    national = stats(d)
    pre = stats(d[d["recebido"] <= CUTOFF])
    post = stats(d[d["recebido"] > CUTOFF])

    # Exact national timeline. The date is retained, so 19:12 is a precise event.
    timeline = compact_timeline(d, "1min")

    # Emission and reception counts by 5-minute bin, used to show whether
    # emission activity predicts the later reception flow.
    e = d.copy()
    e["emissao_bin"] = e["emissao"].dt.floor("5min")
    e["recebido_bin"] = e["recebido"].dt.floor("5min")
    eb = e.groupby("emissao_bin").size().rename("emitidas")
    rb = e.groupby("recebido_bin").size().rename("recebidas")
    flow_idx = eb.index.union(rb.index).sort_values()
    flow = [
        {
            "t": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "emitidas": int(eb.get(ts, 0)),
            "recebidas": int(rb.get(ts, 0)),
        }
        for ts in flow_idx
    ]

    # Emission -> reception lag distribution.
    lag_bins = [0, 5, 10, 15, 30, 45, 60, 90, 120, 180, 240, 360, 720, np.inf]
    labels = ["0–5", "5–10", "10–15", "15–30", "30–45", "45–60", "60–90",
              "90–120", "120–180", "180–240", "240–360", "360–720", ">720"]
    d["lag_bucket"] = pd.cut(d["lag_min"], bins=lag_bins, labels=labels, right=False)
    lag_dist = [
        {"bucket": label, "count": int((d["lag_bucket"] == label).sum())}
        for label in labels
    ]

    # Lag by reception minute: mean/median/P90 and volume.
    lg = d.assign(bin=d["recebido"].dt.floor("5min")).groupby("bin").agg(
        bu=("lag_min", "size"),
        mediana=("lag_min", "median"),
        media=("lag_min", "mean"),
        p90=("lag_min", lambda s: s.quantile(.90)),
    ).reset_index()
    lag_timeline = [
        {
            "t": r.bin.strftime("%Y-%m-%dT%H:%M:%S"),
            "bu": int(r.bu),
            "mediana": round(float(r.mediana), 2),
            "media": round(float(r.media), 2),
            "p90": round(float(r.p90), 2),
        }
        for r in lg.itertuples()
    ]

    # 15-minute emission x reception matrix. This is a compact causal-order
    # diagnostic: the diagonal means near-immediate reception; cells below
    # the diagonal represent delay.
    d["e15"] = d["emissao"].dt.floor("15min")
    d["r15"] = d["recebido"].dt.floor("15min")
    matrix = (
        d.groupby(["e15", "r15"]).size()
        .reset_index(name="count")
        .sort_values(["e15", "r15"])
    )
    matrix_data = [
        {"e": r.e15.strftime("%H:%M"), "r": r.r15.strftime("%H:%M"), "count": int(r["count"])}
        for r in matrix.itertuples()
    ]

    # Correlation over every valid BU, not over aggregated bins.
    x = d["emissao"].astype("int64") / 60_000_000_000
    y = d["recebido"].astype("int64") / 60_000_000_000
    corr = float(np.corrcoef(x, y)[0, 1]) if len(d) > 1 else None

    # Deterministic scatter sample, retaining all observations in the
    # correlation calculation.
    sample_n = min(5000, len(d))
    sample = d.sort_values(["emissao", "recebido"]).iloc[
        np.linspace(0, len(d) - 1, sample_n, dtype=int)
    ]
    scatter = [
        {
            "x": r.emissao.strftime("%Y-%m-%dT%H:%M:%S"),
            "y": r.recebido.strftime("%Y-%m-%dT%H:%M:%S"),
            "lag": round(float(r.lag_min), 2),
        }
        for r in sample.itertuples()
    ]

    # UF comparison around the cut. This lets the dashboard test whether the
    # national pattern is broad or concentrated geographically.
    uf_rows = []
    for uf, g in d.groupby("SG_UF", sort=True):
        a = stats(g[g["recebido"] <= CUTOFF])
        b = stats(g[g["recebido"] > CUTOFF])
        uf_rows.append({
            "uf": uf,
            "preBU": a["bu"], "postBU": b["bu"],
            "preShareF": a["shareF"], "postShareF": b["shareF"],
            "deltaShareF": round(b["shareF"] - a["shareF"], 3),
            "preLag": a["lagMedian"], "postLag": b["lagMedian"],
            "deltaLag": round((b["lagMedian"] or 0) - (a["lagMedian"] or 0), 3),
        })

    # Municipality summary is intentionally aggregate, not row-level, so the
    # HTML remains practical to load in a browser.
    mun_rows = []
    for (uf, code, name), g in d.groupby(["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"], sort=True):
        a = stats(g[g["recebido"] <= CUTOFF])
        b = stats(g[g["recebido"] > CUTOFF])
        mun_rows.append({
            "uf": uf, "code": str(code), "name": str(name),
            "preBU": a["bu"], "postBU": b["bu"],
            "preShareF": a["shareF"], "postShareF": b["shareF"],
            "deltaShareF": round(b["shareF"] - a["shareF"], 3),
            "preLag": a["lagMedian"], "postLag": b["lagMedian"],
        })

    payload = {
        "cutoff": CUTOFF.strftime("%Y-%m-%dT%H:%M:%S"),
        "national": national,
        "pre": pre,
        "post": post,
        "integrity": {
            "rowsInput": int(len(df)),
            "rowsValid": int(len(d)),
            "invalidTimestamps": invalid,
            "negativeLag": negative,
            "correlationPearson": None if corr is None else round(corr, 6),
            "minEmission": d["emissao"].min().strftime("%Y-%m-%dT%H:%M:%S"),
            "maxReception": d["recebido"].max().strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "timeline": timeline,
        "flow": flow,
        "lagDistribution": lag_dist,
        "lagTimeline": lag_timeline,
        "matrix": matrix_data,
        "scatter": scatter,
        "ufs": uf_rows,
        "municipalities": mun_rows,
    }

    html = TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"dashboard: {OUTPUT}")
    print(f"rows={len(df):,} valid={len(d):,} invalid={invalid:,} negative_lag={negative:,}")
    print(f"pearson_emissao_recebimento={corr}")


TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Análise BU — Emissão × Recebimento — Eleições 2026</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#17212b;--muted:#65727f;--line:#d9e1e7;--shadow:0 6px 22px rgba(23,33,43,.08);--accent:#315f8f;--cut:#a33b3b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}.wrap{max-width:1550px;margin:auto;padding:22px}
header{margin-bottom:16px}h1{margin:0 0 5px;font-size:28px}.sub{color:var(--muted)}.note{font-size:12px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:17px;margin-bottom:15px}
.kpis{display:grid;grid-template-columns:repeat(6,minmax(130px,1fr));gap:10px}.kpi{border:1px solid var(--line);border-radius:10px;padding:11px}.kpi b{display:block;font-size:21px}.kpi span{color:var(--muted);font-size:11px}
.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.controls label{display:flex;flex-direction:column;gap:5px;font-weight:700}.controls select{min-width:170px;padding:8px;border:1px solid #cbd4dc;border-radius:8px;background:#fff}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:15px}.chartbox{height:390px}.wide{height:450px}
table{border-collapse:collapse;width:100%}th,td{padding:7px 9px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:right}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-size:12px}.scroll{overflow:auto;max-height:520px}
.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 8px;font-size:12px;margin:2px}.warning{background:#fff6f6;border-color:#e7b4b4}.ok{background:#f5fbf7;border-color:#b7ddc3}
.heat{border-collapse:separate;border-spacing:2px}.heat td,.heat th{padding:5px;text-align:center;font-size:11px}.heat td{border:0;border-radius:3px;min-width:52px}
@media(max-width:1050px){.kpis{grid-template-columns:repeat(3,1fr)}.grid2{grid-template-columns:1fr}}@media(max-width:600px){.wrap{padding:12px}.kpis{grid-template-columns:repeat(2,1fr)}h1{font-size:23px}}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Emissão × recebimento dos Boletins de Urna</h1>
<div class="sub">Análise nacional das BUs do 1º turno. O corte em <b>04/10/2026 19:12</b> representa o horário em que o acompanhamento público da apuração parou de atualizar; ele é um marco analítico, não uma hipótese causal.</div>
</header>

<section class="card">
<h2>O que estamos medindo</h2>
<p>Para cada BU, comparamos <b>quando o boletim foi emitido</b> com <b>quando ele foi recebido</b>. A diferença entre os dois timestamps é o <b>tempo de transmissão/recepção observado no arquivo</b>. A correlação mede associação temporal; ela não prova causalidade.</p>
<div id="integrity"></div>
</section>

<section class="card">
<h2>Resumo antes × depois de 19:12</h2>
<div id="kpis" class="kpis"></div>
</section>

<section class="card">
<h2>Fluxo temporal</h2>
<div class="note">As séries de emissão e recebimento são contagens de BUs em janelas de 5 minutos. A linha vertical de 19:12 é o corte analítico.</div>
<div class="chartbox wide"><canvas id="flow"></canvas></div>
</section>

<section class="card">
<h2>Curva de votos recebidos</h2>
<div class="note">A curva acumula os votos das BUs pelo horário em que elas foram recebidas. A margem mostra Flávio − Lula.</div>
<div class="chartbox wide"><canvas id="votes"></canvas></div>
</section>

<section class="grid2">
<div class="card"><h2>Tempo emissão → recebimento</h2><div class="chartbox"><canvas id="lag"></canvas></div></div>
<div class="card"><h2>Latência por horário de recebimento</h2><div class="chartbox"><canvas id="lagTime"></canvas></div></div>
</section>

<section class="card">
<h2>Existe correlação entre emissão e recebimento?</h2>
<div class="sub">O coeficiente abaixo é calculado sobre todas as BUs válidas. O gráfico mostra uma amostra determinística apenas para visualização; a estatística não usa a amostra.</div>
<div id="corr" style="font-size:30px;font-weight:800;margin:12px 0"></div>
<div class="chartbox wide"><canvas id="scatter"></canvas></div>
</section>

<section class="card">
<h2>Mapa temporal da transmissão</h2>
<div class="sub">Cada célula mostra quantas BUs foram emitidas no intervalo da linha e recebidas no intervalo da coluna. Valores abaixo da diagonal indicam atraso entre emissão e recepção.</div>
<div class="scroll"><div id="heatmap"></div></div>
</section>

<section class="card">
<h2>Onde a mudança de composição aparece?</h2>
<div class="controls"><label>UF<select id="uf"><option value="">Brasil</option></select></label><label>Município<select id="mun"><option value="">Todos</option></select></label></div>
<div class="scroll"><table id="geoTable"></table></div>
</section>

<section class="card">
<h2>Leitura analítica</h2>
<ul>
<li><b>Emissão não é recebimento.</b> O horário de emissão registra quando o BU foi produzido; o horário de recebimento registra quando ele entrou no fluxo observado.</li>
<li><b>19:12 deve ser tratado como marco do sistema de divulgação.</b> Uma mudança de composição posterior pode coexistir com uma mudança no fluxo de recepção, mas o corte isoladamente não demonstra que uma coisa causou a outra.</li>
<li><b>A pergunta central é temporal:</b> BUs emitidas antes do corte foram recebidas depois? Se sim, o atraso de transmissão pode fazer o relógio de recebimento contar uma história diferente do relógio de emissão.</li>
<li><b>A correlação global precisa ser acompanhada pela distribuição de latência.</b> Mesmo uma correlação alta pode coexistir com uma cauda longa de BUs recebidas muito depois da emissão.</li>
</ul>
</section>

<footer class="note">Fonte: dados de Boletim de Urna do TSE processados pelo projeto. Esta página apresenta análises derivadas e não substitui a divulgação oficial.</footer>
</div>
<script>
const D=__PAYLOAD__;
const CUT=new Date(D.cutoff);
const fmt=n=>new Intl.NumberFormat('pt-BR').format(n);
const pct=n=>n==null?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+'%';
const min=n=>n==null?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+' min';
const common={responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom'}}};
function cutPlugin(){return{ id:'cutoff', afterDraw(c){const x=c.scales.x;if(!x)return;const px=x.getPixelForValue(CUT);if(px<x.left||px>x.right)return;const ctx=c.ctx;ctx.save();ctx.strokeStyle='#a33b3b';ctx.setLineDash([6,5]);ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(px,c.chartArea.top);ctx.lineTo(px,c.chartArea.bottom);ctx.stroke();ctx.fillStyle='#a33b3b';ctx.font='11px Segoe UI';ctx.fillText('19:12',px+5,c.chartArea.top+14);ctx.restore()}}}
function labels(a){return a.map(x=>new Date(x.t).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}))}
function renderKPIs(){
 const cards=[
 ['BUs até 19:12',D.pre.bu],['BUs após 19:12',D.post.bu],
 ['Flávio até',D.pre.flavio],['Flávio após',D.post.flavio],
 ['Lula até',D.pre.lula],['Lula após',D.post.lula],
 ['Share Flávio até',pct(D.pre.shareF)],['Share Flávio após',pct(D.post.shareF)],
 ['Latência mediana até',min(D.pre.lagMedian)],['Latência mediana após',min(D.post.lagMedian)],
 ['Latência P90 até',min(D.pre.lagP90)],['Latência P90 após',min(D.post.lagP90)]
 ];
 document.getElementById('kpis').innerHTML=cards.map(x=>'<div class="kpi"><span>'+x[0]+'</span><b>'+x[1].toLocaleString?fmt(x[1]):x[1]+'</b></div>').join('');
}
document.getElementById('integrity').innerHTML=
 '<span class="badge ok">BUs válidas: '+fmt(D.integrity.rowsValid)+'</span>'+
 '<span class="badge '+(D.integrity.invalidTimestamps?'warning':'ok')+'">timestamps inválidos: '+fmt(D.integrity.invalidTimestamps)+'</span>'+
 '<span class="badge '+(D.integrity.negativeLag?'warning':'ok')+'">latências negativas: '+fmt(D.integrity.negativeLag)+'</span>'+
 '<span class="badge">Pearson emissão × recebimento: '+D.integrity.correlationPearson+'</span>';
renderKPIs();

new Chart(document.getElementById('flow'),{type:'line',data:{labels:labels(D.flow),datasets:[
 {label:'BUs emitidas',data:D.flow.map(x=>x.emitidas),borderWidth:2,tension:.15},
 {label:'BUs recebidas',data:D.flow.map(x=>x.recebidas),borderWidth:2,tension:.15}
]},options:{...common,scales:{y:{beginAtZero:true,title:{display:true,text:'BUs / 5 min'}},x:{ticks:{maxTicksLimit:18}}}},plugins:[cutPlugin()]});

new Chart(document.getElementById('votes'),{type:'line',data:{labels:labels(D.timeline),datasets:[
 {label:'Flávio acumulado',data:D.timeline.map(x=>x.flavioAcum),borderWidth:2,tension:.12,yAxisID:'v'},
 {label:'Lula acumulado',data:D.timeline.map(x=>x.lulaAcum),borderWidth:2,tension:.12,yAxisID:'v'},
 {label:'Margem Flávio − Lula',data:D.timeline.map(x=>x.margem),borderWidth:2,borderDash:[6,4],tension:.12,yAxisID:'m'}
]},options:{...common,scales:{v:{position:'left',title:{display:true,text:'Votos acumulados'}},m:{position:'right',title:{display:true,text:'Margem'},grid:{drawOnChartArea:false}},x:{ticks:{maxTicksLimit:18}}}},plugins:[cutPlugin()]});

new Chart(document.getElementById('lag'),{type:'bar',data:{labels:D.lagDistribution.map(x=>x.bucket+' min'),datasets:[{label:'BUs',data:D.lagDistribution.map(x=>x.count)}]},options:{...common,scales:{y:{beginAtZero:true,title:{display:true,text:'BUs'}},x:{title:{display:true,text:'Atraso entre emissão e recebimento'}}}}});
new Chart(document.getElementById('lagTime'),{type:'line',data:{labels:labels(D.lagTimeline),datasets:[
 {label:'Mediana',data:D.lagTimeline.map(x=>x.mediana),borderWidth:2,tension:.15},
 {label:'P90',data:D.lagTimeline.map(x=>x.p90),borderWidth:2,tension:.15},
 {label:'Média',data:D.lagTimeline.map(x=>x.media),borderWidth:1,borderDash:[4,4],tension:.15}
]},options:{...common,scales:{y:{beginAtZero:true,title:{display:true,text:'Minutos'}},x:{ticks:{maxTicksLimit:18}}}},plugins:[cutPlugin()]});

document.getElementById('corr').textContent='Pearson = '+D.integrity.correlationPearson;
new Chart(document.getElementById('scatter'),{type:'scatter',data:{datasets:[{label:'BUs (amostra visual)',data:D.scatter.map(x=>({x:new Date(x.x),y:new Date(x.y)})),pointRadius:2,pointHoverRadius:4}]},options:{...common,scales:{x:{type:'time',time:{unit:'hour'},title:{display:true,text:'Emissão'}},y:{type:'time',time:{unit:'hour'},title:{display:true,text:'Recebimento'}}}},plugins:[cutPlugin()]});

const times=[...new Set(D.matrix.flatMap(x=>[x.e,x.r]))].sort();
const map=new Map(D.matrix.map(x=>[x.e+'|'+x.r,x.count]));
const max=Math.max(...D.matrix.map(x=>x.count),1);
document.getElementById('heatmap').innerHTML='<table class="heat"><tr><th>Emissão \\ Receb.</th>'+times.map(t=>'<th>'+t+'</th>').join('')+'</tr>'+
times.map(e=>'<tr><th>'+e+'</th>'+times.map(r=>{const v=map.get(e+'|'+r)||0;const a=Math.round(18+70*v/max);return '<td style="background:rgba(49,95,143,'+(a/100)+');color:'+(v/max>.45?'#fff':'#17212b')+'">'+(v?fmt(v):'')+'</td>'}).join('')+'</tr>').join('')+'</table>';

const uf=document.getElementById('uf'),mun=document.getElementById('mun');
[...new Set(D.municipalities.map(x=>x.uf))].sort().forEach(x=>uf.insertAdjacentHTML('beforeend','<option>'+x+'</option>'));
function fillMun(){
 const selected=uf.value;const rows=D.municipalities.filter(x=>!selected||x.uf===selected);
 mun.innerHTML='<option value="">Todos</option>'+rows.sort((a,b)=>a.name.localeCompare(b.name,'pt-BR')).map(x=>'<option value="'+x.code+'">'+x.name+'</option>').join('');
}
function geo(){
 const selectedUF=uf.value, selectedMun=mun.value;
 let rows;
 if(selectedMun) rows=D.municipalities.filter(x=>x.uf===selectedUF&&x.code===selectedMun);
 else if(selectedUF) rows=D.municipalities.filter(x=>x.uf===selectedUF);
 else rows=D.ufs;
 if(rows===D.ufs||rows.length>50){
   rows=[...rows].sort((a,b)=>a.deltaShareF-b.deltaShareF).slice(0,50);
 }
 document.getElementById('geoTable').innerHTML='<thead><tr><th>UF</th><th>Município</th><th>BUs ≤19:12</th><th>BUs >19:12</th><th>Flávio % ≤</th><th>Flávio % ></th><th>Δ p.p.</th><th>Latência mediana ≤</th><th>Latência mediana ></th></tr></thead><tbody>'+
 rows.map(r=>'<tr><td>'+r.uf+'</td><td>'+((r.name)||'Brasil/UF')+'</td><td>'+fmt(r.preBU)+'</td><td>'+fmt(r.postBU)+'</td><td>'+pct(r.preShareF)+'</td><td>'+pct(r.postShareF)+'</td><td>'+r.deltaShareF.toLocaleString('pt-BR',{minimumFractionDigits:2})+'</td><td>'+min(r.preLag)+'</td><td>'+min(r.postLag)+'</td></tr>').join('')+'</tbody>';
}
uf.onchange=()=>{fillMun();geo()};mun.onchange=geo;fillMun();geo();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
