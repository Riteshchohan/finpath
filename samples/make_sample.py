"""Create synthetic sample.csv with the six most recent complete months."""
import calendar
import csv
from datetime import date, timedelta
from pathlib import Path

if __name__=='__main__':
    end=date.today().replace(day=1)-timedelta(days=1)
    start=end.replace(day=1)
    for _ in range(5):
        start=(start-timedelta(days=1)).replace(day=1)
    rows=[];month=start;index=0
    while month<=end:
        items=[(1,'Salary payroll',0,60000+index*500),(2,'Apartment rent',15000,0),
               (5,'Electricity bill',1800,0),(8,'Groceries supermarket',4500,0),
               (10,'Broadband utility',900,0),(12,'Metro transport',1200,0),
               (15,'Restaurant dining',1600,0),(18,'Netflix',499,0),
               (20,'Pharmacy medical',650,0),(23,'Shopping',1800,0),
               (25,'Own account transfer',5000,0)]
        if index==5:items.append((26,'Electronics shopping',26000,0))
        for day,description,debit,credit in items:
            rows.append([month.replace(day=day).isoformat(),description,debit or '',credit or ''])
        month=(month.replace(day=calendar.monthrange(month.year,month.month)[1])+timedelta(days=1))
        index+=1
    path=Path(__file__).with_name('sample.csv')
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['date','description','debit','credit']);writer.writerows(rows)
    print(f'Synthetic sample created: {path}\nUpload period: {start} through {end}\nRows: {len(rows)}')
