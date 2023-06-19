import csv
import subprocess
import os

def get_rustdoc_path(name, version, document_hidden):
    with open('tmp_crate_hidden/Cargo.toml', 'w') as f:
        f.write('[package]\nname = "baseline"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n' + name + ' = "=' + version + '"\n')
    proc = subprocess.run(['cargo', 
                           'doc', 
                           '--manifest-path=tmp_crate_hidden/Cargo.toml'], 
                          capture_output=True, 
                          env=dict(os.environ, RUSTC_BOOTSTRAP='1', RUSTDOCFLAGS='-Z unstable-options --document-private-items ' + ('--document-hidden-items ' if document_hidden else '') + '--output-format=json --cap-lints allow'))
    return 'tmp_crate_hidden/target/doc/' + name + '.json'

def save_rustdoc(name, version, document_hidden, path):
    file = get_rustdoc_path(name, version, document_hidden)
    os.rename(file, path)

def get_semver_checks_output(path_baseline_json, path_current_json):
    result = subprocess.run(['cargo', 'run', '--release', '--', 'semver-checks', 'check-release', '--current-rustdoc=' + path_current_json, '--baseline-rustdoc=' + path_baseline_json],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return result.stdout.decode()

def get_hidden_items(name, version):
    with_hidden, without_hidden = 'with_hidden.json', 'without_hidden.json'
    try:
        save_rustdoc(name, version, True, with_hidden)
        save_rustdoc(name, version, False, without_hidden)
        output = get_semver_checks_output(with_hidden, without_hidden)
    except:
        return []    
    ret = set()
    for desc in output.split('--- failure ')[1:]:
        err_type, desc = desc.split('Failed in:')
        err_type = err_type.split(':')[0]
        if err_type == 'method_parameter_count_changed' or (name == 'goblin' and not err_type.endswith('missing')) or err_type == 'auto_trait_impl_removed':
            continue
        print(err_type, desc)
        assert err_type.endswith('missing')
        desc = desc.strip().split('\n')
        desc = [x.strip() for x in desc]
        desc = [x.split(' in ')[0] for x in desc]
        desc = [x.split(' ')[0] for x in desc]
        print(err_type, desc)
        for x in desc:
            ret.add(x)
    return sorted(list(ret))

err_types_with_variants = ['enum_struct_variant_field_added', 'enum_struct_variant_field_missing', 'enum_tuple_variant_field_added', 'enum_tuple_variant_field_missing', 'enum_variant_added', 'enum_variant_missing', 'variant_marked_non_exhaustive']

def tag_hidden_items(err_type, desc, hidden_items):
    def change_line(line):
        if '(hidden)' in line or ' in ' not in line:
            return (False, line)
        l = line.split(' ')
        if len(l) == 0:
            return (False, line)
        importable_path = l[0]
        print(importable_path)
        if err_type == 'method_parameter_count_changed' or err_type in err_types_with_variants:
            if importable_path in hidden_items:
                l[0] = '(hidden) ' + importable_path
                return (True, ' '.join(l))
            importable_path = '::'.join(importable_path.split('::')[:-1])
        if importable_path in hidden_items:
            l[0] = '(hidden) ' + importable_path
            return (True, ' '.join(l))
        return (False, line)
    is_all_hidden = True
    new_desc = []
    for line in desc.split('\n'):
        is_hidden, line = change_line(line)
        if not is_hidden:
            is_all_hidden = False
        new_desc.append(line)
    return (is_all_hidden, '\n'.join(new_desc))

rem_hidden_items = {}

with open('results.csv') as f:
    with open('from_hidden.csv', 'w') as f_out:
        writer = csv.writer(f_out)
        for row in csv.reader(f):
            name = row[0]
            baseline, current = row[1].split(' -> ')

            if 'TODO' in row[2]:
                print(name, baseline, current)
                if (name, baseline) not in rem_hidden_items:
                    rem_hidden_items[(name, baseline)] = get_hidden_items(name, baseline)
                hidden_items = rem_hidden_items[(name, baseline)]
                print(hidden_items)
                (is_all_hidden, row[3]) = tag_hidden_items(row[2].lstrip('TODO '), row[3], hidden_items)
                if is_all_hidden:
                    print('became all hidden')
                    if row[4] != 'doc hidden (confirmed by script)':
                        print('previously "' + row[4] + '", now doc hidden')
                    row[4] = 'doc hidden (confirmed by script)'
            writer.writerow(row)
