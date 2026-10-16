from pathlib import Path
import zipfile,csv,io,re,json,datetime,collections
import pandas as pd
R=Path(__file__).resolve().parents[1]; O=R/'analysis_outputs'
h=pd.read_csv(O/'household_coverage.csv'); st=pd.read_csv(O/'sensor_statistics.csv'); q=pd.read_csv(O/'label_quality.csv'); l=pd.read_csv(O/'household_labels.csv')
paths=sorted(p for p in (R/'Dataset').rglob('*.zip') if '_01.' in p.name)
keys=set()
for p in paths:
    with zipfile.ZipFile(p) as z:
        keys.update(re.search(r'I_([AB]\d{4})',n)[1] for n in z.namelist())
aliases={k:('N' if g=='A' else 'E')+f'{i+1:03d}' for g in 'AB' for i,k in enumerate(sorted(k for k in keys if k[0]==g))}
checks=[]
for p in paths:
    with zipfile.ZipFile(p) as z:
        n=z.namelist()[0]; key=re.search(r'I_([AB]\d{4})',n)[1]; alias=aliases[key]
        with z.open(n) as f:
            rows=list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig')))
    times=sorted(set(datetime.datetime.fromisoformat(r['Time']) for r in rows))
    delta=[(b-a).total_seconds()/60 for a,b in zip(times,times[1:])]
    row=h.set_index('household').loc[alias]
    assert len(rows)==row.rows
    assert str(times[0])==row.start and str(times[-1])==row.end
    assert max(delta)==row.max_gap_minutes
    assert sum(x>10 for x in delta)==row.gap_count
    assert sum(float(r['Activity_IR'])==0 for r in rows)==row.activity_zero_rows
    latest=sum(times[-1]-datetime.timedelta(days=14)<t<=times[-1] for t in times)
    assert latest==row.latest14_observed_slots
    assert len(set(t.date() for t in times))==row.recorded_days
    checks.append(dict(household=alias,rows=len(rows),checks=7,result='passed'))
for g in 'AB':
    n=int(h[h.cohort==g].rows.sum())
    for r in st[st.cohort==g].itertuples():
        assert r.n+r.missing_or_non_numeric+r.infinite==n
    expected=q[q.cohort==g].em_records.sum()
    assert l[(l.cohort==g)&(l.component=='EM_Sensor')]['count'].sum()==expected
assert len(h)==927 and not h.household.duplicated().any()
out=dict(independent_csv_checks=checks,total_rows=int(h.rows.sum()),sensor_denominator_reconciliation='passed',label_denominator_reconciliation='passed',unique_household_check='passed',timestamp_units='explicit datetime64[ns]; independent datetime comparison passed')
(O/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
