"""Offline scoring: human answers are loaded here, never by model payload builders."""
import csv
import json
from pathlib import Path
from .core import TOPICS, INTENTS, atomic_json, course
from .label_ui import validate

def evaluate(human_path,predictions_path,out_path):
    with Path(human_path).open(newline='',encoding='utf-8-sig') as f:human=list(csv.DictReader(f))
    if len(human)!=50 or len({r['review_id'] for r in human})!=50:raise ValueError('Expected 50 distinct human golden IDs.')
    pending=[]
    for row in human:
        try:validate(row,row)
        except (ValueError,KeyError,TypeError):pending.append(row['review_id'])
    if pending:
        result={'state':'pending_human_labels','completed_human_rows':50-len(pending),'pending_human_rows':len(pending),'accuracy':None,'new_model_calls':0}
        atomic_json(out_path,result);return result
    path=Path(predictions_path)
    if not path.exists():
        result={'state':'pending_predictions','completed_human_rows':50,'accuracy':None,'new_model_calls':0}
        atomic_json(out_path,result);return result
    predictions=json.loads(path.read_text()) if path.suffix=='.json' else [json.loads(s) for s in path.read_text().splitlines()]
    expected_ids={r['review_id'] for r in human}
    predicted_ids=[r['review_id'] for r in predictions]
    if len(predicted_ids)!=len(set(predicted_ids)) or not set(predicted_ids)<=expected_ids:
        raise ValueError('Golden predictions contain duplicate or unexpected IDs.')
    lookup={r['review_id']:r for r in predictions if r.get('status')=='completed'}
    errors=[];metrics={}
    for field,labels in [('topic',TOPICS),('intent',INTENTS)]:
        pairs=[(r[field],lookup.get(r['review_id'],{}).get(field,'<missing>')) for r in human]
        scores={}
        for label in labels:
            tp=sum(a==b==label for a,b in pairs);actual=sum(a==label for a,b in pairs);predicted=sum(b==label for a,b in pairs)
            scores[label]={'support':actual,'precision':tp/predicted if predicted else 0,'recall':tp/actual if actual else 0,'f1':2*tp/(actual+predicted) if actual+predicted else 0}
        metrics[field]={'accuracy':sum(a==b for a,b in pairs)/50,'macro_f1':sum(v['f1'] for v in scores.values())/len(labels),'per_class':scores}
    severity_distance=[];sentiment_distance=[]
    for row in human:
        prediction=lookup.get(row['review_id'])
        if prediction and prediction.get('source_sha256')!=course.row_sha(row):raise ValueError('Golden source identity differs from prediction.')
        if prediction:
            severity_distance.append(abs(int(row['severity'])-prediction['severity']));sentiment_distance.append(abs(float(row['sentiment'])-prediction['sentiment']))
        if not prediction or any(str(prediction.get(f))!=row[f] for f in ('topic','intent','severity')):errors.append({'review_id':row['review_id'],'human':{f:row[f] for f in ('topic','intent','severity')},'prediction':{f:prediction.get(f) for f in ('topic','intent','severity')} if prediction else None})
    rubric_conflicts=[{'review_id':r['review_id'],'field':'severity','human_value':r['severity'],'rule':'Pure request, praise or unclear/no-problem is severity 1; review the source and intent before changing a label.'}
                     for r in human if r['intent'] in ('request','praise','unclear') and int(r['severity'])!=1]
    flag_agreement=sum(str(lookup.get(r['review_id'],{}).get('needs_review')).lower()==r['needs_review'].lower() for r in human)/50
    quote_valid=sum(bool(lookup.get(r['review_id'],{}).get('evidence_quote')) and lookup[r['review_id']]['evidence_quote'] in r['review_text'] for r in human)
    result={'state':'scored','official_instructor_benchmark':False,'benchmark_source':'student human labels','denominator':50,'valid_predictions':len(severity_distance),
            'classification_metrics':metrics,'severity_mae_valid_predictions':sum(severity_distance)/len(severity_distance) if severity_distance else None,
            'sentiment_mae_valid_predictions':sum(sentiment_distance)/len(sentiment_distance) if sentiment_distance else None,
            'severity_exact_agreement':sum(d==0 for d in severity_distance)/50,'needs_review_agreement':flag_agreement,
            'exact_source_quote_count':quote_valid,'quote_semantic_support':'manual review pending',
            'human_rubric_conflicts_for_review':rubric_conflicts,'human_labels_modified':False,
            'disagreements':errors,'new_model_calls':0,'note':'Missing predictions stay in accuracy denominators. Macro F1 uses the full declared label set. If these answers guide tuning, collect a fresh holdout.'}
    atomic_json(out_path,result);return result
