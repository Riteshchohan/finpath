import calendar
import math
from datetime import date, timedelta
from statistics import median
from .ml import forecast, anomalies

def next_month(d):
    return date(d.year+(d.month==12), 1 if d.month==12 else d.month+1, 1)

def complete_months(rows, statements, today):
    periods = [(date.fromisoformat(s['start_date']),date.fromisoformat(s['end_date'])) for s in statements]
    if not periods:
        return []
    cursor = min(a for a,b in periods).replace(day=1)
    result = []
    while next_month(cursor) <= today:
        end = next_month(cursor)-timedelta(days=1)
        covered = all(any(a <= cursor+timedelta(days=i) <= b for a,b in periods)
                      for i in range((end-cursor).days+1))
        if covered:
            selected = [r for r in rows if cursor.isoformat() <= r['date'] <= end.isoformat() and r['category']!='Transfer']
            result.append(dict(month=cursor.strftime('%Y-%m'),
                income=round(sum(max(0,r['amount_cents']) for r in selected)/100,2),
                expense=round(sum(max(0,-r['amount_cents']) for r in selected)/100,2),
                essential=round(sum(-r['amount_cents'] for r in selected if r['amount_cents']<0 and r['essential'])/100,2)))
        cursor = next_month(cursor)
    return result[-24:]

def dashboard(rows, statements, goals, today=None):
    today = today or date.today()
    months = complete_months(rows, statements, today)
    # Never pass disjoint months to a regular time-series model as consecutive observations.
    consecutive = []
    for month in months:
        if consecutive and next_month(date.fromisoformat(consecutive[-1]['month']+'-01')).strftime('%Y-%m') != month['month']:
            consecutive = []
        consecutive.append(month)
    f = forecast(consecutive)
    essential = round(float(median([m['essential'] for m in consecutive[-6:]])),2) if consecutive else 0
    buffer = round(f['conservative_income']*.1,2)
    plans, required = [], 0
    overdue = False
    for g in goals:
        remaining = max(0,(g['target_cents']-g['saved_cents'])/100)
        deadline = date.fromisoformat(g['deadline'])
        days = (deadline-today).days
        expired = days <= 0 and remaining > 0
        overdue |= expired
        monthly = round(remaining/max(days,1)*30.4375,2)
        required += monthly
        milestones = []
        point = min(next_month(today)-timedelta(days=1),deadline)
        while point >= today and point <= deadline and len(milestones)<60:
            fraction = min(1, max(0,(point-today).days)/max(days,1))
            milestones.append(dict(date=point.isoformat(), saved=round(g['saved_cents']/100+remaining*fraction,2)))
            if point == deadline:
                break
            point = min(next_month(point.replace(day=1))+timedelta(days=calendar.monthrange(next_month(point.replace(day=1)).year,next_month(point.replace(day=1)).month)[1]-1), deadline)
        plans.append({**g,'remaining':remaining,'monthly_saving':monthly,
                      'daily_saving':round(remaining/max(days,1),2),'overdue':expired,'milestones':milestones})
    available = round(f['conservative_income']-essential-buffer-required,2)
    current_rows = [r for r in rows if r['date'][:7]==today.strftime('%Y-%m') and r['category']!='Transfer']
    spent = round(sum(-r['amount_cents'] for r in current_rows if r['amount_cents']<0 and not r['essential'])/100,2)
    remaining_budget = max(0, round(available-spent,2))
    stale = not statements or max(s['end_date'] for s in statements) < (today-timedelta(days=45)).isoformat()
    possible = bool(months) and not overdue and available >= 0
    categories = {}
    for r in rows:
        if r['amount_cents']<0 and r['category']!='Transfer':
            categories[r['category']] = round(categories.get(r['category'],0)-r['amount_cents']/100,2)
    # Repeated descriptions across at least three distinct months are candidates, not promised bills.
    recurring = {}
    for r in rows:
        if r['amount_cents'] < 0 and r['category'] != 'Transfer':
            recurring.setdefault(r['description'].lower().strip(),[]).append(r)
    recurring = [dict(description=v[0]['description'], typical=round(median([-r['amount_cents']/100 for r in v]),2),
                      months=len(set(r['date'][:7] for r in v))) for v in recurring.values() if len(set(r['date'][:7] for r in v))>=3]
    return dict(months=months, forecast=f, essential_monthly=essential, safety_buffer=buffer,
        required_monthly=round(required,2), discretionary_monthly=max(0,available),
        current_month_spent=spent, remaining_month_budget=remaining_budget,
        daily_budget=round(remaining_budget/(calendar.monthrange(today.year,today.month)[1]-today.day+1),2),
        monthly_shortfall=max(0,-available), feasible=possible, stale=stale,
        goals=plans, anomalies=anomalies(rows), categories=categories,
        data_through=max((s['end_date'] for s in statements),default=None),
        recurring=recurring[:20], transaction_count=len(rows), currency='INR',
        note='One bank account, INR. Transfers excluded. All goals share one budget; saved amounts must not be counted twice.')
