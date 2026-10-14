#!/usr/bin/env python3
"""Compare saved golden predictions with final export coverage; never infer accuracy."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(golden, records):
    predictions=json.loads(golden.read_text())
    by_id={r['review_id']:r for r in predictions}
    if len(predictions)!=50 or len(by_id)!=50:
        raise ValueError('Expected 50 unique saved golden predictions.')
    found={};digest=hashlib.sha256()
    with records.open('rb') as source:
        for line in source:
            digest.update(line)
            if not line.strip():continue
            row=json.loads(line);rid=row['review_id']
            if rid in by_id:
                if rid in found:raise ValueError('Duplicate golden ID in final export.')
                found[rid]=row
    differences=[]
    for rid,row in sorted(found.items()):
        changed={key:{'golden':by_id[rid].get(key),'production':row.get(key)}
                 for key in ('topic','intent','severity','sentiment','needs_review')
                 if by_id[rid].get(key)!=row.get(key)}
        if changed:differences.append({'review_id':rid,'fields':changed})
    return dict(golden_predictions=50,final_export_overlap=len(found),
                completed_overlap=sum(r['status']=='completed' for r in found.values()),
                missing_golden_ids=sorted(set(by_id)-set(found)),prediction_differences=differences,
                golden_sha256=hashlib.sha256(golden.read_bytes()).hexdigest(),
                final_export_sha256=digest.hexdigest(),labels_modified=False,new_model_calls=0,
                interpretation='Original golden agreement is not a fresh evaluation of this final export. Private instructor benchmark unavailable; no private-benchmark accuracy inferred.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--golden',type=Path,default=Path('reports/golden50/records.json'))
    parser.add_argument('--records',type=Path,default=Path('grading/records.jsonl'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.resolve() in (args.golden.resolve(),args.records.resolve()):
        parser.error('Output must not overwrite saved evidence.')
    result=compare(args.golden,args.records)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('golden_predictions','final_export_overlap','completed_overlap','new_model_calls')}))
