import json

def parse_date(date_range):
    # Parse date range like 'Dec 30, 2026 - Jan 6, 2026'
    # Extract the first date
    parts = date_range.split(' - ')
    first_date = parts[0].strip()
    
    # Parse 'Dec 30, 2026' format
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    # Remove comma and split
    first_date = first_date.replace(',', '')
    month_str, day, year = first_date.split()
    
    month = month_map.get(month_str, 1)
    day = int(day)
    year = int(year)
    
    return (year, month, day)

data = json.load(open('src/frontend/public/data/weeks.json', 'r'))
data['weeks'].sort(key=lambda w: parse_date(w['date_range']))
json.dump(data, open('src/frontend/public/data/weeks.json', 'w'), indent=2)
print('Sorted weeks.json chronologically')
