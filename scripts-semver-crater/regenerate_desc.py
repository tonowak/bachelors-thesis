import csv
import subprocess
import os

def get_semver_crater_output(name, baseline, current, err_type):
    #os.system("cargo run --release --no-default-features --features semver-crater --bin=semver-crater -- --name=" + name + " --current=" + current + " --baseline=" + baseline + " 2>/dev/null")
            # os.system("cat full_report.csv")
            # os.system("cat full_report.csv >> ces.csv")

    result = subprocess.run(['cargo', 'run', '--release', '--no-default-features', '--features', 'semver-crater', '--bin=semver-crater', '--', 
                             '--name=' + name, '--current=' + current, '--baseline=' + baseline],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    with open('full_report.csv', 'r') as f:
        for row in csv.reader(f):
            print(row)
            if row[2] == err_type:
                return row[3]
    os.system("echo " + name + " " + baseline + " " + current + " >> compilation_errors.txt")
    return ''

def parse_desc(name, err_type, desc):
    desc = desc.split('--- failure ')
    desc = list(filter(lambda t: t.startswith(err_type), desc))
    assert len(desc) == 1
    desc = desc[0].split('Failed in:')[1]
    desc = desc.strip().split('\n')
    desc = [x.strip() for x in desc]
    def get_parsed_loc(line):
        parts = line.split(' in ')
        assert len(parts) == 2
        file = parts[1].lstrip('file ').strip()
        if file.startswith('['):
            return (parts[0], "ignored")
        if ':' not in file:
            file = file.replace(' ', ':')
        assert ':' in file
        filename, line = file.split(':')
        if not filename.startswith('/home/tonowak/.cargo/'):
            return (parts[0], "ignored")
        filename = filename.split('/')[7:]
        docs_link = 'https://docs.rs/' + '/'.join(filename[0].rsplit('-', 1)) + '/src/' + name.replace('-', '_') + '/' + '/'.join(filename[2:]) + '.html#' + line
        return (parts[0], docs_link)
    desc = [get_parsed_loc(line) for line in desc]
    desc = [x + ' in ' + y for (x, y) in desc]
    return desc

with open('results.csv') as f:
    with open('fixed_csv.csv', 'w') as f_out:
        writer = csv.writer(f_out)
        for row in csv.reader(f):
            name = row[0]
            baseline, current = row[1].split(' -> ')
            err_type = row[2]

            if 'TODO' in row[2] and "doesn't compile anymore (confirmed by script)" != row[4]:
                err_type = err_type.lstrip('TODO ')
                print(name, baseline, current, err_type)
                desc = get_semver_crater_output(name, baseline, current, err_type)
                assert desc != ''
                if desc != '':
                    desc = parse_desc(name, err_type, desc)
                    row[3] = '\n'.join(desc)
            writer.writerow(row)
