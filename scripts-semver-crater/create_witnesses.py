import csv
import subprocess
import os

def cargo_build(manifest_path):
    result = subprocess.run(['cargo', 'build', '--manifest-path=' + manifest_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return (result.returncode == 0, result.stderr.decode())

def get_manifest(name, version):
    return '[package]\nname = "baseline"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n' + name + ' = "=' + version + '"\n'

def try_compile(name, version, librs):
    with open('tmp_crate_witnesses/Cargo.toml', 'w') as f:
        f.write(get_manifest(name, version))
    with open('tmp_crate_witnesses/src/lib.rs', 'w') as f:
        f.write(librs)
    return cargo_build('tmp_crate_witnesses/Cargo.toml')

def create_witness_generic_item_missing(name, version, line, line_id):
    importable_path = line[0]
    generic0 = 'fn witness' + str(line_id) + '(value: ' + importable_path + ') {}'
    generic1 = 'fn witness' + str(line_id) + '<T0>(value: ' + importable_path + '<T0>) {}'
    generic2 = 'fn witness' + str(line_id) + '<T0, T1>(value: ' + importable_path + '<T0, T1>) {}'
    generic3 = 'fn witness' + str(line_id) + '<T0, T1, T2>(value: ' + importable_path + '<T0, T1, T2>) {}'
    failure = '// The below case requires nontrivial generic arguments, the script used a fallback pub use.\n//' + generic0 + '\n' + 'use ' + importable_path + ';'
    for g in [generic0, generic1, generic2, generic3, failure]:
        if try_compile(name, version, g)[0]:
            return g
    return generic0

def create_witness_trait_missing(name, version, line, line_id):
    importable_path = line[0]
    generic0 = 'fn _witness' + str(line_id) + '<T: ' + importable_path + '>(_value: T) {}'
    generic1 = 'fn _witness' + str(line_id) + '<X0, T: ' + importable_path + '<X0>>(_value: T) {}'
    generic2 = 'fn _witness' + str(line_id) + '<X0, X1, T: ' + importable_path + '<X0, X1>>(_value: T) {}'
    failure = '// The below case requires nontrivial generic arguments, the script used a fallback pub use.\n//' + generic0 + '\n' + 'use ' + importable_path + ';'
    for g in [generic0, generic1, generic2, failure]:
        if try_compile(name, version, g)[0]:
            return g
    return generic0

def create_witness_fun_par_cnt_changed(name, version, line, line_id):
    path = line[0]
    argcount = line[7]
    argcount = int(argcount)
    args = ("todo!(), " * argcount)[:-2]
    return f"fn _witness" + str(line_id) + f"() {{ {path}({args}); }}"

def create_witness_function_rm(name, version, line, line_id):
    importable_path = line[0]
    argc0 = 'fn witness' + str(line_id) + '() { ' + importable_path + '(); }'
    argc1 = 'fn witness' + str(line_id) + '() { ' + importable_path + '(todo!()); }'
    argc2 = 'fn witness' + str(line_id) + '() { ' + importable_path + '(todo!(), todo!()); }'
    argc3 = 'fn witness' + str(line_id) + '() { ' + importable_path + '(todo!(), todo!(), todo!()); }'
    argc4 = 'fn witness' + str(line_id) + '() { ' + importable_path + '(todo!(), todo!(), todo!(), todo!()); }'
    failure_witness = 'fn witness' + str(line_id) + '() { use ' + importable_path + '; }'
    failure = '// The below case requires nontrivial function arguments, the script used a fallback pub use.\n//' + argc0 + '\n' + failure_witness
    for g in [argc0, argc1, argc2, argc3, argc4, failure]:
        if try_compile(name, version, g)[0]:
            return g
    return argc0

def create_witness_trait_impl_rm(name, version, line, line_id):
    assert line[1] == 'no' and line[2] == 'longer'
    importable_path, trait = line[0], line[-1]
    print(importable_path, trait)
    if trait in ['Send', 'Sync', 'Unpin', 'Copy', 'Sized', 'Copy']:
        trait = 'core::marker::' + trait
    elif trait in ['UnwindSafe', 'RefUnwindSafe']:
        trait = 'core::panic::' + trait
    elif trait == 'Hash':
        trait = 'core::hash::' + trait
    elif trait == 'Debug':
        trait = 'core::fmt::' + trait
    elif trait in ['Eq', 'Ord', 'PartialEq', 'PartialOrd']:
        trait = 'core::cmp::' + trait
    elif trait == 'Clone':
        trait = 'core::clone::' + trait
    else:
        assert False
    sum_traits = 'core::marker::Send + core::marker::Sync + core::marker::Unpin + core::marker::Copy + core::marker::Sized + core::marker::Copy + core::panic::UnwindSafe + core::panic::RefUnwindSafe + core::hash::Hash + core::fmt::Debug + core::cmp::Eq + core::cmp::Ord + core::cmp::PartialEq + core::cmp::PartialOrd + core::clone::Clone'
    generic0 = 'fn witness' + str(line_id) + '(value: ' + importable_path + ') { witness_take' + str(line_id) + '(value); }\n' + ' fn witness_take' + str(line_id) + '<T: ' + trait + '>(_value: T) {}'
    generic1 = 'fn witness' + str(line_id) + '<T0: ' + sum_traits + '>(value: ' + importable_path + '<T0>) { witness_take' + str(line_id) + '(value); }\n' + ' fn witness_take' + str(line_id) + '<T: ' + trait + '>(_value: T) {}'
    generic2 = 'fn witness' + str(line_id) + '<T0: ' + sum_traits + ', T1: ' + sum_traits + '>(value: ' + importable_path + '<T0, T1>) { witness_take' + str(line_id) + '(value); }\n' + ' fn witness_take' + str(line_id) + '<T: ' + trait + '>(_value: T) {}'
    generic3 = 'fn witness' + str(line_id) + '<T0: ' + sum_traits + ', T1: ' + sum_traits + ', T2: ' + sum_traits + '>(value: ' + importable_path + '<T0, T1, T2>) { witness_take' + str(line_id) + '(value); }\n' + ' fn witness_take' + str(line_id) + '<T: ' + trait + '>(_value: T) {}'
    generic4 = 'fn witness' + str(line_id) + '<T0: ' + sum_traits + ', T1: ' + sum_traits + ', T2: ' + sum_traits + ', T3: ' + sum_traits + '>(value: ' + importable_path + '<T0, T1, T2, T3>) { witness_take' + str(line_id) + '(value); }\n' + ' fn witness_take' + str(line_id) + '<T: ' + trait + '>(_value: T) {}'
    for g in [generic0, generic1, generic2, generic3, generic4]:
        if try_compile(name, version, g)[0]:
            return g
    return generic0

def create_witness_variant_missing(name, version, line, line_id):
    importable_path = line[0]
    enum_path = '::'.join(importable_path.split('::')[:-1])
    variant_name = importable_path.split('::')[-1]
    generic0 = 'fn witness' + str(line_id) + '(value: ' + enum_path + ') {\n\tif let ' + importable_path + '{..} = value {\n\t\tprintln!("matched");\n\t}\n}'
    return generic0

def create_witness_struct_pub_field_rm(name, version, line, line_id):
    assert line[1] == 'field'
    importable_path, field = line[0], line[2]
    generic0 = 'fn witness' + str(line_id) + '(value: ' + importable_path + ') { let x = value.' + field + '; }'
    generic1 = 'fn witness' + str(line_id) + '<T0>(value: ' + importable_path + '<T0>) { let x = value.' + field + '; }'
    generic2 = 'fn witness' + str(line_id) + '<T0, T1>(value: ' + importable_path + '<T0, T1>) { let x = value.' + field + '; }'
    for g in [generic0, generic1, generic2]:
        if try_compile(name, version, g)[0]:
            return g
    return generic0

def create_witness_enum_variant_added(name, version, line, line_id):
    importable_path = line[0]
    importable_path = '::'.join(importable_path.split('::')[:-1])
    # cargo run --quiet --manifest-path=custom_trustfall_query/Cargo.toml -- --name base64 --version 0.12.1 --importable-path "base64::CharacterSet::BinHex" --query-type enum
    result = subprocess.run(['cargo', 'run', '--quiet', '--manifest-path', 'custom_trustfall_query/Cargo.toml', '--', '--name', name, '--version', version, '--importable-path', importable_path, '--query-type', 'enum'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        return 'failure while retrieving variants through another script'
    output = result.stdout.decode()
    variants = output.strip().split(", ")
    print(variants)
    generic0 = 'fn witness' + str(line_id) + '(value: ' + importable_path + ') {\n\tmatch value {\n' + '\n'.join(['\t\t| ' + importable_path + '::' + x + '{..} => {},' for x in variants]) + '\n\t}\n}'
    return generic0

def create_witness_nonexhaustive(name, version, line, line_id):
    importable_path = line[0]
    # cargo run --quiet --manifest-path=custom_trustfall_query/Cargo.toml -- --name base64 --version 0.12.1 --importable-path "base64::CharacterSet::BinHex" --query-type enum
    result = subprocess.run(['cargo', 'run', '--quiet', '--manifest-path', 'custom_trustfall_query/Cargo.toml', '--', '--name', name, '--version', version, '--importable-path', importable_path, '--query-type', 'enum'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        return 'failure while retrieving variants through another script'
    output = result.stdout.decode()
    variants = output.strip().split(", ")
    print(variants)
    generic0 = 'fn witness' + str(line_id) + '(value: ' + importable_path + ') {\n\tmatch value {\n' + '\n'.join(['\t\t| ' + importable_path + '::' + x + '{..} => {},' for x in variants]) + '\n\t}\n}'
    return generic0

def create_witness_constr_str_adds_field(name, version, line, line_id):
    importable_path = line[0]
    assert line[1] == 'field'
    result = subprocess.run(['cargo', 'run', '--quiet', '--manifest-path', 'custom_trustfall_query/Cargo.toml', '--', '--name', name, '--version', version, '--importable-path', importable_path, '--query-type', 'struct'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        return 'failure while retrieving fields through another script'
    output = result.stdout.decode()
    fields = output.strip().split(", ")
    print(fields)
    generic0 = 'fn witness' + str(line_id) + '() {\n\tlet _ = ' + importable_path + ' {\n' + '\n'.join(['\t\t' + x + ': todo!(),' for x in fields]) + '\n\t};\n}'
    return generic0

def try_witness(row):
    err_type = row[2]
    name = row[0]
    baseline, current = row[1].split(' -> ')

    f = None
    if err_type in ['struct_missing', 'enum_missing', 'struct_missing']:
        f = create_witness_generic_item_missing
    elif err_type == 'trait_missing':
        f = create_witness_trait_missing
    elif err_type in ['function_parameter_count_changed', 'method_parameter_count_changed']:
        f = create_witness_fun_par_cnt_changed
    elif err_type in ['function_missing', 'inherent_method_missing']:
        f = create_witness_function_rm
    elif err_type in ['auto_trait_impl_removed', 'derive_trait_impl_removed']:
        f = create_witness_trait_impl_rm
    elif err_type in ['enum_variant_missing']:
        f = create_witness_variant_missing
    elif err_type in ['struct_pub_field_missing']:
        f = create_witness_struct_pub_field_rm
    elif err_type == 'enum_variant_added':
        f = create_witness_enum_variant_added
    elif err_type == 'enum_marked_non_exhaustive':
        f = create_witness_nonexhaustive
    elif err_type == 'constructible_struct_adds_field':
        f = create_witness_constr_str_adds_field
    else:
        return None
    assert f is not None

    desc = row[3]
    librs = '#![allow(warnings)]\n'
    line_id = 0
    for line in desc.split('\n'):
        og_line = line
        line = line.split(' in ')[0]
        print('line', line)
        if '(hidden)' in line:
            continue
        line = line.split(' ')
        librs += f(name, baseline, line, line_id) + '\n'
        line_id += 1
    print(row, librs)

    (status_baseline, output_baseline) = try_compile(name, baseline, librs)
    if status_baseline:
        output_baseline = 'compiles'
    print(status_baseline, output_baseline)
    (status_current, output_current) = try_compile(name, current, librs)
    if status_current:
        output_current = 'compiles'
    print(status_current, output_current)

    while len(row) <= 10:
        row.append('')

    row[5] = librs
    row[6] = output_baseline
    row[7] = output_current
    row[8] = get_manifest(name, baseline)
    row[9] = get_manifest(name, current).replace('baseline', 'current')

    if status_baseline == False:
        row[4] = 'witness baseline compile error\nTODO: manually check\n' + row[4]
    elif status_current == True:
        row[4] = 'witness false-positive\nTODO: confirm results\n' + row[4]
    else:
        row[4] = 'witness true-positive\nTODO: confirm results\n' + row[4]

    return row

with open('results.csv') as f:
    with open('from_witnesses.csv', 'w') as f_out:
        writer = csv.writer(f_out)
        for row in csv.reader(f):
            name = row[0]
            baseline, current = row[1].split(' -> ')

            if row[2] != 'compile error' and row[4] != 'doc hidden (confirmed by script)' and row[4] != "doesn't compile anymore (confirmed by script)":
                # if 'witness baseline compile error' in row[4] and row[2] == 'function_missing':
                # if row[2] == 'enum_marked_non_exhaustive':#  and 'witness baseline compile error' in row[4]:
                if 'function_missing' == row[2] and 'baseline compile error' in row[4]:
                    print(name, baseline, current)
                    new_row = try_witness(row)
                    if new_row is not None:
                        row = new_row
            writer.writerow(row)
