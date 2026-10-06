import csv
with open('categories.csv', 'r', encoding='utf-8') as file:
    reader = list(csv.reader(file))
with open('SachThieuNhi_url_link.csv', 'w', encoding='utf-8', newline='') as file:
    writer = csv.writer(file)
    for rows in reader[66:75]:
        writer.writerow([rows[0], rows[3]])