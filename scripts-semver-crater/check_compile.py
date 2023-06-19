import csv
import subprocess
import os

def cargo_build(manifest_path):
    result = subprocess.run(['cargo', 'build', '--manifest-path=' + manifest_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    # print(result.stderr.decode())
    return (result.returncode == 0, result.stderr.decode())

def get_manifest(name, version):
    return '[package]\nname = "baseline"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n' + name + ' = "=' + version + '"\n'

def try_compile(name, version, librs):
    with open('tmp_crate_witnesses/Cargo.toml', 'w') as f:
        f.write(get_manifest(name, version))
    with open('tmp_crate_witnesses/src/lib.rs', 'w') as f:
        f.write(librs)
    return cargo_build('tmp_crate_witnesses/Cargo.toml')

with open('results.csv') as f:
    with open('from_check_compile.csv', 'w') as f_out:
        writer = csv.writer(f_out)
        for row in csv.reader(f):
            name = row[0]
            baseline, current = row[1].split(' -> ')
            # print(name, baseline, current)

            if "doesn't compile anymore (confirmed by script)" in row[4]:
                if not try_compile(name, baseline, '')[0] or not try_compile(name, current, '')[0]:
                    print('fail', name, baseline, current)
                    row[4] = 'doesn\'t compile anymore (confirmed by script)'
                else:
                    print('success', name, baseline, current)
            writer.writerow(row)
