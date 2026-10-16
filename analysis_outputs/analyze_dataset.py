from pathlib import Path
import zipfile, json, io, re, csv, time, collections, math
import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'Dataset'
OUT = ROOT / 'analysis_outputs'
FIELDS = ['Activity_IR', 'Temperature', 'Humidity']
archives = sorted(DATA.rglob('*.zip'))
ids = set()
inventory = []
schemas = []
for p in archives:
    with zipfile.ZipFile(p) as z:
        members = [x for x in z.infolist() if not x.is_dir()]
        ext = collections.Counter(Path(x.filename).suffix.lower() for x in members)
        for x in members:
            m = re.search(r'(?:I_|L_|IR_)([AB]\d{4})', x.filename)
            if m: ids.add(m[1])
        # Image archive filenames contain source identifiers: anonymize in inventory.
        name = re.sub(r'IR_A\d{4}', 'IR_[household]', p.name)
        inventory.append(dict(path=str(p.parent.relative_to(DATA) / name), bytes=p.stat().st_size,
                              expanded_bytes=sum(x.file_size for x in members), members=len(members), types=dict(ext)))
aliases = {key: ('N' if key[0]=='A' else 'E')+f'{i+1:03d}' for group in 'AB'
           for i,key in enumerate(sorted(k for k in ids if k[0]==group))}
freq = {g:{f:collections.Counter() for f in FIELDS} for g in 'AB'}
invalid = {g:{f:collections.Counter() for f in FIELDS} for g in 'AB'}
intervals = {g:collections.Counter() for g in 'AB'}
households=[]; daily=[]; hourly=[]; label_rows=[]; label_quality=[]; units=collections.Counter()
peak=0; start=time.time()
def rss():
    global peak
    peak=max(peak,psutil.Process().memory_info().rss)
def longest(mask):
    best=run=0
    for b in mask:
        run=run+1 if b else 0; best=max(best,run)
    return best
def save(name, rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')

gapfile=(OUT/'missing_intervals.csv').open('w',newline='',encoding='utf-8-sig')
gapwriter=csv.writer(gapfile); gapwriter.writerow(['household','previous_observation','next_observation','delta_minutes','missing_10min_slots'])
raw_by_id={}
for p in archives:
    if '_01.' not in p.name: continue
    group='A' if '_A.' in p.name else 'B'; split='Training' if p.name.startswith('TS') else 'Validation'
    with zipfile.ZipFile(p) as z:
        for index,n in enumerate(z.namelist()):
            if not n.endswith('.csv'): continue
            key=re.search(r'I_([AB]\d{4})',n)[1]; alias=aliases[key]
            chunks=[]; row_count=0; badtime=0; prev=None; inversions=0
            with z.open(n) as f:
                for c in pd.read_csv(f,chunksize=50000,usecols=['Time']+FIELDS):
                    row_count+=len(c); t=pd.to_datetime(c['Time'],errors='coerce'); badtime+=int(t.isna().sum())
                    a=t.dropna().to_numpy(dtype='datetime64[ns]').astype('int64')
                    if prev is not None and len(a): inversions+=int(a[0]<prev)
                    inversions+=int((np.diff(a)<0).sum())
                    if len(a): prev=a[-1]
                    for field in FIELDS:
                        v=pd.to_numeric(c[field],errors='coerce'); finite=np.isfinite(v)
                        invalid[group][field]['missing_or_non_numeric']+=int(v.isna().sum())
                        invalid[group][field]['infinite']+=int((v.notna() & ~finite).sum())
                        vc=v[finite].value_counts(); freq[group][field].update(dict(zip(vc.index.astype(float),vc.astype(int))))
                        c[field]=v
                    c['Time']=t; chunks.append(c); rss()
            d=pd.concat(chunks,ignore_index=True); del chunks
            d=d.dropna(subset=['Time']).sort_values('Time',kind='stable')
            duplicates=int(d['Time'].duplicated().sum())
            conflicts=int(d.groupby('Time')[FIELDS].nunique(dropna=False).gt(1).any(axis=1).sum())
            unique=d.drop_duplicates('Time',keep='first').copy()
            ts=unique['Time'].to_numpy(dtype='datetime64[ns]').astype('int64'); delta=np.diff(ts)//10**9
            intervals[group].update(dict(zip(*np.unique(delta,return_counts=True))))
            for ix in np.flatnonzero(delta>600):
                gapwriter.writerow([alias,str(unique['Time'].iloc[ix]),str(unique['Time'].iloc[ix+1]),delta[ix]/60,max(0,math.ceil(delta[ix]/600)-1)])
            first=unique['Time'].min(); last=unique['Time'].max()
            ongrid=(ts%(600*10**9)==0)
            valid=unique[FIELDS].notna().all(axis=1).to_numpy() & np.isfinite(unique[FIELDS]).all(axis=1).to_numpy()
            plausible=(unique['Activity_IR']>=0).to_numpy() & unique['Temperature'].between(-40,85).to_numpy() & unique['Humidity'].between(0,100).to_numpy()
            unique['date']=unique['Time'].dt.floor('D')
            dates=pd.date_range(first.floor('D'),last.floor('D'),freq='D')
            cnt=unique.groupby('date').size().reindex(dates,fill_value=0)
            good=unique[valid & plausible & ongrid].groupby('date').size().reindex(dates,fill_value=0)
            full=good.eq(144).to_numpy(); tolerant=good.ge(130).to_numpy()
            for date,total,quality in zip(dates,cnt,good):
                daily.append(dict(household=alias,cohort=group,date=str(date.date()),observed_slots=int(total),valid_slots=int(quality),coverage=quality/144))
            # Exact consecutive timestamp segment, including a partial first/last calendar day.
            breaks=np.r_[0,np.flatnonzero((delta!=600) | ~valid[:-1] | ~valid[1:] | ~plausible[:-1] | ~plausible[1:])+1,len(ts)]
            continuous=max((int(b-a) if valid[a] and plausible[a] else 0 for a,b in zip(breaks[:-1],breaks[1:])),default=0)
            cutoff=last-pd.Timedelta(days=14)
            recent=unique[unique['Time']>cutoff]; recentvalid=(unique['Time']>cutoff).to_numpy() & valid & plausible & ongrid
            h=dict(household=alias,cohort=group,split=split,rows=row_count,start=str(first),end=str(last),span_calendar_days=len(dates),
                recorded_days=int((cnt>0).sum()),missing_whole_days=int((cnt==0).sum()),bad_timestamps=badtime,duplicate_timestamps=duplicates,
                conflicting_timestamps=conflicts,original_time_inversions=inversions,off_grid_rows=int((~ongrid).sum()),
                gap_count=int((delta>600).sum()),max_gap_minutes=float(delta.max()/60) if len(delta) else 0,
                expected_slots=int((last-first).total_seconds()/600)+1,unique_slots=len(unique),
                longest_complete_days=longest(full),longest_90pct_days=longest(tolerant),longest_continuous_valid_slots=continuous,
                any_14_complete_days=longest(full)>=14,any_14_90pct_days=longest(tolerant)>=14,any_14_continuous_slots=continuous>=2016,
                latest14_observed_slots=len(recent),latest14_valid_slots=int(recentvalid.sum()),latest14_coverage=float(recentvalid.sum()/2016),
                latest14_complete=bool(recentvalid.sum()==2016),activity_zero_rows=int(d['Activity_IR'].eq(0).sum()),
                activity_valid_rows=int(np.isfinite(d['Activity_IR']).sum()))
            for field in FIELDS:
                h[field+'_missing']=int(d[field].isna().sum())
            households.append(h)
            unique['hour']=unique['Time'].dt.hour
            for hour,s in unique.groupby('hour'):
                hourly.append(dict(household=alias,cohort=group,hour=int(hour),rows=len(s),activity_mean=float(s.Activity_IR.mean()),
                    activity_median=float(s.Activity_IR.median()),zero_rate=float(s.Activity_IR.eq(0).sum()/s.Activity_IR.notna().sum()),
                    temperature_mean=float(s.Temperature.mean()),humidity_mean=float(s.Humidity.mean())))
            raw_by_id[key]=(p,n)
            rss()
            if (index+1)%100==0 or group=='A': print('environment',group,split,index+1,'RSS_MB',round(peak/2**20),flush=True)
gapfile.close()
save('household_coverage.csv',households); save('daily_coverage.csv',daily); save('hourly_patterns.csv',hourly)
save('archive_inventory.csv',[{**x,'types':json.dumps(x['types'])} for x in inventory])
for p in archives:
    if '_06.' in p.name:
        group='A' if '_A.' in p.name else 'B'
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                with z.open(n) as f:
                    d=pd.read_csv(f,usecols=['ModelList','movement UoM'])
                    for r in d.to_dict('records'): units[(group,str(r['ModelList']),str(r['movement UoM']))]+=1
    if p.name.startswith(('TS','VS')) and 'IMAGE' not in p.name:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                with z.open(n) as f: cols=pd.read_csv(f,nrows=0).columns.tolist()
                schemas.append(dict(archive=re.sub(r'IR_A\d{4}','IR_[household]',p.name),columns=cols))

def records(f):
    # Incremental UTF-8 text decoding and one JSON object at a time. Never load a member in full.
    reader=io.TextIOWrapper(f,encoding='utf-8-sig'); buf=''; decoder=json.JSONDecoder()
    while '"TimeSeriesData"' not in buf:
        part=reader.read(65536)
        if not part: raise ValueError('TimeSeriesData absent')
        buf+=part
    pos=buf.index('[',buf.index('"TimeSeriesData"'))+1
    while True:
        while pos<len(buf) and buf[pos] in ' \r\n\t,': pos+=1
        if pos<len(buf) and buf[pos]==']': return
        try:
            obj,end=decoder.raw_decode(buf,pos)
        except json.JSONDecodeError:
            part=reader.read(1024*1024)
            if not part: raise ValueError('Truncated/malformed JSON')
            buf=buf[pos:]+part; pos=0
            if len(buf)>16*1024*1024: raise ValueError('Single JSON record exceeds buffer limit')
            continue
        pos=end
        yield obj

for p in archives:
    if not p.name.startswith(('TL','VL')): continue
    group='A' if '_A.' in p.name else 'B'
    with zipfile.ZipFile(p) as z:
        for index,n in enumerate(z.namelist()):
            key=re.search(r'L_([AB]\d{4})',n)[1]; alias=aliases[key]
            counts=collections.Counter(); components=collections.Counter(); seen=set(); duplicates=badtime=rows=0
            # Compare label sensor values and times to raw CSV, only within this household.
            rp,rn=raw_by_id[key]
            with zipfile.ZipFile(rp) as rz,rz.open(rn) as rf:
                rd=pd.read_csv(rf,usecols=['Time']+FIELDS)
            rawmap={str(t)[:16].replace(' ','T'):tuple(v) for t,*v in rd[['Time']+FIELDS].itertuples(index=False,name=None)}
            rawmatched=set(); unmatched=disagree=emrows=0; first=last=None
            with z.open(n) as f:
                for o in records(f):
                    rows+=1; t=o.get('TimeStamp'); components.update(o.keys())
                    if t in seen: duplicates+=1
                    seen.add(t)
                    if isinstance(t,str): first=t if first is None or t<first else first; last=t if last is None or t>last else last
                    else: badtime+=1
                    for component in ['EM_Sensor','SM_Sensor','ER_Sensor','Total_Labeling']:
                        obj=o.get(component)
                        if isinstance(obj,dict):
                            field='Estimation' if component=='Total_Labeling' else 'Label'
                            v=obj.get(field); counts[(component,field,str(v) if v is not None else '__MISSING__')]+=1
                    em=o.get('EM_Sensor')
                    if isinstance(em,dict):
                        emrows+=1
                        if t not in rawmap: unmatched+=1
                        else:
                            rawmatched.add(t); rv=rawmap[t]
                            for v,fld in zip(rv,FIELDS):
                                jv=em.get(fld)
                                if not (jv==v or (pd.isna(v) and jv is None)):
                                    disagree+=1; break
                    if rows%50000==0: rss()
            for (comp,field,label),cnt in counts.items(): label_rows.append(dict(household=alias,cohort=group,component=comp,field=field,label=label,count=cnt))
            label_quality.append(dict(household=alias,cohort=group,records=rows,unique_timestamps=len(seen),duplicate_timestamps=duplicates,
                missing_timestamp=badtime,start=first,end=last,em_records=emrows,em_unmatched_raw=unmatched,
                em_value_disagreements=disagree,raw_unmatched_label=len(set(rawmap)-rawmatched),components=json.dumps(components)))
            rss()
            if (index+1)%25==0 or group=='A': print('labels',group,p.name[:4],index+1,'elapsed_s',round(time.time()-start),'RSS_MB',round(peak/2**20),flush=True)
    save('household_labels.csv',label_rows); save('label_quality.csv',label_quality)

stats=[]; histogram=[]
for g in 'AB':
    for f in FIELDS:
        c=freq[g][f]; values=np.array(sorted(c)); weights=np.array([c[v] for v in values]); total=int(weights.sum()); cum=np.cumsum(weights)
        mean=float(np.dot(values,weights)/total); sd=float(np.sqrt(np.dot((values-mean)**2,weights)/total))
        def quant(q):
            rank=(total-1)*q; lo=math.floor(rank); hi=math.ceil(rank)
            a=values[np.searchsorted(cum,lo+1)]; b=values[np.searchsorted(cum,hi+1)]
            return float(a+(b-a)*(rank-lo))
        q1,q3=quant(.25),quant(.75); low=q1-1.5*(q3-q1); high=q3+1.5*(q3-q1)
        out=int(weights[(values<low)|(values>high)].sum())
        physical=int(weights[(values<0)].sum()) if f=='Activity_IR' else int(weights[(values<0)|(values>100)].sum()) if f=='Humidity' else int(weights[(values< -40)|(values>85)].sum())
        stats.append(dict(cohort=g,field=f,n=total,unique_values=len(values),minimum=float(values.min()),maximum=float(values.max()),mean=mean,std=sd,
            p01=quant(.01),p05=quant(.05),p25=q1,p50=quant(.5),p75=q3,p95=quant(.95),p99=quant(.99),
            zero_count=int(c[0]),zero_rate=c[0]/total,noninteger_count=int(weights[values%1!=0].sum()),iqr_low=low,iqr_high=high,iqr_outliers=out,
            plausibility_flagged=physical,**invalid[g][f]))
        histogram.extend(dict(cohort=g,field=f,value=float(v),count=int(w)) for v,w in zip(values,weights))
save('sensor_statistics.csv',stats); save('sensor_value_counts.csv',histogram)
save('measurement_intervals.csv',[dict(cohort=g,seconds=int(v),count=int(w)) for g,c in intervals.items() for v,w in sorted(c.items())])
save('sensor_units.csv',[dict(cohort=g,models=m,movement_unit=u,households=c) for (g,m,u),c in units.items()])
(OUT/'schema_inventory.json').write_text(json.dumps(schemas,ensure_ascii=False,indent=2),encoding='utf-8')
summary=dict(archives=len(archives),compressed_bytes=sum(x['bytes'] for x in inventory),expanded_bytes=sum(x['expanded_bytes'] for x in inventory),
    members=sum(x['members'] for x in inventory),households=len(households),cohorts={g:sum(h['cohort']==g for h in households) for g in 'AB'},
    rows=sum(h['rows'] for h in households),label_records=sum(h['records'] for h in label_quality),sampled_peak_rss_bytes=peak,elapsed_seconds=time.time()-start)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('DONE',json.dumps(summary),flush=True)
