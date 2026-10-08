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
EVENT_FIELDS = {
    "DT_ENCERRAMENTO": "Encerramento",
    "DT_EMISSAO_BU": "Emissão do BU",
    "DT_BU_RECEBIDO": "BU recebido",
}
TIME_FIELDS = list(EVENT_FIELDS)
VOTE_FIELDS = [
    "VOTOS_FLAVIO_BOLSONARO",
    "VOTOS_LULA",
    "TOTAL_VOTOS_PRES",
]
SECTION_FIELDS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_SECAO",
    "NR_LOCAL_VOTACAO", *TIME_FIELDS, *VOTE_FIELDS,
]


def parse_time_minutes(series: pd.Series, field: str) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    invalid = text.ne("") & parsed.isna()
    if invalid.any():
        bad = series.loc[invalid].head(5).tolist()
        raise ValueError(f"{field} inválido. Exemplos: {bad}")
    result = pd.Series(pd.NA, index=series.index, dtype="Int64")
    valid = parsed.notna()
    if valid.any():
        result.loc[valid] = (
            parsed.loc[valid].dt.hour * 60 + parsed.loc[valid].dt.minute
        ).astype("int64")
    return result


def build_analysis_data(path: Path) -> dict:
    event_counts = {
        event: {uf: {} for uf in [*UFS, "BR"]}
        for event in TIME_FIELDS
    }
    municipalities = {uf: {} for uf in UFS}
    sections = []

    usecols = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_SECAO",
               "NR_LOCAL_VOTACAO", *TIME_FIELDS, *VOTE_FIELDS]
    for chunk in pd.read_csv(
        path, sep=";", encoding="utf-8-sig", usecols=usecols,
        dtype=str, chunksize=CHUNK_SIZE,
    ):
        if not set(chunk["SG_UF"].dropna()).issubset(set(UFS)):
            bad_ufs = sorted(set(chunk["SG_UF"].dropna()) - set(UFS))
            raise ValueError(f"UF inesperada no nacional: {bad_ufs}")

        times = {field: parse_time_minutes(chunk[field], field) for field in TIME_FIELDS}
        for event, minutes in times.items():
            valid = minutes.notna()
            if not valid.any():
                continue
            grouped = pd.DataFrame({
                "uf": chunk.loc[valid, "SG_UF"],
                "minute": minutes.loc[valid].astype(int),
            }).groupby(["uf", "minute"]).size()
            for (uf, minute), count in grouped.items():
                event_counts[event][uf][str(int(minute))] = (
                    event_counts[event][uf].get(str(int(minute)), 0) + int(count)
                )

        for uf, group in chunk.groupby("SG_UF", sort=False):
            if uf not in municipalities:
                raise ValueError(f"UF inesperada no nacional: {uf}")
            for code, name in group[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates().itertuples(index=False):
                if pd.notna(code):
                    municipalities[uf][str(code)] = "" if pd.isna(name) else str(name)

        for i, row in chunk.iterrows():
            sections.append([
                str(row["SG_UF"]),
                str(row["CD_MUNICIPIO"]),
                "" if pd.isna(row["NR_SECAO"]) else str(row["NR_SECAO"]),
                "" if pd.isna(row["NR_LOCAL_VOTACAO"]) else str(row["NR_LOCAL_VOTACAO"]),
                *[None if pd.isna(times[field].loc[i]) else int(times[field].loc[i]) for field in TIME_FIELDS],
                int(pd.to_numeric(row["VOTOS_FLAVIO_BOLSONARO"], errors="coerce") or 0),
                int(pd.to_numeric(row["VOTOS_LULA"], errors="coerce") or 0),
                int(pd.to_numeric(row["TOTAL_VOTOS_PRES"], errors="coerce") or 0),
            ])

    for event in TIME_FIELDS:
        merged = {}
        for uf in UFS:
            for minute, count in event_counts[event][uf].items():
                merged[minute] = merged.get(minute, 0) + count
        event_counts[event]["BR"] = merged

    municipalities_out = {
        uf: [{"code": code, "name": name}
             for code, name in sorted(values.items(), key=lambda x: x[1])]
        for uf, values in municipalities.items()
    }
    return {
        "event_counts": event_counts,
        "municipalities": municipalities_out,
        "sections": sections,
    }


def prepare_analysis_payload(data: dict) -> dict:
    return {
        "events": data["event_counts"],
        "event_labels": EVENT_FIELDS,
        "municipalities": data["municipalities"],
        "sections": data["sections"],
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Análise intradiária dos Boletins de Urna — Eleições 2026</title>
<style>
:root{--bg:#f5f7fa;--card:#fff;--ink:#17202a;--muted:#65717e;--line:#dfe5eb;--shadow:0 8px 28px rgba(23,32,42,.08);--before:#1769aa;--after:#d97706}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}.wrap{max-width:1500px;margin:auto;padding:24px}
.hero{margin-bottom:18px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#1769aa}h1{font-size:29px;line-height:1.15;margin:5px 0 8px}h2{font-size:18px;margin:0 0 5px}.sub,.note{color:var(--muted)}.note{font-size:12px;margin-top:8px}
.toolbar,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.toolbar{padding:14px 16px;display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:16px}.card{padding:18px;margin-bottom:16px}
label{display:flex;flex-direction:column;gap:5px;font-weight:650;color:#34404b}select,input[type=time]{min-width:210px;padding:9px 11px;border:1px solid #cbd4dd;border-radius:8px;background:#fff;font:inherit}
.cut{min-width:130px}.controls-note{align-self:center;max-width:560px}.chart-wrap{width:100%;overflow:auto}.main-chart{width:100%;min-width:900px;height:720px}.legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:8px}.legend-item{display:inline-flex;align-items:center;gap:6px}.swatch{width:22px;height:4px;border-radius:2px;display:inline-block}
.summary,.sections{width:100%;border-collapse:collapse}.table-wrap{overflow:auto;margin-top:12px}.summary{min-width:850px}.sections{min-width:1050px}.summary th,.summary td,.sections th,.sections td{padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap}.summary th,.sections th{text-align:left;font-size:12px;color:var(--muted)}.summary td,.sections td{font-variant-numeric:tabular-nums}.num{text-align:right}.side-before{background:#eaf3fa}.side-after{background:#fff3e4}.time-before{color:#1769aa;font-weight:700}.time-after{color:#d97706;font-weight:700}.empty{padding:20px;text-align:center;color:var(--muted)}
@media(max-width:800px){.wrap{padding:14px}h1{font-size:24px}.main-chart{min-width:760px;height:680px}}
</style>
</head>
<body>
<div class="wrap">
<section class="hero">
<div class="eyebrow">TSE • 1º turno • 2026</div>
<h1>Eventos do Boletim de Urna por horário do dia</h1>
<div class="sub">A análise ignora completamente a data dos campos <b>DT_ENCERRAMENTO</b>, <b>DT_EMISSAO_BU</b> e <b>DT_BU_RECEBIDO</b> e usa somente <b>hh:mm</b>. <b>DT_ABERTURA não participa desta análise.</b></div>
</section>
<div class="toolbar">
<label>Unidade da Federação<select id="uf"></select></label>
<label>Município<select id="municipio"></select></label>
<label class="cut">Horário de corte<input id="cutoff" type="time" value="07:12"></label>
<label>Início do eixo X<input id="xstart" type="time" value="00:00"></label>
<label>Fim do eixo X<input id="xend" type="time" value="23:59"></label>
<div class="controls-note note">Até o corte: <b>hh:mm ≤ corte</b>. Após o corte: <b>hh:mm &gt; corte</b>. O intervalo do eixo X controla o zoom; as faixas do histograma são recalculadas automaticamente.</div>
</div>
<section class="card">
<h2>Distribuição horária dos três eventos</h2>
<div class="sub">Um único eixo X compartilhado e três histogramas empilhados. Cada barra mostra o número de seções na faixa e o valor aparece sobre a barra. Passe o cursor sobre uma barra para ver a faixa e as seções.</div>
<div class="chart-wrap"><svg id="mainChart" class="main-chart" viewBox="0 0 1200 720" preserveAspectRatio="none"></svg></div>
<div class="legend">
<span class="legend-item"><span class="swatch" style="background:#1769aa"></span>Até o corte</span>
<span class="legend-item"><span class="swatch" style="background:#d97706"></span>Após o corte</span>
<span class="legend-item"><span class="swatch" style="background:#333;height:2px"></span>Linha de corte</span>
</div>
<div class="note">A região anterior ao corte é destacada também por fundo, para não depender apenas da cor. A linha tracejada está rotulada com o horário de corte.</div>
</section>
<section class="card">
<h2>Resumo por evento e lado do corte</h2>
<div class="sub">Os votos são agregados das seções que caíram naquele lado do corte para o respectivo evento. A métrica é calculada sobre a soma dos votos, nunca como média das seções.</div>
<div class="table-wrap"><table class="summary"><thead><tr><th>Campo</th><th>Lado</th><th class="num">Seções</th><th class="num">Votos Flávio</th><th class="num">Votos Lula</th><th class="num">Total de votos</th><th class="num">Métrica</th></tr></thead><tbody id="summaryBody"></tbody></table></div>
</section>
<section class="card">
<h2>Seções</h2>
<div class="sub">Cada seção entra no lado do corte conforme o horário do campo selecionado. Os três horários são independentes e coloridos por lado do corte.</div>
<div class="table-wrap"><table class="sections"><thead><tr><th>Seção</th><th>Local</th><th>Encerramento</th><th>Emissão do BU</th><th>BU recebido</th><th class="num">Votos Flávio</th><th class="num">Votos Lula</th><th class="num">Métrica</th></tr></thead><tbody id="sectionsBody"></tbody></table></div>
</section>
<div class="foot note">Fonte: Tribunal Superior Eleitoral (TSE), Boletim de Urna 2026. Este painel analisa os horários registrados nos BUs; não representa o instante de totalização individual de votos. Datas são deliberadamente ignoradas nesta análise.</div>
</div>
<script>
const DATA=__DATA__;
const UFS=__UFS__;
const $=id=>document.getElementById(id);
const fmtInt=n=>new Intl.NumberFormat("pt-BR").format(n);
const fmtPct=n=>n==null?"–":n.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2})+"%";
const EVENT_ORDER=["DT_ENCERRAMENTO","DT_EMISSAO_BU","DT_BU_RECEBIDO"];
const COLORS={before:"#1769aa",after:"#d97706"};
const LABELS=DATA.event_labels;
function timeText(m){if(m==null)return "—";return String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0")}
function cutoff(){return timeMinutes($("cutoff").value)}
function timeMinutes(s){if(!s)return null;const [h,m]=s.split(":").map(Number);return h*60+m}
function side(m,c){return m==null?"":(m<=c?"before":"after")}
function metric(vf,vl){return vf===0?"–":fmtPct((vf-vl)*100/vf)}
function setup(){
 $("uf").innerHTML='<option value="BR">Brasil</option>'+UFS.map(u=>'<option value="'+u+'">'+u+'</option>').join("");
 $("uf").onchange=()=>{populateMunicipios();render()};
 ["municipio","cutoff","xstart","xend"].forEach(id=>$(id).addEventListener("change",render));
 $("uf").value="BR";populateMunicipios();setDefaultZoom();render();
}
function populateMunicipios(){
 const uf=$("uf").value, list=uf==="BR"?[]:(DATA.municipalities[uf]||[]);
 $("municipio").innerHTML='<option value="ALL">Todos</option>'+list.map(x=>'<option value="'+x.code+'">'+escapeHtml(x.name)+" ("+x.code+")</option>").join("");
 $("municipio").disabled=uf==="BR";
}
function setDefaultZoom(){
 const vals=EVENT_ORDER.flatMap(e=>Object.values(DATA.events[e]||{}).flatMap(o=>Object.keys(o).map(Number)));
 if(vals.length){$("xstart").value=timeText(Math.min(...vals));$("xend").value=timeText(Math.max(...vals));}
}
function selectedSections(){
 const uf=$("uf").value,mun=$("municipio").value;
 return DATA.sections.filter(r=>(uf==="BR"||r[0]===uf)&&(mun==="ALL"||r[1]===mun));
}
function render(){drawChart();drawSummary();drawSections()}
function drawChart(){
 const svg=$("mainChart");clear(svg);const sections=selectedSections(),c=cutoff();
 let start=timeMinutes($("xstart").value),end=timeMinutes($("xend").value);if(start==null)start=0;if(end==null)end=1439;if(end<=start)end=Math.min(1439,start+1);
 const W=1200,H=720,L=78,R=28,T=34,B=55,rowH=185,gap=30,plotW=W-L-R;
 const x=m=>L+(m-start)/(end-start)*plotW;
 const bins=autoBins(start,end,plotW);
 svg.append(el("rect",{x:L,y:T,width:Math.max(0,x(Math.min(c,end))-L),height:H-T-B,class:"before-zone",fill:"#1769aa",opacity:".07"}));
 const cutX=x(c);svg.append(el("line",{x1:cutX,x2:cutX,y1:T-8,y2:H-B,class:"cutline",stroke:"#333","stroke-width":"2","stroke-dasharray":"7 5"}));svg.append(el("rect",{x:Math.max(L,Math.min(cutX-45,W-R-90)),y:6,width:90,height:22,rx:6,fill:"#333"}));svg.append(el("text",{x:Math.max(L+45,Math.min(cutX,W-R-45)),y:21,"text-anchor":"middle",fill:"#fff","font-size":"12","font-weight":"700"}),"Corte "+timeText(c));
 [0,0.25,0.5,0.75,1].forEach(v=>{const xx=L+v*plotW;svg.append(el("line",{x1:xx,x2:xx,y1:H-B,y2:H-B+5,class:"axis",stroke:"#b9c3cc"}))});
 EVENT_ORDER.forEach((field,idx)=>{
   const y0=T+idx*(rowH+gap),yBase=y0+rowH-28;
   svg.append(el("text",{x:8,y:y0+16,"font-size":"14","font-weight":"700",fill:"#17202a"}),LABELS[field]);
   [0,.5,1].forEach(v=>{const yy=yBase-v*(rowH-48);svg.append(el("line",{x1:L,x2:W-R,y1:yy,y2:yy,class:"grid",stroke:"#e8edf2"}));if(v>0)svg.append(el("text",{x:10,y:yy+4},fmtInt(Math.round(v*maxBinCount(sections,field,bins)))))});
   const counts=histogram(sections,field,start,end,bins),max=Math.max(...counts.map(b=>b.n),1),barW=plotW/bins;
   counts.forEach(b=>{const bx=x(b.start),bw=Math.max(1,barW-2),by=yBase-b.n/max*(rowH-48),bh=yBase-by,cl=b.start<=c?"before":"after";const rect=el("rect",{x:bx,y:by,width:bw,height:bh,fill:COLORS[cl],opacity:".84",rx:"2"});const tt=el("title",{},timeText(b.start)+"–"+timeText(Math.max(b.start,b.end-1))+" • "+fmtInt(b.n)+" seções");rect.appendChild(tt);svg.append(rect);if(b.n>0)svg.append(el("text",{x:bx+bw/2,y:Math.max(y0+30,by-5),"text-anchor":"middle",fill:"#34404b","font-size":"10","font-weight":"700"},fmtInt(b.n)))}); 
 });
 for(let m=start;m<=end;m+=Math.max(1,Math.ceil((end-start)/8))){const xx=x(m);svg.append(el("line",{x1:xx,x2:xx,y1:H-B,y2:H-B+5,class:"axis",stroke:"#b9c3cc"}));svg.append(el("text",{x:xx,y:H-18,"text-anchor":"middle"},timeText(m)))}
 svg.append(el("line",{x1:L,x2:W-R,y1:H-B,y2:H-B,class:"axis",stroke:"#b9c3cc"}));
}
function autoBins(start,end,width){const target=Math.max(8,Math.floor(width/65));return Math.max(1,Math.ceil((end-start)/target))}
function histogram(rows,field,start,end,bins){const out=Array.from({length:bins},(_,i)=>({start:start+i*(end-start)/bins,end:start+(i+1)*(end-start)/bins,n:0}));const idx=EVENT_ORDER.indexOf(field)+4;rows.forEach(r=>{const m=r[idx];if(m==null||m<start||m>end)return;let i=Math.min(bins-1,Math.floor((m-start)/(end-start)*bins));out[i].n++});return out}
function maxBinCount(rows,field,bins){return Math.max(1,Math.ceil(rows.length/bins))}
function drawSummary(){
 const rows=selectedSections(),c=cutoff(),out=[];
 EVENT_ORDER.forEach((field,i)=>{["before","after"].forEach(s=>{let n=0,vf=0,vl=0,total=0;rows.forEach(r=>{const m=r[4+i];if(m!=null&&side(m,c)===s){n++;vf+=r[7];vl+=r[8];total+=r[9]}});out.push('<tr class="'+(s==="before"?"side-before":"side-after")+'"><td><b>'+LABELS[field]+'</b></td><td>'+ (s==="before"?"Até o corte":"Após o corte")+'</td><td class="num">'+fmtInt(n)+'</td><td class="num">'+fmtInt(vf)+'</td><td class="num">'+fmtInt(vl)+'</td><td class="num">'+fmtInt(total)+'</td><td class="num">'+metric(vf,vl)+'</td></tr>')})});
 $("summaryBody").innerHTML=out.join("");
}
function drawSections(){
 const rows=selectedSections(),c=cutoff();
 $("sectionsBody").innerHTML=rows.map(r=>'<tr><td>'+escapeHtml(r[2])+'</td><td>'+escapeHtml(r[3])+'</td>'+[4,5,6].map(i=>'<td class="'+(r[i]==null?"":"time-"+side(r[i],c))+'">'+timeText(r[i])+'</td>').join("")+'<td class="num">'+fmtInt(r[7])+'</td><td class="num">'+fmtInt(r[8])+'</td><td class="num">'+metric(r[7],r[8])+'</td></tr>').join("")||'<tr><td colspan="8" class="empty">Nenhuma seção encontrada para os filtros selecionados.</td></tr>';
}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}
function clear(svg){svg.innerHTML=""}
function el(tag,a,text){const n=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const[k,v]of Object.entries(a||{}))n.setAttribute(k,v);if(text!=null)n.textContent=text;return n}
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

    data = build_analysis_data(path)
    payload = prepare_analysis_payload(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__UFS__", json.dumps(UFS))
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard: {output}")
    print(f"Sections: {len(data['sections']):,}")
    print(f"UFs: {len(UFS)}")


if __name__ == "__main__":
    main()
