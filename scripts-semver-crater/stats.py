import csv
import subprocess
import os

cnt_releases = {}
cnt_items = {}
cnt_crates = {}
all_crates = set()
all_releases = set()

with open('true_positives.csv') as f:
    for row in csv.reader(f):
        name = row[0]
        baseline, current = row[1].split(' -> ')
        err_type = row[2]
        # print(name, baseline, current, err_type)

        if err_type not in cnt_releases:
            cnt_releases[err_type] = 0
            cnt_crates[err_type] = set()
            cnt_items[err_type] = 0
        cnt_releases[err_type] += 1
        cnt_crates[err_type].add(name)

        for line in row[3].split('\n'):
            assert ' in ' in line
            if 'hidden' not in line:
                cnt_items[err_type] += 1

        all_crates.add(name)
        all_releases.add((name, baseline))

print("cnt releases:")
sort = []
for err_type in cnt_releases:
    sort.append((-cnt_items[err_type], err_type.replace('_', '\\_') + " & $" + str(cnt_items[err_type]) + "$ & $" + str(cnt_releases[err_type]) + "$ & $" + str(len(cnt_crates[err_type])) + "$ \\\\"))
sort = sorted(sort)
for _, s in sort:
    print(s)

print("all crates:", len(all_crates))
print("all releases:", len(all_releases))

all_items = 0
sum_of_releases = 0
for err_type in cnt_items:
    sum_of_releases += cnt_releases[err_type]
    all_items += cnt_items[err_type]
print("all items:", all_items)
print("sum of releases:", sum_of_releases)

